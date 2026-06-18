package com.example.autoui_injectablehmi.ui.screens

import android.media.MediaPlayer
import android.net.Uri
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.example.autoui_injectablehmi.R
import com.example.autoui_injectablehmi.model.AlertBannerSettings
import com.example.autoui_injectablehmi.ui.components.AlertBanner

@Composable
fun PreviewScreen(
    settings: AlertBannerSettings,
    onDismiss: () -> Unit
) {
    val context = LocalContext.current

    // --- LIVE AUDIO PREVIEW ---
    // This effect starts playing the audio when the dialog opens
    // and automatically stops it when the dialog is dismissed.
    DisposableEffect(settings.isAudioEnabled, settings.audioSource) {
        var mediaPlayer: MediaPlayer? = null
        if (settings.isAudioEnabled && settings.audioSource.isNotBlank()) {
            try {
                mediaPlayer = MediaPlayer().apply {
                    setDataSource(context, Uri.parse(settings.audioSource))
                    prepare()
                    isLooping = true
                    start()
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
        onDispose {
            mediaPlayer?.stop()
            mediaPlayer?.release()
        }
    }

    // --- DIALOG UI ---
    Dialog(
        onDismissRequest = onDismiss,
        // Override Android's default dialog size limits
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Card(
            modifier = Modifier
                .fillMaxWidth(0.9f)  // Take up 90% of tablet width
                .fillMaxHeight(0.9f) // Take up 90% of tablet height
        ) {
            Box(modifier = Modifier.fillMaxSize()) {

                // 1. Base Dashboard Background Image
                Image(
                    painter = painterResource(id = R.drawable.home),
                    contentDescription = "Dashboard Background",
                    modifier = Modifier.fillMaxSize(),
                    contentScale = ContentScale.FillBounds
                )

                // 2. Render the banner using the live unsaved settings (Images load automatically)
                AlertBanner(
                    settings = settings,
                    modifier = Modifier.fillMaxSize()
                )

                // 3. Close Button
                Button(
                    onClick = onDismiss,
                    modifier = Modifier
                        .align(Alignment.TopEnd)
                        .padding(16.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.error
                    )
                ) {
                    Text("Close Preview")
                }
            }
        }
    }
}