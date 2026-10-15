package org.munassiq.app.ui

import android.graphics.BitmapFactory
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.munassiq.app.BuildConfig
import java.net.URL
import javax.net.ssl.HttpsURLConnection
import kotlin.math.*

/** Compose OSM canvas: manual navigation only, no GPS or location permissions. */
@Composable fun MapScreen(model:AppViewModel,picker:Boolean=false,onPick:((Double,Double)->Unit)?=null){
    var latitude by remember{mutableDoubleStateOf(33.5138)}
    var longitude by remember{mutableDoubleStateOf(36.2765)}
    var zoom by remember{mutableIntStateOf(11)}
    var markers by remember{mutableStateOf(emptyList<org.json.JSONObject>())}
    var selection by remember{mutableStateOf<Pair<Double,Double>?>(null)}
    var cluster by remember{mutableStateOf(emptyList<org.json.JSONObject>())}
    var failed by remember{mutableStateOf(false)}
    val tiles=remember{mutableStateMapOf<String,ImageBitmap>()}
    fun project(lat:Double,lon:Double):Pair<Double,Double>{val size=256.0*2.0.pow(zoom);val sine=sin(lat.coerceIn(-85.0,85.0)*PI/180);return (lon+180)/360*size to (.5-ln((1+sine)/(1-sine))/(4*PI))*size}
    fun unproject(x:Double,y:Double):Pair<Double,Double>{val size=256.0*2.0.pow(zoom);return atan(sinh(PI*(1-2*y/size)))*180/PI to ((x/size*360)%360+360)%360-180}
    LaunchedEffect(Unit){if(!picker)try{
        var page:Int?=1;val result=mutableListOf<org.json.JSONObject>()
        while(page!=null){val value=model.repository.load("map/services/?page=$page").value as org.json.JSONObject;result+=rows(value);page=if(value.isNull("next_page"))null else value.optInt("next_page").takeIf{it>0}}
        markers=result
    }catch(_:Exception){failed=true}}
    LaunchedEffect(latitude,longitude,zoom){
        if(BuildConfig.MAP_TILES.isBlank())return@LaunchedEffect
        val center=project(latitude,longitude);val tileX=floor(center.first/256).toInt();val tileY=floor(center.second/256).toInt()
        tiles.clear()
        for(x in tileX-2..tileX+2)for(y in tileY-1..tileY+1){
            if(y<0||y>=2.0.pow(zoom).toInt())continue
            val key="$x:$y";try{
                val image=withContext(Dispatchers.IO){val url=BuildConfig.MAP_TILES.replace("{z}",zoom.toString()).replace("{x}",Math.floorMod(x,2.0.pow(zoom).toInt()).toString()).replace("{y}",y.toString());val connection=URL(url).openConnection() as HttpsURLConnection
                    try{connection.connectTimeout=8000;connection.readTimeout=8000;connection.setRequestProperty("User-Agent","Munassiq Android");connection.inputStream.use{BitmapFactory.decodeStream(it)}?.asImageBitmap()}finally{connection.disconnect()}}
                if(image!=null)tiles[key]=image
            }catch(_:Exception){failed=true}
        }
    }
    Column(Modifier.fillMaxWidth()){
        Row(horizontalArrangement=Arrangement.spacedBy(6.dp)){
            OutlinedButton(onClick={zoom=(zoom+1).coerceAtMost(18)}){Text("+")}
            OutlinedButton(onClick={zoom=(zoom-1).coerceAtLeast(2)}){Text("−")}
            OutlinedButton(onClick={longitude-=360/2.0.pow(zoom+1)}){Text("←")}
            OutlinedButton(onClick={longitude+=360/2.0.pow(zoom+1)}){Text("→")}
        }
        Row{TextButton(onClick={latitude=(latitude+180/2.0.pow(zoom+1)).coerceAtMost(85.0)}){Text("↑")};TextButton(onClick={latitude=(latitude-180/2.0.pow(zoom+1)).coerceAtLeast(-85.0)}){Text("↓")}}
        Canvas(Modifier.fillMaxWidth().height(300.dp).pointerInput(latitude,longitude,zoom,markers){detectTapGestures{point->
            val center=project(latitude,longitude);val chosen=unproject(center.first-size.width/2+point.x,center.second-size.height/2+point.y)
            if(picker){selection=chosen;onPick?.invoke(chosen.first,chosen.second)}else{
                val near=markers.filter{row->val p=row.getJSONObject("payload");val position=project(p.optDouble("latitude"),p.optDouble("longitude"));hypot(position.first-center.first+size.width/2-point.x,position.second-center.second+size.height/2-point.y)<35}
                if(near.size==1)model.open(Screen("services/${near[0].getLong("id")}/","services","detail"))
                else if(near.isNotEmpty()){if(zoom<18){latitude=chosen.first;longitude=chosen.second;zoom=(zoom+2).coerceAtMost(18)}else cluster=near}
            }
        }}){
            drawRect(Color(0xFFE4ECE6));val center=project(latitude,longitude)
            tiles.forEach{(key,image)->val parts=key.split(':');drawImage(image,dstOffset=IntOffset((parts[0].toInt()*256-center.first+size.width/2).toInt(),(parts[1].toInt()*256-center.second+size.height/2).toInt()),dstSize=IntSize(256,256))}
            markers.groupBy{row->val p=row.getJSONObject("payload");val pos=project(p.optDouble("latitude"),p.optDouble("longitude"));floor(pos.first/35).toInt() to floor(pos.second/35).toInt()}.values.forEach{group->
                val p=group.first().getJSONObject("payload");val pos=project(p.optDouble("latitude"),p.optDouble("longitude"));drawCircle(Color(0xFF176B61),if(group.size>1)18f else 10f,Offset((pos.first-center.first+size.width/2).toFloat(),(pos.second-center.second+size.height/2).toFloat()))}
            selection?.let{val p=project(it.first,it.second);drawCircle(Color(0xFFAD5935),12f,Offset((p.first-center.first+size.width/2).toFloat(),(p.second-center.second+size.height/2).toFloat()))}
        }
        if(failed)Text(label("map_unavailable"))
        Text("© OpenStreetMap contributors",style=MaterialTheme.typography.labelSmall)
        cluster.forEach{row->TextButton(onClick={model.open(Screen("services/${row.getLong("id")}/","services","detail"))}){Text(row.getJSONObject("payload").optString("name"))}}
    }
}
