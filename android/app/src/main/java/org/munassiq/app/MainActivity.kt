package org.munassiq.app

import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import org.munassiq.app.ui.AppScreen
import org.munassiq.app.ui.AppViewModel
import java.util.Locale

class MainActivity : ComponentActivity() {
    private val model:AppViewModel by viewModels()
    override fun attachBaseContext(base:Context) {
        val stored=base.getSharedPreferences("display",MODE_PRIVATE).getString("language","system")
        val phone=base.resources.configuration.locales[0].language
        val language=if(stored in listOf("ar","en"))stored!! else if(phone=="en")"en" else "ar"
        val configuration=Configuration(base.resources.configuration).apply{setLocale(Locale.forLanguageTag(language));setLayoutDirection(Locale.forLanguageTag(language))}
        super.attachBaseContext(base.createConfigurationContext(configuration))
    }
    override fun onCreate(savedInstanceState:Bundle?){super.onCreate(savedInstanceState);setContent{AppScreen(model)};if(savedInstanceState==null)model.navigateLink(intent.data)}
    override fun onNewIntent(intent:Intent){super.onNewIntent(intent);setIntent(intent);model.navigateLink(intent.data)}
    override fun onResume(){super.onResume();model.refresh()}
}
