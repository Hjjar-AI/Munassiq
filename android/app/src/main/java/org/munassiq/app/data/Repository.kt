package org.munassiq.app.data

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import org.json.JSONTokener
import java.io.IOException

data class Loaded(val value: Any, val offline: Boolean)

class Repository(val context: Context, val api: ApiClient, val vault: SessionVault, private val cache: CacheDao) {
    fun user(): JSONObject? = vault.read()?.optJSONObject("user")
    private fun scope() = user()?.optLong("id")?.toString() ?: "guest"
    private fun cacheable(path: String) = listOf("events/", "services/", "map/services/", "search/", "categories/", "countries/", "cities/", "currencies/", "organizers/", "occurrences/", "me/items/", "me/registrations/", "me/follows/", "me/notification-preferences/").any { path.startsWith(it) }
    suspend fun load(path: String): Loaded {
        val owner = scope()
        try {
            val value = api.request(path)
            if (cacheable(path)) { cache.put(CachedResponse(owner, path, value.toString(), System.currentTimeMillis())); cache.expire(System.currentTimeMillis() - 7 * 86400000L); cache.trim() }
            return Loaded(value, false)
        } catch (error: IOException) {
            if (cacheable(path)) cache.read(owner, path)?.let {
                if(it.savedAt >= System.currentTimeMillis()-7*86400000L) return Loaded(JSONTokener(it.body).nextValue(), true)
            }
            throw error
        } catch (error: ApiFailure) {
            if (vault.read() == null) cache.clear()
            throw error
        }
    }
    suspend fun signIn(email: String, password: String) {
        val response = api.request("auth/login/", "POST", JSONObject().put("email", email).put("password", password), false) as JSONObject
        cache.clear(); vault.save(response)
    }
    suspend fun signOut(all: Boolean = false): Boolean {
        var remote = true
        try { api.request(if (all) "auth/logout-all/" else "auth/logout/", "POST", JSONObject()) }
        catch (_: Exception) { remote = false }
        finally { clearLocal() }
        return remote
    }
    suspend fun clearLocal() = withContext(Dispatchers.IO) {
        vault.clear(); cache.clear(); context.cacheDir.resolve("exports").deleteRecursively()
        androidx.core.app.NotificationManagerCompat.from(context).cancelAll()
    }
    suspend fun mutate(path: String, method: String, body: JSONObject = JSONObject()): Any {
        val result = api.request(path, method, body)
        if (path == "me/" && method == "PATCH" && result is JSONObject) {
            vault.read()?.let { vault.save(it.put("user", result)) }
        }
        if (path == "me/notification-preferences/" && body.has("language")) {
            vault.read()?.let { session -> session.optJSONObject("user")?.put("language", body.getString("language")); vault.save(session) }
        }
        cache.clear() // Ensure a mutation never leaves stale roster/private state on disk.
        return result
    }
}
