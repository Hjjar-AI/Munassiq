package org.munassiq.app.ui

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId

fun rows(value: Any?): List<JSONObject> {
    val array=if(value is JSONArray)value else (value as? JSONObject)?.optJSONArray("results") ?: JSONArray()
    return (0 until array.length()).mapNotNull{array.optJSONObject(it)}
}

@Composable fun label(key: String): String {
    val context=LocalContext.current
    val resource=context.resources.getIdentifier(key,"string",context.packageName)
    return if(resource!=0)context.getString(resource) else context.getString(org.munassiq.app.R.string.details)
}

@Composable fun Selection(caption: String,value: String,choices: List<Pair<String,String>>,onSelect:(String)->Unit) {
    var expanded by remember{mutableStateOf(false)}
    Column {
        Text(caption,style=MaterialTheme.typography.labelLarge)
        OutlinedButton(onClick={expanded=true}){Text(choices.firstOrNull{it.first==value}?.second ?: if(value.isNotBlank()) value else label("choose"))}
        DropdownMenu(expanded=expanded,onDismissRequest={expanded=false}) {
            choices.forEach{(key,title)->DropdownMenuItem(text={Text(title)},onClick={onSelect(key);expanded=false})}
        }
    }
}

@Composable fun FormsScreen(model: AppViewModel,spec: FormSpec,done:()->Unit) {
    val context=LocalContext.current
    val scope=rememberCoroutineScope()
    val values=remember(spec){mutableStateMapOf<String,String>().apply{
        spec.fields.forEach{field->put(field.key,if(spec.initial.has(field.key)&&!spec.initial.isNull(field.key))spec.initial.opt(field.key)?.toString().orEmpty() else when(field.key){
            "time_zone"->ZoneId.systemDefault().id; "duration_minutes"->"60";"seat_limit"->"20";"occurrence_count"->"1";"cancellation_cutoff_minutes"->"60";"language"->context.resources.configuration.locales[0].language
            else->if(field.type=="choice")field.choices.firstOrNull().orEmpty() else ""
        })}
    }}
    var policy by remember(spec){mutableStateOf<JSONObject?>(null)}
    var pendingUpload by remember{mutableStateOf<Field?>(null)}
    var credential by remember{mutableStateOf<ByteArray?>(null)}
    var error by remember{mutableStateOf<String?>(null)}
    var working by remember{mutableStateOf(false)}
    var duplicateConfirm by remember{mutableStateOf(false)}
    var showDuplicate by remember{mutableStateOf(false)}
    val choices=remember(spec){mutableStateMapOf<String,List<Pair<String,String>>>()}
    LaunchedEffect(spec){
        try {
            if(spec.title=="signup")policy=model.lookup("policies/current/") as JSONObject
            for(field in spec.fields.filter{it.type in listOf("countries","categories","currencies")}){
                val result=model.lookup(field.type+"/")
                choices[field.key]=rows(result).map{row-> row.getLong("id").toString() to (row.optJSONObject("payload")?.optString("name") ?: row.optString(if(context.resources.configuration.locales[0].language=="ar")"name_ar" else "name_en"))}
            }
        }catch(exception:Exception){error=localizedError(context,exception)}
    }
    val filePicker=rememberLauncherForActivityResult(ActivityResultContracts.GetContent()){uri:Uri?->
        val field=pendingUpload
        if(uri!=null&&field!=null)scope.launch{
            working=true
            try {
                val bytes=withContext(Dispatchers.IO){context.contentResolver.openInputStream(uri)?.use { stream->
                    val buffer=java.io.ByteArrayOutputStream();val block=ByteArray(8192)
                    while(true){val count=stream.read(block);if(count<0)break;buffer.write(block,0,count);if(buffer.size()>5*1024*1024)throw InputProblem(context.getString(org.munassiq.app.R.string.file_limit_error))}
                    buffer.toByteArray()
                }?:throw InputProblem(context.getString(org.munassiq.app.R.string.attachment_unreadable))}
                if(field.type=="credential")credential=bytes
                else {
                    val uploaded=model.repository.api.upload(if(field.type=="pdf")"uploads/event-pdfs/" else "uploads/images/",bytes)
                    if(field.type=="images"){
                        val ids=runCatching{JSONArray(values[field.key].orEmpty())}.getOrDefault(JSONArray())
                        ids.put(uploaded.getLong("id"));values[field.key]=ids.toString()
                    }else values[field.key]=uploaded.getLong("id").toString()
                }
            }catch(exception:Exception){error=localizedError(context,exception)}
            finally{working=false}
        }
    }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),verticalArrangement=Arrangement.spacedBy(14.dp)){
        policy?.let{row->Text(row.optString(if(context.resources.configuration.locales[0].language=="ar")"terms_ar" else "terms_en"));Text(row.optString(if(context.resources.configuration.locales[0].language=="ar")"privacy_ar" else "privacy_en"))}
        error?.let{Text(it,color=MaterialTheme.colorScheme.error,modifier=Modifier.semantics{liveRegion=LiveRegionMode.Polite})}
        for(field in spec.fields){
            val caption=label(field.key)
            when(field.type){
                "boolean"->Row{Checkbox(checked=values[field.key]=="true",onCheckedChange={values[field.key]=it.toString()});Text(caption)}
                "choice"->Selection(caption,values[field.key].orEmpty(),field.choices.map{it to label(it)}){values[field.key]=it}
                "countries","currencies"->Selection(caption,values[field.key].orEmpty(),(if(field.optional)listOf("" to label("none")) else emptyList())+choices[field.key].orEmpty()){values[field.key]=it;if(field.type=="countries")values["city_id"]=""}
                "categories"->{
                    Text(caption)
                    val selected=runCatching{JSONArray(values[field.key].orEmpty())}.getOrDefault(JSONArray())
                    val ids=(0 until selected.length()).map{selected.getString(it)}.toSet()
                    choices[field.key].orEmpty().forEach{(id,title)->Row{Checkbox(id in ids,{checked->values[field.key]=JSONArray(if(checked)ids+id else ids-id).toString()});Text(title)}}
                }
                "cities"->ReferencePicker(model,caption,values[field.key].orEmpty(),"cities/"+(values["country_id"]?.takeIf{it.isNotBlank()}?.let{"?country=$it"}?:""),field.optional){values[field.key]=it}
                "services"->ReferencePicker(model,caption,values[field.key].orEmpty(),"services/",field.optional){values[field.key]=it}
                "date"->DateTimeEntry(caption,values[field.key].orEmpty(),values["time_zone"]?:ZoneId.systemDefault().id){values[field.key]=it}
                "image","images","pdf","credential"->{
                    Text(caption)
                    val count=if(field.type=="images")runCatching{JSONArray(values[field.key].orEmpty()).length()}.getOrDefault(0) else if(field.type=="credential"&&credential!=null)1 else if(values[field.key].isNullOrBlank())0 else 1
                    Text(count.toString()+" · "+label("attachments"))
                    if(field.type in listOf("images","image")) {
                        val photoIds=if(field.type=="images")runCatching{val array=JSONArray(values[field.key].orEmpty());(0 until array.length()).map{array.getLong(it)}}.getOrDefault(emptyList()) else listOfNotNull(values[field.key]?.toLongOrNull())
                        PhotoGallery(model,photoIds){removed->values[field.key]=if(field.type=="images")JSONArray(photoIds.filter{it!=removed}).toString() else ""}
                    }
                    Row{OutlinedButton(enabled=!working&&(field.type!="images"||count<(if(spec.path.startsWith("events/"))3 else 5)),onClick={pendingUpload=field;filePicker.launch(if(field.type=="pdf")"application/pdf" else if(field.type=="credential")"*/*" else "image/*")}){Text(label("choose_file"))}
                        TextButton(onClick={values[field.key]=if(field.type=="images")"[]" else "";if(field.type=="credential")credential=null}){Text(label("remove"))}}
                }
                "text"->if(field.key in listOf("quiet_start","quiet_end"))TimeEntry(caption,values[field.key].orEmpty()){values[field.key]=it}
                    else OutlinedTextField(values[field.key].orEmpty(),{values[field.key]=it},label={Text(caption)},modifier=Modifier.fillMaxWidth(),keyboardOptions=KeyboardOptions(keyboardType=when(field.key){"email"->KeyboardType.Email;"phone"->KeyboardType.Phone;else->KeyboardType.Text}))
                "hours"->HoursEditor(values[field.key].orEmpty()){values[field.key]=it}
                else->OutlinedTextField(values[field.key].orEmpty(),{values[field.key]=it},label={Text(caption)},modifier=Modifier.fillMaxWidth(),
                    keyboardOptions=KeyboardOptions(keyboardType=when{field.type=="password"->KeyboardType.Password;field.type=="number"->KeyboardType.Decimal;field.key=="email"->KeyboardType.Email;field.key=="phone"->KeyboardType.Phone;else->KeyboardType.Text}),
                    visualTransformation=if(field.type=="password")PasswordVisualTransformation() else VisualTransformation.None,
                    supportingText={if(field.type=="date")Text(label("date_hint"))},minLines=if(field.type=="long")3 else 1)
            }
        }
        if(spec.fields.any{it.key=="latitude"}){
            Text(label("pick_place"))
            MapScreen(model,picker=true,initialLatitude=spec.initial.optDouble("latitude").takeIf{it.isFinite()},initialLongitude=spec.initial.optDouble("longitude").takeIf{it.isFinite()},onPick={lat,lon->values["latitude"]=lat.toString();values["longitude"]=lon.toString()})
        }
        if(showDuplicate)Row{Checkbox(duplicateConfirm,{duplicateConfirm=it});Text(label("confirm_duplicate"))}
        val missing=label("check_required")
        Button(enabled=!working,onClick={scope.launch{
            working=true;error=null
            try{
                val body=JSONObject()
                for(field in spec.fields){
                    val rawValue=values[field.key].orEmpty()
                    val value=if(field.type in listOf("number","date")||field.key in listOf("phone","quiet_start","quiet_end"))normalizedInput(rawValue) else rawValue
                    if(field.type=="credential")continue
                    if(value.isBlank()&&!field.optional&&field.type !in listOf("images","image","pdf","boolean"))throw InputProblem(missing)
                    if(value.isBlank()&&field.type in listOf("images","hours")){body.put(field.key,JSONArray());continue}
                    if(value.isBlank()&&field.optional){if(field.key !in listOf("phone","contact_person","bio","description","registration_contact","registration_url","address","online_url"))body.put(field.key,JSONObject.NULL) else body.put(field.key,"");continue}
                    try {
                    body.put(field.key,when(field.type){
                        "boolean"->value=="true"
                        "categories","images","hours"->runCatching{JSONArray(value)}.getOrDefault(JSONArray())
                        "countries","cities","services","currencies","image","pdf"->if(value.isBlank())JSONObject.NULL else value.toLong()
                        "number"->{val number=normalizedInput(value);if(field.key=="price"){val price=number.toBigDecimal();require(price.signum()>=0);price.toPlainString()}else if(field.key in listOf("latitude","longitude")){val parsed=number.toDouble();require(parsed.isFinite());parsed}else number.toInt()}
                        "date"->{val zone=ZoneId.of(values["time_zone"]?:"UTC");runCatching{OffsetDateTime.parse(value).toString()}.getOrElse{val date=LocalDateTime.parse(value.replace(' ','T'));if(zone.rules.getValidOffsets(date).size!=1)throw java.time.DateTimeException("Ambiguous or nonexistent local time");date.atZone(zone).toOffsetDateTime().toString()}}
                        else->if(field.key in listOf("quiet_start","quiet_end")&&value.isNotBlank())java.time.LocalTime.parse(value).toString() else value
                    })
                    } catch(failure:Exception) {
                        val resource=context.resources.getIdentifier(field.key,"string",context.packageName)
                        val caption=if(resource!=0)context.getString(resource) else context.getString(org.munassiq.app.R.string.details)
                        throw InputProblem(caption+": "+localizedError(context,failure))
                    }
                }
                if(spec.title=="signup"){if(!body.optBoolean("consent"))throw InputProblem(missing);body.put("policy_id",policy?.getLong("id")?:throw InputProblem(missing))}
                if(spec.title=="delete_account"){if(!body.optBoolean("confirm"))throw InputProblem(missing);body.remove("confirm")}
                if(spec.title=="report")body.put("item_id",spec.initial.getLong("item_id"))
                if(spec.path=="services/"&&!duplicateConfirm){
                    val check=model.lookupDuplicate(body.getString("name"))
                    if(check){showDuplicate=true;throw InputProblem(context.getString(org.munassiq.app.R.string.confirm_duplicate))}
                }
                val response=if(spec.title=="apply")model.repository.api.upload(spec.path,credential?:throw InputProblem(missing),body,"credential")
                    else model.repository.mutate(spec.path,spec.method,body)
                if(spec.title=="signup")model.repository.vault.save(response as JSONObject)
                if(spec.title=="signup")org.munassiq.app.notifications.DeviceSync.enqueue(context)
                if(spec.title in listOf("delete_account","password"))model.repository.clearLocal()
                if(body.optString("language") in listOf("ar","en")){
                    context.getSharedPreferences("display",android.content.Context.MODE_PRIVATE).edit().putString("language",body.getString("language")).apply()
                }
                done()
                if(body.optString("language") in listOf("ar","en"))(context as? android.app.Activity)?.recreate()
            }catch(exception:Exception){error=localizedError(context,exception)}
            finally{working=false}
        }}){Text(label("save"))}
    }
}

private suspend fun AppViewModel.lookupDuplicate(name:String)= (repository.api.request("services/duplicate-check/","POST",JSONObject().put("name",name)) as JSONObject).optBoolean("similar_name_exists")

@Composable private fun HoursEditor(raw:String,onChange:(String)->Unit){
    val values=runCatching{JSONArray(raw)}.getOrDefault(JSONArray())
    Text(label("hours"))
    for(index in 0 until values.length()){
        val row=values.getJSONObject(index)
        Column {
            Selection(label("day"),row.optInt("day").toString(),(0..6).map{it.toString() to label("weekday_$it")}){day->row.put("day",day.toInt());onChange(values.toString())}
            TimeEntry(label("from"),row.optString("start")){row.put("start",normalizedInput(it));onChange(values.toString())}
            TimeEntry(label("until"),row.optString("end")){row.put("end",normalizedInput(it));onChange(values.toString())}
            TextButton(onClick={values.remove(index);onChange(values.toString())}){Text(label("remove"))}
        }
    }
    OutlinedButton(onClick={values.put(JSONObject().put("day",0).put("start","09:00").put("end","17:00"));onChange(values.toString())}){Text(label("add_hours"))}
}
