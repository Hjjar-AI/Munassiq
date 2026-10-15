package org.munassiq.app.ui

import android.app.Activity
import android.content.Context
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import org.munassiq.app.BuildConfig

@Composable fun SettingsScreen(model:AppViewModel,edit:(FormSpec)->Unit){
    val context=LocalContext.current;val scope=rememberCoroutineScope();val user=model.repository.user()
    val prefs=remember{context.getSharedPreferences("display",Context.MODE_PRIVATE)}
    var settings by remember{mutableStateOf<JSONObject?>(null)}
    var hijri by remember{mutableStateOf(prefs.getBoolean("hijri",false))}
    val saveData=rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/json")){uri->if(uri!=null)scope.launch{
        try{val data=model.repository.api.download("me/data-export/");withContext(Dispatchers.IO){context.contentResolver.openOutputStream(uri)?.use{it.write(data)}}}catch(error:Exception){model.showError(error)}
    }}
    LaunchedEffect(Unit){runCatching{settings=model.lookup("app-settings/") as JSONObject}}
    LazyColumn(Modifier.fillMaxSize().padding(16.dp),verticalArrangement=Arrangement.spacedBy(12.dp)){
        item{
            Text(label("privacy_intro"))
            if(user==null){Button(onClick={model.open(Screen("","login","login"))}){Text(label("login"))}}
            else{
                Text(user.optString("name"));Text(user.optString("email"))
                for(operation in listOf("profile","verify","password","email","preferences","apply","organizer_profile","feedback","delete_account")){
                    if(operation=="organizer_profile"&&!user.optJSONArray("roles").toString().contains("organizer"))continue
                    if(operation=="apply"&&user.optJSONArray("roles").toString().contains("organizer"))continue
                    TextButton(onClick={scope.launch{
                        try{
                            val spec=NativeForms.account(operation)
                            val initial=when(operation){
                                "profile"->user
                                "preferences"->model.repository.load("me/notification-preferences/").value as JSONObject
                                "organizer_profile"->model.repository.load("organizers/${user.optLong("id")}/").value as JSONObject
                                else->JSONObject()
                            }
                            edit(spec.copy(initial=initial))
                        }catch(error:Exception){model.showError(error)}
                    }}){Text(label(operation))}
                }
                TextButton(onClick={saveData.launch("munassiq-account.json")}){Text(label("data_export"))}
                TextButton(onClick={model.open(Screen("me/organizer-requests/","requests"))}){Text(label("requests"))}
                TextButton(onClick={model.open(Screen("me/follows/","follows","follows"))}){Text(label("follows"))}
                TextButton(onClick={model.logout(false)}){Text(label("logout"))}
                TextButton(onClick={model.logout(true)}){Text(label("logout_all"))}
            }
            Selection(label("language"),prefs.getString("language","system").orEmpty(),listOf("system" to label("system"),"ar" to "العربية","en" to "English")){value->scope.launch{
                try{
                    val phone=android.content.res.Resources.getSystem().configuration.locales[0].language
                    val locale=if(value=="system")if(phone=="en")"en"else"ar"else value
                    if(user!=null)model.repository.mutate("me/notification-preferences/","PATCH",JSONObject().put("language",locale).put("time_zone",java.time.ZoneId.systemDefault().id))
                    prefs.edit().putString("language",value).apply();(context as? Activity)?.recreate()
                }catch(error:Exception){model.showError(error)}
            }}
            Selection(label("theme"),prefs.getString("theme","system").orEmpty(),listOf("system","light","dark").map{it to label(it)}){value->prefs.edit().putString("theme",value).apply();(context as? Activity)?.recreate()}
            Row{Checkbox(hijri,{hijri=it;prefs.edit().putBoolean("hijri",it).apply()});Text(label("hijri"))}
            TextButton(onClick={model.open(Screen("policies/current/","policies","policies"))}){Text(label("policies"))}
            settings?.let{value->
                if(value.optInt("apk_version_code")>BuildConfig.VERSION_CODE&&value.optString("apk_download_url").startsWith("https://")){
                    Text(label("update_available"));Text(label("install_help"))
                    OutlinedButton(onClick={DeviceActions.external(context,Uri.parse(value.getString("apk_download_url")))}){Text(label("download_update"))}
                }
            }
            TextButton(onClick={DeviceActions.external(context,Uri.parse(BuildConfig.SERVER_ORIGIN+"/dashboard/"))}){Text(label("dashboard"))}
            Text("GeoNames · CC BY 4.0\n© OpenStreetMap contributors",style=MaterialTheme.typography.labelSmall)
        }
    }
}
