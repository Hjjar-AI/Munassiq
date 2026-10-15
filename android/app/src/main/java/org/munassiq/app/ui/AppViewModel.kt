package org.munassiq.app.ui

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONArray
import org.json.JSONObject
import org.munassiq.app.MunassiqApplication
import org.munassiq.app.data.ApiFailure
import org.munassiq.app.data.Repository
import java.time.ZoneId

data class Screen(val path: String, val title: String, val kind: String = "list", val extra: JSONObject = JSONObject())
data class UiState(val screen: Screen = Screen("events/?sort=date", "events"), val data: Any = JSONObject(),
    val busy: Boolean = false, val offline: Boolean = false, val error: String? = null, val message: String? = null,
    val user: JSONObject? = null)

class AppViewModel(application: Application) : AndroidViewModel(application) {
    val repository: Repository = (application as MunassiqApplication).repository
    private val mutable = MutableStateFlow(UiState(user = repository.user()))
    val state = mutable.asStateFlow()
    private var pending: Job? = null
    private val history = mutableListOf<Screen>()
    init { refresh() }
    fun open(screen: Screen) {
        history.add(mutable.value.screen)
        pending?.cancel()
        mutable.value = mutable.value.copy(screen = screen, data = JSONObject(), error = null, message = null)
        refresh()
    }
    fun back() {
        if (history.isNotEmpty()) { mutable.value = mutable.value.copy(screen = history.removeAt(history.lastIndex)); refresh() }
    }
    fun refresh() {
        pending?.cancel()
        val screen = mutable.value.screen
        if (screen.kind in listOf("login", "settings", "editor")) return
        pending = viewModelScope.launch {
            mutable.value = mutable.value.copy(busy = true, error = null)
            try {
                val loaded = repository.load(screen.path)
                mutable.value = mutable.value.copy(data = loaded.value, offline = loaded.offline, user = repository.user())
            } catch (error: Exception) { failure(error) }
            finally { mutable.value = mutable.value.copy(busy = false) }
        }
    }
    private fun failure(error: Exception) {
        if (error is kotlinx.coroutines.CancellationException) throw error
        val message = if (error is ApiFailure) {
            if (error.status == 401) "session_expired" else error.detail.ifBlank { "request_failed" }
        } else "connection_failed"
        mutable.value = mutable.value.copy(error = message, user = repository.user())
    }
    fun login(email: String, password: String) = viewModelScope.launch {
        mutable.value = mutable.value.copy(busy = true, error = null)
        try {
            repository.signIn(email, password)
            val display=getApplication<Application>().getSharedPreferences("display",android.content.Context.MODE_PRIVATE)
            val selected=display.getString("language","system")
            val phone=android.content.res.Resources.getSystem().configuration.locales[0].language
            val language=if(selected in listOf("ar","en"))selected else if(phone=="en")"en"else"ar"
            runCatching{repository.mutate("me/notification-preferences/","PATCH",JSONObject().put("language",language).put("time_zone",ZoneId.systemDefault().id))}
            org.munassiq.app.notifications.DeviceSync.enqueue(getApplication())
            history.clear(); mutable.value = UiState(user = repository.user()); refresh()
        } catch (error: Exception) { failure(error) }
        finally { mutable.value = mutable.value.copy(busy = false) }
    }
    fun logout(all: Boolean) {
        pending?.cancel()
        viewModelScope.launch {
            val remote = repository.signOut(all)
            history.clear(); mutable.value = UiState(message = if (remote) "signed_out" else "local_signout_only")
            refresh()
        }
    }
    fun act(path: String, method: String = "POST", body: JSONObject = JSONObject(), after: (() -> Unit)? = null) = viewModelScope.launch {
        mutable.value = mutable.value.copy(busy = true, error = null, message = null)
        try {
            val result = repository.mutate(path, method, body)
            val overlapping = if (result is JSONArray) (0 until result.length()).any { result.optJSONObject(it)?.optBoolean("overlap_warning") == true } else (result as? JSONObject)?.optBoolean("overlap_warning") == true
            mutable.value = mutable.value.copy(message = if (overlapping) "overlap_warning" else "saved")
            after?.invoke()
            refresh()
        } catch (error: Exception) { failure(error) }
        finally { mutable.value = mutable.value.copy(busy = false) }
    }
    fun navigateLink(uri: Uri?) {
        if (uri == null) return
        val server = Uri.parse(org.munassiq.app.BuildConfig.SERVER_ORIGIN)
        if (uri.scheme == "https" && uri.host == server.host) {
            val parts = uri.pathSegments
            if (parts.size == 2 && parts[0] == "events" && parts[1].toLongOrNull() != null)
                open(Screen("events/${parts[1]}/?time_zone=${Uri.encode(ZoneId.systemDefault().id)}", "events", "detail"))
        } else if (uri.scheme == "munassiq" && uri.host in listOf("events", "services", "occurrences")) {
            val id = uri.pathSegments.firstOrNull()?.toLongOrNull() ?: return
            open(Screen("${uri.host}/$id/?time_zone=${Uri.encode(ZoneId.systemDefault().id)}", "events", if (uri.host == "occurrences") "occurrence" else "detail"))
        }
    }
    suspend fun lookup(path: String): Any = repository.api.request(path)
    fun showError(error: Exception) { failure(error) }
}
