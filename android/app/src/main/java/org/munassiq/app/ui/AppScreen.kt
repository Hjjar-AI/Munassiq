package org.munassiq.app.ui

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.*
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import org.munassiq.app.BuildConfig
import org.munassiq.app.R
import org.munassiq.app.notifications.DeviceSync
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun AppScreen(model:AppViewModel){
    val state by model.state.collectAsStateWithLifecycle()
    val context=LocalContext.current
    val scope=rememberCoroutineScope()
    val prefs=remember{context.getSharedPreferences("display",Context.MODE_PRIVATE)}
    var onboarding by remember{mutableStateOf(!prefs.getBoolean("onboarding_seen",false))}
    var editor by remember{mutableStateOf<FormSpec?>(null)}
    var confirmation by remember{mutableStateOf<Pair<String,()->Unit>?>(null)}
    var permissionAction by remember{mutableStateOf<(() -> Unit)?>(null)}
    var banners by remember(state.user){mutableStateOf(emptyList<JSONObject>())}
    LaunchedEffect(state.screen.path,state.user){if(state.screen.title=="events")runCatching{banners=rows(model.lookup("announcements/"))}}
    val permission=rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()){
        DeviceSync.enqueue(context);permissionAction?.invoke();permissionAction=null
    }
    fun withNotificationPermission(action:()->Unit){
        if(Build.VERSION.SDK_INT>=33&&ContextCompat.checkSelfPermission(context,Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED){permissionAction=action;permission.launch(Manifest.permission.POST_NOTIFICATIONS)}
        else{DeviceSync.enqueue(context);action()}
    }
    fun confirm(title:String,action:()->Unit){confirmation=title to action}
    val dark=when(prefs.getString("theme","system")){"dark"->true;"light"->false;else->isSystemInDarkTheme()}
    MunassiqTheme(dark){
        BackHandler{if(editor!=null)editor=null else model.back()}
        fun destination(key:String)=when(key){
            "map"->Screen("map/services/","map","map")
            "registrations"->Screen("me/registrations/",key)
            "mine"->Screen("me/items/",key)
            else->Screen("$key/"+(if(key=="events")"?sort=date" else ""),key)
        }
        Scaffold(containerColor=MaterialTheme.colorScheme.background,
            topBar={Column{
                Row(Modifier.fillMaxWidth().padding(horizontal=20.dp,vertical=12.dp),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(12.dp)){
                    Column(Modifier.weight(1f)){
                        Text(label("app_name"),color=MaterialTheme.colorScheme.primary,style=MaterialTheme.typography.labelLarge)
                        Text(label(editor?.title?:state.screen.title),style=MaterialTheme.typography.headlineSmall)
                    }
                    if(editor!=null||state.screen.kind!="list")TextButton(onClick={if(editor!=null)editor=null else model.back()}){Text(label("back"))}
                    IconButton(onClick={editor=null;model.open(Screen("","settings","settings"))}){
                        AppGlyph("settings",modifier=Modifier.size(24.dp).semantics{contentDescription=context.getString(R.string.settings)})
                    }
                }
                LazyRow(Modifier.fillMaxWidth().padding(horizontal=20.dp),horizontalArrangement=Arrangement.spacedBy(8.dp)){
                    items(listOf("categories","mine")){key->FilterChip(selected=editor==null&&state.screen.title==key,onClick={editor=null;model.open(destination(key))},label={Text(label(key))})}
                }
            }},
            bottomBar={NavigationBar(containerColor=MaterialTheme.colorScheme.surface,tonalElevation=2.dp){
                for(key in listOf("events","services","map","registrations"))NavigationBarItem(
                    selected=editor==null&&state.screen.title==key,
                    onClick={editor=null;model.open(destination(key))},
                    icon={AppGlyph(key,color=if(state.screen.title==key)MaterialTheme.colorScheme.onSecondaryContainer else MaterialTheme.colorScheme.onSurfaceVariant)},
                    label={Text(label(key),style=MaterialTheme.typography.labelSmall)}
                )
            }}
        ){padding->Column(Modifier.padding(padding).fillMaxSize()){
            if(BuildConfig.IS_VALIDATION)Text(label("validation_build"),color=MaterialTheme.colorScheme.error,modifier=Modifier.padding(12.dp))
            state.error?.let{message->Text(if(message in listOf("session_expired","request_failed","connection_failed"))label(message) else message,color=MaterialTheme.colorScheme.error,modifier=Modifier.padding(12.dp).semantics{liveRegion=LiveRegionMode.Polite})}
            state.message?.let{Text(label(it),modifier=Modifier.padding(12.dp))}
            if(state.offline)Row{Text(label("offline"),Modifier.weight(1f));TextButton(onClick={model.refresh()}){Text(label("retry"))}}
            if(editor!=null){FormsScreen(model,editor!!){editor=null;model.refresh()}}
            else when(state.screen.kind){
                "login"->LoginScreen(model){editor=NativeForms.account(it)}
                "settings"->SettingsScreen(model,{editor=it})
                "map"->MapScreen(model)
                "detail"->DetailScreen(model,state,{editor=it},{title,act->confirm(title,act)},{withNotificationPermission(it)})
                "occurrence"->OccurrenceScreen(model,state,{editor=it},{title,act->confirm(title,act)},{withNotificationPermission(it)})
                "policies"->LazyColumn(Modifier.padding(16.dp)){item{val value=state.data as? JSONObject;Text(value?.optString(if(context.resources.configuration.locales[0].language=="ar")"terms_ar"else"terms_en").orEmpty());Text(value?.optString(if(context.resources.configuration.locales[0].language=="ar")"privacy_ar"else"privacy_en").orEmpty())}}
                "follows"->FollowsScreen(model,state,{title,act->confirm(title,act)})
                else->PullToRefreshBox(isRefreshing=state.busy,onRefresh={model.refresh()}){
                    LazyColumn(Modifier.fillMaxSize().padding(horizontal=20.dp),contentPadding=PaddingValues(top=12.dp,bottom=24.dp),verticalArrangement=Arrangement.spacedBy(14.dp)){
                        if(state.screen.title in listOf("events","services"))item{BrowseIntro(state.screen.title)}
                        if(state.screen.title=="events")items(banners){banner->Card(Modifier.fillMaxWidth()){Column(Modifier.padding(12.dp)){Text(banner.optString(if(context.resources.configuration.locales[0].language=="ar")"title_ar"else"title_en"));Text(banner.optString(if(context.resources.configuration.locales[0].language=="ar")"body_ar"else"body_en"))}}}
                        if(state.screen.title in listOf("events","services"))item{FilterBar(model,state.screen.title)}
                        if(state.screen.title=="mine"&&state.user?.optJSONArray("roles")?.toString()?.contains("organizer")==true)item{
                            Text(label("organizer_guide"));Row{Button(onClick={editor=NativeForms.content("event")}){Text(label("new_event"))};Button(onClick={editor=NativeForms.content("service")}){Text(label("new_service"))}}
                        }
                        items(rows(state.data),key={it.optLong("id")}){row->
                            Card(Modifier.fillMaxWidth(),shape=RoundedCornerShape(24.dp),colors=CardDefaults.cardColors(containerColor=MaterialTheme.colorScheme.surface),elevation=CardDefaults.cardElevation(defaultElevation=1.dp)){
                                Column(Modifier.padding(20.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
                                    val payload=row.optJSONObject("payload")
                                    Row(horizontalArrangement=Arrangement.spacedBy(8.dp),verticalAlignment=Alignment.CenterVertically){
                                        AppGlyph(if(row.optString("kind")=="service")"services" else "events",Modifier.size(20.dp))
                                        Text(label(if(row.optString("kind")=="service")"services" else if(row.has("occurrence_id"))"registration" else state.screen.title),style=MaterialTheme.typography.labelMedium,color=MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                    var registrationTitle by remember(row.optLong("id")){mutableStateOf("")}
                                    LaunchedEffect(row.optLong("occurrence_id")){if(row.has("occurrence_id"))runCatching{registrationTitle=(model.repository.load("occurrences/${row.optLong("occurrence_id")}/").value as JSONObject).optJSONObject("payload")?.optString("title").orEmpty()}}
                                    Text(registrationTitle.ifBlank{payload?.optString("title",payload.optString("name"))?:row.optString("name",row.optString(if(context.resources.configuration.locales[0].language=="ar")"name_ar"else"name_en",label("registration")))},style=MaterialTheme.typography.titleMedium)
                                    when{
                                        row.has("occurrence_id")->{
                                            Text(label(row.optString("state")))
                                            TextButton(onClick={model.open(Screen("occurrences/${row.getLong("occurrence_id")}/?time_zone=${Uri.encode(ZoneId.systemDefault().id)}","events","occurrence"))}){Text(label("open_details"))}
                                            for(action in listOf("cancel","reconfirm")){val caption=label(if(action=="cancel")"cancel_registration" else "reconfirm");TextButton(onClick={confirm(caption){model.act("registrations/${row.getLong("id")}/$action/")}}){Text(caption)}}
                                        }
                                        payload!=null->{
                                            if(row.has("status"))Surface(shape=RoundedCornerShape(10.dp),color=MaterialTheme.colorScheme.secondaryContainer){Text(label(row.optString("status")),Modifier.padding(horizontal=12.dp,vertical=5.dp),style=MaterialTheme.typography.labelMedium)}
                                            row.optJSONObject("date_range")?.let{range->Text(formatTime(context,range.optString("start"))+" — "+formatTime(context,range.optString("end")))}
                                            val kind=row.optString("kind","event")
                                            TextButton(onClick={model.open(Screen("${kind}s/${row.getLong("id")}/?time_zone=${Uri.encode(ZoneId.systemDefault().id)}",if(kind=="event")"events" else "services","detail"))}){Text(label("open_details"))}
                                            if(state.screen.title=="mine"){
                                                row.optString("rejection_reason").takeIf{it.isNotBlank()}?.let{Text(it)}
                                                TextButton(onClick={editor=NativeForms.content(kind,row.getLong("id"),payload)}){Text(label("edit"))}
                                            }
                                        }
                                        state.screen.title=="categories"->{
                                            TextButton(onClick={model.open(Screen("events/?category=${row.getLong("id")}","events"))}){Text(label("events"))}
                                            val following=label("follow");TextButton(onClick={model.act("me/follows/categories/${row.getLong("id")}/","PUT")}){Text(following)}
                                            TextButton(onClick={model.act("me/follows/categories/${row.getLong("id")}/","DELETE")}){Text(label("unfollow"))}
                                        }
                                        state.screen.title=="requests"->{Text(label(row.optString("status")));Text(row.optString("decision_reason"))}
                                    }
                                }
                            }
                        }
                        val value=state.data as? JSONObject
                        if(value?.optInt("next_page",0)?.let{it>0}==true)item{TextButton(onClick={
                            val path=state.screen.path.substringBefore('?');val query=Uri.parse(state.screen.path).buildUpon().clearQuery()
                            val original=Uri.parse(state.screen.path)
                            original.queryParameterNames.filter{it!="page"}.forEach{query.appendQueryParameter(it,original.getQueryParameter(it))}
                            query.appendQueryParameter("page",value.getInt("next_page").toString());model.open(state.screen.copy(path=path+"?"+query.build().encodedQuery))
                        }){Text(label("next"))}}
                        if(rows(state.data).isEmpty()&&!state.busy)item{Text(label("empty"))}
                        item{Text("GeoNames · CC BY 4.0",style=MaterialTheme.typography.labelSmall)}
                    }
                }
            }
        }}
        confirmation?.let{(title,action)->AlertDialog(onDismissRequest={confirmation=null},title={Text(title)},text={Text(label("confirm_action"))},confirmButton={TextButton(onClick={confirmation=null;action()}){Text(label("confirm"))}},dismissButton={TextButton(onClick={confirmation=null}){Text(label("back"))}})}
        if(onboarding)AlertDialog(onDismissRequest={onboarding=false;prefs.edit().putBoolean("onboarding_seen",true).apply()},title={Text(label("app_name"))},text={Text(label("onboarding_intro")+"\n\n"+label("privacy_intro"))},confirmButton={TextButton(onClick={onboarding=false;prefs.edit().putBoolean("onboarding_seen",true).apply()}){Text(label("confirm"))}})
    }
}

@Composable private fun LoginScreen(model:AppViewModel,form:(String)->Unit){
    var email by remember{mutableStateOf("")};var password by remember{mutableStateOf("")}
    Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(14.dp)){
        OutlinedTextField(email,{email=it},label={Text(label("email"))},keyboardOptions=KeyboardOptions(keyboardType=KeyboardType.Email))
        OutlinedTextField(password,{password=it},label={Text(label("password"))},visualTransformation=PasswordVisualTransformation(),keyboardOptions=KeyboardOptions(keyboardType=KeyboardType.Password))
        Button(onClick={model.login(email,password)}){Text(label("login"))}
        TextButton(onClick={form("signup")}){Text(label("signup"))};TextButton(onClick={form("forgot")}){Text(label("forgot"))}
    }
}

@Composable private fun FilterBar(model:AppViewModel,kind:String){
    var expanded by remember(kind){mutableStateOf(false)}
    var query by remember(kind){mutableStateOf("")};var archive by remember(kind){mutableStateOf(false)};var open by remember(kind){mutableStateOf(false)}
    var country by remember(kind){mutableStateOf("")};var city by remember(kind){mutableStateOf("")};var category by remember(kind){mutableStateOf("")};var sort by remember(kind){mutableStateOf(if(kind=="events")"date" else "name")};var currency by remember(kind){mutableStateOf("")}
    val options=remember{mutableStateMapOf<String,List<Pair<String,String>>>()}
    val context=LocalContext.current
    LaunchedEffect(kind){for(key in listOf("countries","categories","currencies"))runCatching{options[key]=rows(model.lookup("$key/")).map{it.getLong("id").toString() to it.optString(if(context.resources.configuration.locales[0].language=="ar")"name_ar" else "name_en")}}}
    Column(verticalArrangement=Arrangement.spacedBy(8.dp)){
        OutlinedTextField(query,{query=it},label={Text(label("search"))},modifier=Modifier.fillMaxWidth(),shape=RoundedCornerShape(28.dp),singleLine=true)
        TextButton(onClick={expanded=!expanded}){Text(label(if(expanded)"hide_filters" else "advanced_filters"))}
        if(expanded){
        Selection(label("country_id"),country,listOf("" to label("all"))+options["countries"].orEmpty()){country=it;city=""}
        ReferencePicker(model,label("city_id"),city,"cities/"+(if(country.isBlank())"" else "?country=$country"),true){city=it}
        Selection(label("category_ids"),category,listOf("" to label("all"))+options["categories"].orEmpty()){category=it}
        Selection(label("sort"),sort,(if(kind=="events")listOf("date","name")else listOf("name","price")).map{it to label(it)}){sort=it}
        if(kind=="services"){
            Row{Checkbox(open,{open=it});Text(label("open_now"))}
            Selection(label("currency_id"),currency,listOf("" to label("none"))+options["currencies"].orEmpty()){currency=it}
        }else Row{Checkbox(archive,{archive=it});Text(label("archive"))}
        }
        Button(modifier=Modifier.fillMaxWidth(),onClick={
            val params=Uri.Builder().appendQueryParameter("q",query).appendQueryParameter("sort",sort)
            if(country.isNotBlank())params.appendQueryParameter("country",country)
            if(city.isNotBlank())params.appendQueryParameter("city",city)
            if(category.isNotBlank())params.appendQueryParameter("category",category)
            if(currency.isNotBlank())params.appendQueryParameter("currency",currency)
            if(archive)params.appendQueryParameter("archive","true")
            if(open)params.appendQueryParameter("open_now","true")
            model.open(Screen("$kind/?"+params.build().encodedQuery,kind))
        }){Text(label("apply_filters"))}
    }
}

fun formatTime(context:Context,value:String):String = runCatching{
    val date=OffsetDateTime.parse(value)
    val hijri=context.getSharedPreferences("display",Context.MODE_PRIVATE).getBoolean("hijri",false)
    val formatter=DateTimeFormatter.ofPattern("yyyy/MM/dd HH:mm",context.resources.configuration.locales[0]).withDecimalStyle(java.time.format.DecimalStyle.of(android.content.res.Resources.getSystem().configuration.locales[0]))
    if(hijri)formatter.withChronology(java.time.chrono.HijrahChronology.INSTANCE).format(date) else formatter.format(date)
}.getOrDefault(value)

@Composable private fun FollowsScreen(model:AppViewModel,state:UiState,confirm:(String,()->Unit)->Unit){
    val context=LocalContext.current
    val data=state.data as? JSONObject
    var followed by remember(data){mutableStateOf(emptyList<Triple<String,Long,String>>())}
    LaunchedEffect(data){
        val result=mutableListOf<Triple<String,Long,String>>()
        val categories=runCatching{rows(model.lookup("categories/"))}.getOrDefault(emptyList())
        for(kind in listOf("organizer","category")){
            val ids=data?.optJSONArray("${kind}_ids")?:JSONArray()
            for(index in 0 until ids.length()){
                val id=ids.optLong(index)
                val name=if(kind=="organizer")runCatching{(model.lookup("organizers/$id/") as JSONObject).optString("name")}.getOrDefault(context.getString(R.string.organizer))
                    else categories.firstOrNull{it.optLong("id")==id}?.optString(if(context.resources.configuration.locales[0].language=="ar")"name_ar"else"name_en")?:context.getString(R.string.categories)
                result+=Triple(kind,id,name)
            }
        }
        followed=result
    }
    LazyColumn(Modifier.padding(16.dp)) {
        items(followed) { (kind, id, name) ->
            Row {
                Text(name, Modifier.weight(1f))
                val caption = label("unfollow")
                val collection = if (kind == "category") "categories" else "organizers"
                TextButton(onClick = {
                    confirm(caption) { model.act("me/follows/$collection/$id/", "DELETE") }
                }) {
                    Text(caption)
                }
            }
        }
    }
}
