package org.munassiq.app.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONObject
import org.json.JSONTokener
import org.munassiq.app.BuildConfig
import java.io.IOException
import java.net.URL
import javax.net.ssl.HttpsURLConnection

class ApiFailure(val status: Int, val detail: String) : Exception("HTTP $status")

class ApiClient(private val vault: SessionVault) {
    private val refreshLock = Mutex()
    private val cookies = java.net.CookieManager(null, java.net.CookiePolicy.ACCEPT_ORIGINAL_SERVER)
    private fun connection(path: String, method: String, token: String?): HttpsURLConnection {
        check(!BuildConfig.IS_VALIDATION) { "Validation build has no configured server" }
        require(!path.startsWith('/') && !path.contains("://") && !path.contains(".."))
        val connection = URL(BuildConfig.SERVER_ORIGIN + "/api/v1/" + path).openConnection() as HttpsURLConnection
        connection.requestMethod = method
        connection.instanceFollowRedirects = false // Never forward a bearer token to another origin.
        connection.connectTimeout = 12000
        connection.readTimeout = 15000
        connection.setRequestProperty("Accept", "application/json")
        cookies.get(connection.url.toURI(), emptyMap()).forEach { (name, values) -> connection.setRequestProperty(name, values.joinToString("; ")) }
        token?.takeIf { it.isNotBlank() }?.let { connection.setRequestProperty("Authorization", "Bearer $it") }
        return connection
    }
    private fun raw(path: String, method: String, body: JSONObject?, token: String?): Any {
        val connection = connection(path, method, token)
        return try {
            if (body != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            }
            val status = connection.responseCode
            cookies.put(connection.url.toURI(), connection.headerFields)
            val bytes = (if (status in 200..299) connection.inputStream else connection.errorStream)?.use { it.readBytes() } ?: byteArrayOf()
            val text = bytes.toString(Charsets.UTF_8)
            if (status !in 200..299) throw ApiFailure(status, text.take(8000))
            if (text.isBlank()) JSONObject() else JSONTokener(text).nextValue()
        } finally { connection.disconnect() }
    }
    private suspend fun refresh(oldAccess: String?) = refreshLock.withLock {
        val current = vault.read() ?: throw ApiFailure(401, "")
        if (current.optString("access_token") != oldAccess) return@withLock
        try {
            val result = raw("auth/refresh/", "POST", JSONObject().put("refresh_token", current.getString("refresh_token")), null) as JSONObject
            vault.save(result)
        } catch (error: ApiFailure) {
            if (error.status == 401 || error.status == 403) vault.clear()
            throw error
        }
    }
    suspend fun request(path: String, method: String = "GET", body: JSONObject? = null, authenticated: Boolean = true): Any = withContext(Dispatchers.IO) {
        val access = if (authenticated) vault.read()?.optString("access_token") else null
        try { raw(path, method, body, access) }
        catch (error: ApiFailure) {
            if (error.status != 401 || access == null) throw error
            refresh(access)
            raw(path, method, body, vault.read()?.getString("access_token"))
        }
    }
    suspend fun upload(path: String, bytes: ByteArray, fields: JSONObject = JSONObject(), fieldName: String = "file"): JSONObject = withContext(Dispatchers.IO) {
        require(bytes.size in 1..5 * 1024 * 1024)
        // Refresh before streaming: a consumed upload must never be retried blindly.
        request("me/")
        val connection = connection(path, "POST", vault.read()?.getString("access_token"))
        val boundary = "Munassiq" + java.util.UUID.randomUUID()
        try {
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
            connection.outputStream.use {
                fields.keys().forEach { key ->
                    require(key.matches(Regex("[a-z_]+")))
                    it.write("--$boundary\r\nContent-Disposition: form-data; name=\"$key\"\r\n\r\n${fields.get(key)}\r\n".toByteArray(Charsets.UTF_8))
                }
                require(fieldName in listOf("file", "credential"))
                it.write("--$boundary\r\nContent-Disposition: form-data; name=\"$fieldName\"; filename=\"upload\"\r\nContent-Type: application/octet-stream\r\n\r\n".toByteArray())
                it.write(bytes); it.write("\r\n--$boundary--\r\n".toByteArray())
            }
            val status = connection.responseCode
            val text = (if (status in 200..299) connection.inputStream else connection.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
            if (status !in 200..299) throw ApiFailure(status, text.take(8000))
            JSONObject(text)
        } finally { connection.disconnect() }
    }
    suspend fun download(path: String): ByteArray = withContext(Dispatchers.IO) {
        if (vault.read() != null) request("me/")
        val connection = connection(path, "GET", vault.read()?.optString("access_token"))
        try {
            if (connection.responseCode !in 200..299) throw ApiFailure(connection.responseCode, "")
            connection.inputStream.use { stream ->
                val output = java.io.ByteArrayOutputStream()
                val buffer = ByteArray(8192)
                while (true) { val count = stream.read(buffer); if (count < 0) break; output.write(buffer, 0, count); if (output.size() > 20 * 1024 * 1024) throw IOException("Download limit") }
                output.toByteArray()
            }
        } finally { connection.disconnect() }
    }
}
