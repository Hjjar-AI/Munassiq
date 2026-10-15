package org.munassiq.app.notifications

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import org.munassiq.app.MainActivity
import org.munassiq.app.MunassiqApplication
import org.munassiq.app.R
import java.time.Instant
import java.time.LocalTime
import java.time.ZoneId

class PushService : FirebaseMessagingService() {
    override fun onNewToken(token: String) { DeviceSync.enqueue(this) }
    override fun onDeletedMessages() { DeviceSync.enqueue(this) } // Lists always refresh on opening.
    override fun onMessageReceived(message: RemoteMessage) {
        val app = application as MunassiqApplication
        if (app.repository.user() == null) return
        if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        val data = message.data
        val notice = data["notice_id"] ?: return
        val prefs = getSharedPreferences("push-dedupe", MODE_PRIVATE)
        if (prefs.contains(notice)) return
        data["expires_at"]?.let { value -> if (runCatching { java.time.OffsetDateTime.parse(value).toInstant().isBefore(Instant.now()) }.getOrDefault(true)) return }
        val quiet = runCatching {
            val start = data["quiet_start"].orEmpty(); val end = data["quiet_end"].orEmpty()
            if (start.isBlank() || end.isBlank()) false else {
                val local = LocalTime.now(ZoneId.of(data["time_zone"] ?: ZoneId.systemDefault().id))
                val from = LocalTime.parse(start); val until = LocalTime.parse(end)
                if (from < until) local >= from && local < until else local >= from || local < until
            }
        }.getOrDefault(data["silent"] == "true")
        val manager = getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= 26) {
            manager.createNotificationChannel(NotificationChannel("munassiq_default", getString(R.string.notifications), NotificationManager.IMPORTANCE_DEFAULT))
            manager.createNotificationChannel(NotificationChannel("munassiq_silent", getString(R.string.quiet_hours), NotificationManager.IMPORTANCE_LOW).apply { setSound(null, null); enableVibration(false) })
        }
        val destination = when {
            data["occurrence_id"] != null -> "munassiq://occurrences/${data["occurrence_id"]}"
            data["item_id"] != null -> "munassiq://${if(data["item_kind"]=="service")"services"else"events"}/${data["item_id"]}"
            else -> "munassiq://home"
        }
        val intent = Intent(this, MainActivity::class.java).setData(Uri.parse(destination)).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP)
        val id = notice.hashCode()
        val pending = PendingIntent.getActivity(this, id, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val notification = NotificationCompat.Builder(this, if (quiet) "munassiq_silent" else "munassiq_default")
            .setSmallIcon(R.drawable.ic_app).setContentTitle(data["title"] ?: message.notification?.title ?: getString(R.string.app_name))
            .setContentText(data["body"] ?: message.notification?.body ?: getString(R.string.open_details))
            .setAutoCancel(true).setContentIntent(pending).setSilent(quiet).build()
        manager.notify(id, notification)
        val cutoff = System.currentTimeMillis() - 30 * 86400000L
        val editor = prefs.edit()
        prefs.all.forEach { (key, value) -> if ((value as? Long ?: 0) < cutoff) editor.remove(key) }
        editor.putLong(notice, System.currentTimeMillis()).apply()
    }
}
