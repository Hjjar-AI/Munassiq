package org.munassiq.app.ui

import android.net.Uri
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import org.munassiq.app.BuildConfig
import java.time.OffsetDateTime
import java.time.ZoneId

@Composable fun DetailScreen(model:AppViewModel,state:UiState,edit:(FormSpec)->Unit,confirm:(String,()->Unit)->Unit,requestPermission:(()->Unit)->Unit){
    val item=state.data as? JSONObject?:return
    val payload=item.optJSONObject("payload")?:return
    val context=LocalContext.current;val scope=rememberCoroutineScope()
    val kind=item.optString("kind","event");val id=item.optLong("id")
    var linked by remember(id){mutableStateOf(emptyList<JSONObject>())}
    var profile by remember(id){mutableStateOf<JSONObject?>(null)}
    LaunchedEffect(id){
        if(kind=="event")runCatching{model.repository.api.request("events/$id/views/","POST",JSONObject())}
        else runCatching{linked=rows(model.repository.load("services/$id/events/").value)}
        if(!item.isNull("owner_id"))runCatching{profile=model.repository.load("organizers/${item.getLong("owner_id")}/").value as JSONObject}
    }
    LazyColumn(Modifier.fillMaxSize().padding(16.dp),verticalArrangement=Arrangement.spacedBy(12.dp)){
        item{
            Card(colors=CardDefaults.cardColors(containerColor=MaterialTheme.colorScheme.primaryContainer)){
                Column(Modifier.fillMaxWidth().padding(22.dp),verticalArrangement=Arrangement.spacedBy(10.dp)){
                    AppGlyph(if(kind=="event")"events" else "services",Modifier.size(28.dp))
                    Text(payload.optString("title",payload.optString("name")),style=MaterialTheme.typography.headlineSmall)
                }
            }
            Text(payload.optString("description"),style=MaterialTheme.typography.bodyLarge)
            for(key in listOf("speaker_name","topic","address","contact_person","registration_contact"))payload.optString(key).takeIf{it.isNotBlank()}?.let{Text(label(key)+": "+it)}
            if(!payload.isNull("price"))Text(label("price")+": "+payload.optString("price"))
            profile?.let{organizer->Text(organizer.optString("name")+if(organizer.optBoolean("verified"))" · "+label("verified")else "");Text(organizer.optString("bio"))
                if(!organizer.isNull("photo_id"))PhotoGallery(model,listOf(organizer.getLong("photo_id")))
                TextButton(onClick={model.open(Screen("organizers/${organizer.optLong("id")}/events/","events"))}){Text(label("events"))}
                val caption=label("follow");OutlinedButton(onClick={model.act("me/follows/organizers/${organizer.optLong("id")}/","PUT")}){Text(caption)}
                TextButton(onClick={model.act("me/follows/organizers/${organizer.optLong("id")}/","DELETE")}){Text(label("unfollow"))}
            }
            for(key in listOf("online_url","registration_url"))payload.optString(key).takeIf{it.isNotBlank()}?.let{url->TextButton(onClick={DeviceActions.external(context,Uri.parse(url))}){Text(label(key))}}
            payload.optString("phone").takeIf{it.isNotBlank()}?.let{phone->OutlinedButton(onClick={DeviceActions.external(context,Uri.parse("tel:$phone"))}){Text(label("call"))}}
            payload.optString("address").takeIf{it.isNotBlank()}?.let{address->OutlinedButton(onClick={DeviceActions.copy(context,address)}){Text(label("copy_address"))}}
            if(!payload.isNull("latitude")&&!payload.isNull("longitude"))OutlinedButton(onClick={DeviceActions.external(context,Uri.parse("geo:${payload.optDouble("latitude")},${payload.optDouble("longitude")}?q=${payload.optDouble("latitude")},${payload.optDouble("longitude")}"))}){Text(label("directions"))}
            OutlinedButton(onClick={DeviceActions.share(context,payload.optString("title",payload.optString("name")),BuildConfig.SERVER_ORIGIN+"/${kind}s/$id/")}){Text(label("share"))}
            val ids=payload.optJSONArray("image_ids")?:JSONArray()
            PhotoGallery(model, (0 until ids.length()).map { ids.getLong(it) })
            if(!payload.isNull("pdf_id")){val asset=payload.getLong("pdf_id");TextButton(onClick={scope.launch{try{DeviceActions.download(context,model.repository,"files/$asset/","event-$id.pdf","application/pdf")}catch(error:Exception){model.showError(error)}}}){Text(label("download_pdf"))}}
            val report=FormSpec("reports/","POST","report",listOf(Field("reason","choice",listOf("spam","wrong_info","other")),Field("text","long",optional=true)),JSONObject().put("item_id",id))
            TextButton(onClick={edit(report)}){Text(label("report"))}
            if(kind=="event"&&state.user?.optLong("id")==item.optLong("owner_id")){
                val duplicate=FormSpec("events/$id/duplicate/","POST","duplicate",listOf(Field("starts_at","date"),Field("time_zone"),Field("title",optional=true)))
                TextButton(onClick={edit(duplicate)}){Text(label("duplicate"))}
            }
            if(kind=="event"&&!item.isNull("id")){
                val caption=label("series_register");OutlinedButton(onClick={requestPermission{confirm(caption){model.act("series/$id/registrations/")}}}){Text(caption)}
            }
        }
        items(rows(item.optJSONArray("occurrences"))){row->
            Card(Modifier.fillMaxWidth()){Column(Modifier.padding(16.dp)){
                Text(formatTime(context,row.optString("event_local_start"))+" — "+formatTime(context,row.optString("event_local_end")))
                Text(row.optString("time_zone"))
                Text(label("your_local_time")+": "+formatTime(context,OffsetDateTime.parse(row.getString("starts_at")).atZoneSameInstant(ZoneId.systemDefault()).toOffsetDateTime().toString()))
                if(row.optBoolean("archived"))Text(label("archive"))
                if(row.optBoolean("cancelled"))Text(label("cancelled"))
                TextButton(onClick={model.open(Screen("occurrences/${row.getLong("id")}/?time_zone=${Uri.encode(ZoneId.systemDefault().id)}","events","occurrence",JSONObject().put("owner_id",item.optLong("owner_id"))))}){Text(label("open_details"))}
            }}
        }
        items(linked){row->TextButton(onClick={model.open(Screen("events/${row.optLong("id")}/","events","detail"))}){Text(row.optJSONObject("payload")?.optString("title").orEmpty())}}
    }
}

