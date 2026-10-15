package org.munassiq.app.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.CalendarContract
import androidx.core.content.FileProvider
import org.json.JSONObject
import org.munassiq.app.R
import org.munassiq.app.data.Repository
import java.time.OffsetDateTime

object DeviceActions {
    fun external(context: Context, uri: Uri, mime: String? = null) {
        val intent = Intent(Intent.ACTION_VIEW).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        if (mime == null) intent.data = uri else intent.setDataAndType(uri, mime)
        try { context.startActivity(intent) } catch (_: android.content.ActivityNotFoundException) { android.widget.Toast.makeText(context,R.string.no_handler,android.widget.Toast.LENGTH_LONG).show() }
    }
    fun share(context: Context, title: String, url: String) {
        context.startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT,"$title\n$url"),context.getString(R.string.share)))
    }
    fun copy(context: Context, text: String) { (context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager).setPrimaryClip(ClipData.newPlainText("",text)) }
    fun calendar(context: Context, row: JSONObject) {
        val intent=Intent(Intent.ACTION_INSERT).setData(CalendarContract.Events.CONTENT_URI)
            .putExtra(CalendarContract.Events.TITLE,row.optJSONObject("payload")?.optString("title").orEmpty())
            .putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME,OffsetDateTime.parse(row.getString("starts_at")).toInstant().toEpochMilli())
            .putExtra(CalendarContract.EXTRA_EVENT_END_TIME,OffsetDateTime.parse(row.getString("ends_at")).toInstant().toEpochMilli())
        try { context.startActivity(intent) } catch(_:android.content.ActivityNotFoundException) { android.widget.Toast.makeText(context,R.string.no_handler,android.widget.Toast.LENGTH_LONG).show() }
    }
    suspend fun download(context: Context, repo: Repository, path: String, name: String, mime: String) {
        val bytes=repo.api.download(path)
        kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
            val directory=context.cacheDir.resolve("exports").apply{mkdirs()}
            // Callers choose fixed filenames/extensions, never server-supplied paths.
            directory.resolve(name).writeBytes(bytes)
        }
        external(context,FileProvider.getUriForFile(context,context.packageName+".files",context.cacheDir.resolve("exports").resolve(name)),mime)
    }
}
