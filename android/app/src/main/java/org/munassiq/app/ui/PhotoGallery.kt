package org.munassiq.app.ui

import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Images remain in memory and use the API's authenticated file permissions. */
@Composable fun PhotoGallery(model: AppViewModel, ids: List<Long>, onRemove: ((Long) -> Unit)? = null) {
    if (ids.isEmpty()) return
    val context = LocalContext.current
    val owner = model.repository.user()?.optLong("id")
    var index by remember(ids, owner) { mutableIntStateOf(0) }
    var fullscreen by remember(ids, owner) { mutableStateOf(false) }
    var bitmap by remember(ids, index, owner) { mutableStateOf<ImageBitmap?>(null) }
    var error by remember(ids, index, owner) { mutableStateOf<String?>(null) }
    var attempt by remember { mutableIntStateOf(0) }
    LaunchedEffect(ids, index, owner, attempt) {
        try {
            val bytes = model.repository.api.download("files/${ids[index]}/")
            bitmap = withContext(Dispatchers.Default) {
                val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
                BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
                val options = BitmapFactory.Options()
                while (bounds.outWidth / options.inSampleSize > 1600 || bounds.outHeight / options.inSampleSize > 1600) options.inSampleSize *= 2
                BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options)?.asImageBitmap()
                    ?: throw IllegalArgumentException("Invalid image")
            }
        } catch (failure: Exception) { error = localizedError(context, failure) }
    }
    val description = context.getString(org.munassiq.app.R.string.photo_position, index + 1, ids.size)
    Column {
        Text(description)
        bitmap?.let { Image(it, description, Modifier.fillMaxWidth().height(220.dp), contentScale = ContentScale.Fit) }
        if (bitmap == null && error == null) CircularProgressIndicator()
        error?.let { Text(it); TextButton(onClick = { error = null; attempt++ }) { Text(label("retry")) } }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TextButton(enabled = index > 0, onClick = { index-- }) { Text(label("previous")) }
            TextButton(enabled = bitmap != null, onClick = { fullscreen = true }) { Text(label("view_photo")) }
            if(onRemove != null) TextButton(onClick = { onRemove(ids[index]) }) { Text(label("remove")) }
            TextButton(enabled = index < ids.lastIndex, onClick = { index++ }) { Text(label("next")) }
        }
    }
    if (fullscreen) Dialog(onDismissRequest = { fullscreen = false }) {
        Surface { Column(Modifier.padding(16.dp)) {
            bitmap?.let { Image(it, description, Modifier.fillMaxWidth().height(440.dp), contentScale = ContentScale.Fit) }
            TextButton(onClick = { fullscreen = false }) { Text(label("back")) }
        } }
    }
}
