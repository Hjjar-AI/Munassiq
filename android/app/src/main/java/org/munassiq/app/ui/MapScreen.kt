package org.munassiq.app.ui

import android.graphics.BitmapFactory
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.contentDescription
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
@Composable fun MapScreen(model:AppViewModel,picker:Boolean=false,initialLatitude:Double?=null,initialLongitude:Double?=null,onPick:((Double,Double)->Unit)?=null){
    val context=LocalContext.current
    var reload by remember{mutableIntStateOf(0)}
    var shown by remember{mutableIntStateOf(20)}
    var coordinateError by remember{mutableStateOf<String?>(null)}
    var latitude by remember(initialLatitude){mutableDoubleStateOf(initialLatitude?:33.5138)}
    var longitude by remember(initialLongitude){mutableDoubleStateOf(initialLongitude?:36.2765)}
    var zoom by remember{mutableIntStateOf(11)}
    var markers by remember{mutableStateOf(emptyList<org.json.JSONObject>())}
    var selection by remember{mutableStateOf<Pair<Double,Double>?>(if(picker&&initialLatitude!=null&&initialLongitude!=null)initialLatitude to initialLongitude else null)}
    var cluster by remember{mutableStateOf(emptyList<org.json.JSONObject>())}
    var failed by remember{mutableStateOf(false)}
    val tiles=remember{mutableStateMapOf<String,ImageBitmap>()}
    fun project(lat:Double,lon:Double):Pair<Double,Double>{val size=256.0*2.0.pow(zoom);val sine=sin(lat.coerceIn(-85.0,85.0)*PI/180);return (lon+180)/360*size to (.5-ln((1+sine)/(1-sine))/(4*PI))*size}
    fun unproject(x:Double,y:Double):Pair<Double,Double>{val size=256.0*2.0.pow(zoom);return atan(sinh(PI*(1-2*y/size)))*180/PI to ((x/size*360)%360+360)%360-180}
    LaunchedEffect(reload){if(!picker)try{
        var page:Int?=1;val result=mutableListOf<org.json.JSONObject>()
        while(page!=null){val value=model.repository.load("map/services/?page=$page").value as org.json.JSONObject;result+=rows(value);page=if(value.isNull("next_page"))null else value.optInt("next_page").takeIf{it>0}}
        markers=result
    }catch(error:Exception){if(error is kotlinx.coroutines.CancellationException)throw error;failed=true}}
    LaunchedEffect(latitude,longitude,zoom,reload){
        if(BuildConfig.MAP_TILES.isBlank())return@LaunchedEffect
        val center=project(latitude,longitude);val tileX=floor(center.first/256).toInt();val tileY=floor(center.second/256).toInt()
        tiles.clear()
        for(x in tileX-2..tileX+2)for(y in tileY-1..tileY+1){
            if(y<0||y>=2.0.pow(zoom).toInt())continue
            val key="$x:$y";try{
                val image=withContext(Dispatchers.IO){val url=BuildConfig.MAP_TILES.replace("{z}",zoom.toString()).replace("{x}",Math.floorMod(x,2.0.pow(zoom).toInt()).toString()).replace("{y}",y.toString());val connection=URL(url).openConnection() as HttpsURLConnection
                    try{connection.connectTimeout=8000;connection.readTimeout=8000;connection.setRequestProperty("User-Agent","Munassiq Android");connection.inputStream.use{BitmapFactory.decodeStream(it)}?.asImageBitmap()}finally{connection.disconnect()}}
                if(image!=null)tiles[key]=image
            }catch(error:Exception){if(error is kotlinx.coroutines.CancellationException)throw error;failed=true}
        }
    }
    Column(Modifier.fillMaxWidth().heightIn(max=650.dp).verticalScroll(rememberScrollState())){
        var latitudeText by remember(latitude){mutableStateOf(latitude.toString())}
        var longitudeText by remember(longitude){mutableStateOf(longitude.toString())}
        OutlinedTextField(latitudeText,{latitudeText=it},label={Text(label("latitude"))},keyboardOptions=KeyboardOptions(keyboardType=KeyboardType.Decimal))
        OutlinedTextField(longitudeText,{longitudeText=it},label={Text(label("longitude"))},keyboardOptions=KeyboardOptions(keyboardType=KeyboardType.Decimal))
        coordinateError?.let{Text(it,color=MaterialTheme.colorScheme.error)}
        OutlinedButton(onClick={
            val lat=normalizedInput(latitudeText).toDoubleOrNull()
            val lon=normalizedInput(longitudeText).toDoubleOrNull()
            if(lat==null||lon==null||!lat.isFinite()||!lon.isFinite()||lat !in -85.0..85.0||lon !in -180.0..180.0)coordinateError=context.getString(org.munassiq.app.R.string.invalid_number)
            else{latitude=lat;longitude=lon;coordinateError=null}
        }){Text(label("move_map"))}
        if(picker)OutlinedButton(onClick={selection=latitude to longitude;onPick?.invoke(latitude,longitude)}){Text(label("pick_center"))}
        val mapDescription=label("map_description")
        val zoomIn=label("zoom_in");val zoomOut=label("zoom_out")
        val west=label("pan_west");val east=label("pan_east");val north=label("pan_north");val south=label("pan_south")
        Row(horizontalArrangement=Arrangement.spacedBy(6.dp)){
            OutlinedButton(modifier=Modifier.semantics{contentDescription=zoomIn},onClick={zoom=(zoom+1).coerceAtMost(18)}){Text("+")}
            OutlinedButton(modifier=Modifier.semantics{contentDescription=zoomOut},onClick={zoom=(zoom-1).coerceAtLeast(2)}){Text("−")}
            OutlinedButton(modifier=Modifier.semantics{contentDescription=west},onClick={longitude=(longitude-360/2.0.pow(zoom+1)).coerceAtLeast(-180.0)}){Text("←")}
            OutlinedButton(modifier=Modifier.semantics{contentDescription=east},onClick={longitude=(longitude+360/2.0.pow(zoom+1)).coerceAtMost(180.0)}){Text("→")}
        }
        Row{TextButton(modifier=Modifier.semantics{contentDescription=north},onClick={latitude=(latitude+180/2.0.pow(zoom+1)).coerceAtMost(85.0)}){Text("↑")};TextButton(modifier=Modifier.semantics{contentDescription=south},onClick={latitude=(latitude-180/2.0.pow(zoom+1)).coerceAtLeast(-85.0)}){Text("↓")}}
        Canvas(Modifier.fillMaxWidth().height(300.dp).semantics{contentDescription=mapDescription}.pointerInput(latitude,longitude,zoom,markers){detectTapGestures{point->
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
        if(failed){Text(label("map_unavailable"));TextButton(onClick={failed=false;reload++}){Text(label("retry"))}}
        selection?.let{Text(label("latitude")+": "+it.first+" · "+label("longitude")+": "+it.second)}
        if(!picker){
            Text(label("map_places"))
            markers.take(shown).forEach{row->TextButton(onClick={model.open(Screen("services/${row.getLong("id")}/","services","detail"))}){Text(row.getJSONObject("payload").optString("name"))}}
            if(shown<markers.size)TextButton(onClick={shown+=20}){Text(label("load_more"))}
        }
        Text("© OpenStreetMap contributors",style=MaterialTheme.typography.labelSmall)
        cluster.forEach{row->TextButton(onClick={model.open(Screen("services/${row.getLong("id")}/","services","detail"))}){Text(row.getJSONObject("payload").optString("name"))}}
    }
}
