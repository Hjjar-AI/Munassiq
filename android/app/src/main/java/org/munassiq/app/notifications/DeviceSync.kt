package org.munassiq.app.notifications

import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat
import androidx.work.*
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.suspendCancellableCoroutine
import org.json.JSONObject
import org.munassiq.app.MunassiqApplication
import java.util.UUID
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

class DeviceSync(context: Context, parameters: WorkerParameters) : CoroutineWorker(context, parameters) {
    override suspend fun doWork(): Result {
        val app = applicationContext as MunassiqApplication
        if (app.repository.user() == null || FirebaseApp.getApps(app).isEmpty()) return Result.success()
        if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(app, android.Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return Result.success()
        return try {
            val token = suspendCancellableCoroutine<String> { continuation ->
                FirebaseMessaging.getInstance().token.addOnSuccessListener { if (continuation.isActive) continuation.resume(it) }
                    .addOnFailureListener { if (continuation.isActive) continuation.resumeWithException(it) }
            }
            val prefs = app.getSharedPreferences("installation", Context.MODE_PRIVATE)
            val installation = prefs.getString("id", null) ?: UUID.randomUUID().toString().also { prefs.edit().putString("id", it).commit() }
            app.repository.api.request("me/devices/", "PUT", JSONObject().put("token", token).put("installation_id", installation))
            Result.success()
        } catch (error: org.munassiq.app.data.ApiFailure) {
            if (error.status == 401 || error.status == 403) Result.success() else if(runAttemptCount<5)Result.retry() else Result.failure()
        } catch (_: Exception) { if (runAttemptCount < 5) Result.retry() else Result.failure() }
    }
    companion object {
        fun enqueue(context: Context) {
            val request = OneTimeWorkRequestBuilder<DeviceSync>().setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()).build()
            WorkManager.getInstance(context).enqueueUniqueWork("device-sync", ExistingWorkPolicy.REPLACE, request)
        }
    }
}