@Composable fun OccurrenceScreen(model:AppViewModel,state:UiState,edit:(FormSpec)->Unit,confirm:(String,()->Unit)->Unit,requestPermission:(()->Unit)->Unit){
    val row=state.data as? JSONObject?:return
    if(!row.has("starts_at"))return
    val context=LocalContext.current;val scope=rememberCoroutineScope();val id=row.optLong("id")
    var roster by remember(id){mutableStateOf<List<JSONObject>?>(null)}
    var stats by remember(id){mutableStateOf<JSONObject?>(null)}
    LaunchedEffect(id,state.user){if(state.user!=null){runCatching{roster=rows(model.lookup("organizer/occurrences/$id/registrants/"))};runCatching{stats=model.lookup("organizer/occurrences/$id/stats/") as JSONObject}}}
    val readonly=row.optBoolean("archived")||row.optBoolean("cancelled")||OffsetDateTime.parse(row.getString("starts_at")).toInstant().isBefore(java.time.Instant.now())
    LazyColumn(Modifier.fillMaxSize().padding(16.dp),verticalArrangement=Arrangement.spacedBy(12.dp)){
        item{
            Text(row.optJSONObject("payload")?.optString("title").orEmpty(),style=MaterialTheme.typography.headlineSmall)
            Text(formatTime(context,row.optString("event_local_start"))+" · "+row.optString("time_zone"))
            Text(label("your_local_time")+": "+formatTime(context,row.optString("user_local_start")))
            OutlinedButton(onClick={DeviceActions.calendar(context,row)}){Text(label("add_calendar"))}
            if(readonly)Text(label("read_only"))else{
                val registration=label("register");Button(onClick={requestPermission{confirm(registration){model.act("occurrences/$id/registration/")}}}){Text(registration)}
                OutlinedButton(onClick={requestPermission{edit(FormSpec("occurrences/$id/reminder/","PUT","reminder",listOf(Field("offset_minutes","number"))))}}){Text(label("reminder"))}
                val remove=label("remove_reminder");TextButton(onClick={confirm(remove){model.act("occurrences/$id/reminder/","DELETE")}}){Text(remove)}
            }
            if(roster!=null){
                if(!readonly){TextButton(onClick={edit(FormSpec("occurrences/$id/reschedule/","POST","reschedule",listOf(Field("starts_at","date"),Field("duration_minutes","number"),Field("time_zone")),JSONObject().put("time_zone",row.getString("time_zone"))))}){Text(label("reschedule"))}
                    val caption=label("cancel_event");TextButton(onClick={confirm(caption){model.act("occurrences/$id/cancel/")}}){Text(caption)}}
                for(format in listOf("csv","pdf","waitlist_csv","waitlist_pdf")){
                    val ext=format.substringAfterLast('_');val path="organizer/occurrences/$id/registrants/export/?format=$ext"+if(format.startsWith("waitlist"))"&state=waitlisted"else ""
                    TextButton(onClick={scope.launch{try{DeviceActions.download(context,model.repository,path,"registrants-$id.$ext",if(ext=="pdf")"application/pdf"else"text/csv")}catch(error:Exception){model.showError(error)}}}){Text(label("export_$format"))}
                }
                stats?.let{value->for(key in listOf("views","registered","waitlisted","pending_reconfirm"))Text(label(key)+": "+value.optInt(key))}
            }
        }
        items(roster.orEmpty()){registration->Card(Modifier.fillMaxWidth()){Column(Modifier.padding(12.dp)){
            Text(registration.optString("name"));Text(registration.optString("email"));Text(label(registration.optString("state")))
            TextButton(onClick={edit(FormSpec("organizer/registrations/${registration.optLong("id")}/remove/","POST","remove_registration",listOf(Field("reason","long"))))}){Text(label("remove_registration"))}
        }}}
    }
}
