package org.munassiq.app.ui

import android.net.Uri
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import org.json.JSONObject

/** Uses the actual API page contract, including city X-Next-Page adapted by ApiClient. */
@Composable fun ReferencePicker(model: AppViewModel, caption: String, value: String, path: String,
    optional: Boolean = false, onSelect: (String) -> Unit) {
    val context = LocalContext.current
    val selectedLabels = remember(path) { mutableStateMapOf<String,String>() }
    var query by remember(path) { mutableStateOf("") }
    var entries by remember(path, query) { mutableStateOf(emptyList<JSONObject>()) }
    var page by remember(path, query) { mutableIntStateOf(1) }
    var next by remember(path, query) { mutableStateOf<Int?>(null) }
    var busy by remember(path, query) { mutableStateOf(false) }
    var error by remember(path, query) { mutableStateOf<String?>(null) }
    var retry by remember { mutableIntStateOf(0) }
    LaunchedEffect(path, query, page, retry) {
        busy = true; error = null
        try {
            delay(300)
            val separator = if ('?' in path) "&" else "?"
            val result = model.lookup(path + separator + "q=${Uri.encode(query)}&page=$page")
            entries = (if (page == 1) rows(result) else entries + rows(result)).distinctBy { it.optLong("id") }
            next = (result as? JSONObject)?.optInt("next_page", 0)?.takeIf { it > page }
        } catch (failure: Exception) {
            if (failure is CancellationException) throw failure
            error = localizedError(context, failure)
        } finally { busy = false }
    }
    Column {
        OutlinedTextField(query, { query = it }, label = { Text(label("search") + ": " + caption) }, modifier = Modifier.fillMaxWidth())
        val choices = entries.map { row ->
            row.optLong("id").toString() to (row.optJSONObject("payload")?.optString("name")
                ?: row.optString(if (context.resources.configuration.locales[0].language == "ar") "name_ar" else "name_en"))
        }
        SideEffect { choices.forEach{(id,name)->selectedLabels[id]=name} }
        val selected = if(value.isNotBlank() && choices.none{it.first==value})listOf(value to (selectedLabels[value]?:value)) else emptyList()
        Selection(caption, value, selected + (if (optional) listOf("" to label("none")) else emptyList()) + choices, onSelect)
        if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        error?.let { Text(it); TextButton(onClick = { retry++ }) { Text(label("retry")) } }
        if (next != null) TextButton(enabled = !busy, onClick = { page = next ?: page }) { Text(label("load_more")) }
        if (!busy && error == null && entries.isEmpty()) Text(label("empty"))
    }
}
