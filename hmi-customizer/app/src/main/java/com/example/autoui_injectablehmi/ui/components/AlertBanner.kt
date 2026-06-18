package com.example.autoui_injectablehmi.ui.components

import android.graphics.ImageDecoder
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import androidx.compose.animation.core.*
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.autoui_injectablehmi.model.AlertBannerSettings
import com.example.autoui_injectablehmi.ui.screens.TextAlignment

@Composable
fun AlertBanner(
    settings: AlertBannerSettings,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current

    // 1. Blinking Animation
    val infiniteTransition = rememberInfiniteTransition(label = "blink")
    val animatedAlpha by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 0f,
        animationSpec = infiniteRepeatable(
            animation = tween(500, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "alpha"
    )
    val currentAlpha = if (settings.isBlinking) animatedAlpha else 1f

    // 2. Typography Mapping
    val mappedWeight = when (settings.fontWeight) {
        "Normal" -> FontWeight.Normal
        "ExtraBold" -> FontWeight.ExtraBold
        else -> FontWeight.Bold
    }
    val mappedStyle = if (settings.fontStyle == "Italic") FontStyle.Italic else FontStyle.Normal
    val mappedFamily = when (settings.fontFamily) {
        "Monospace" -> FontFamily.Monospace
        "Serif" -> FontFamily.Serif
        else -> FontFamily.Default
    }

    // 3. Load Banner Photo Bitmap if Uploaded
    var bannerBitmap by remember { mutableStateOf<androidx.compose.ui.graphics.ImageBitmap?>(null) }
    LaunchedEffect(settings.bannerPhotoSource) {
        if (settings.isBannerPhotoEnabled && settings.bannerPhotoSource.isNotBlank()) {
            try {
                val uri = Uri.parse(settings.bannerPhotoSource)
                val btm = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                    ImageDecoder.decodeBitmap(ImageDecoder.createSource(context.contentResolver, uri))
                } else {
                    @Suppress("DEPRECATION")
                    MediaStore.Images.Media.getBitmap(context.contentResolver, uri)
                }
                bannerBitmap = btm.asImageBitmap()
            } catch (e: Exception) {
                e.printStackTrace()
                bannerBitmap = null
            }
        } else {
            bannerBitmap = null
        }
    }

    // 4. Load Overlay Photo Bitmap if Uploaded
    var overlayBitmap by remember { mutableStateOf<androidx.compose.ui.graphics.ImageBitmap?>(null) }
    LaunchedEffect(settings.overlayPhotoSource) {
        if (settings.isOverlayPhotoEnabled && settings.overlayPhotoSource.isNotBlank()) {
            try {
                val uri = Uri.parse(settings.overlayPhotoSource)
                val btm = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                    ImageDecoder.decodeBitmap(ImageDecoder.createSource(context.contentResolver, uri))
                } else {
                    @Suppress("DEPRECATION")
                    MediaStore.Images.Media.getBitmap(context.contentResolver, uri)
                }
                overlayBitmap = btm.asImageBitmap()
            } catch (e: Exception) {
                e.printStackTrace()
                overlayBitmap = null
            }
        } else {
            overlayBitmap = null
        }
    }

    // BoxWithConstraints allows us to get the actual dp dimensions of the screen
    @Suppress("UnusedBoxWithConstraintsScope")
    BoxWithConstraints(
        modifier = modifier.fillMaxSize(),
        contentAlignment = Alignment.TopStart // Anchor to top-left so offsets are calculated correctly
    ) {
        // --- Background Screen Overlay ---
        if (settings.isOverlayEnabled) {
            Box(modifier = Modifier.fillMaxSize()) {
                // If a photo was uploaded, display it as the background
                if (settings.isOverlayPhotoEnabled && overlayBitmap != null) {
                    Image(
                        bitmap = overlayBitmap!!,
                        contentDescription = "Background Overlay Image",
                        contentScale = ContentScale.Crop, // Stretches beautifully across the tablet
                        modifier = Modifier.fillMaxSize()
                    )
                }
                // Apply the dimming layer over the top
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .background(
                            Color(android.graphics.Color.parseColor(settings.overlayColorHex))
                                .copy(alpha = settings.overlayOpacity)
                        )
                )
            }
        }

        // --- Grid Positioning and Rendering ---
        val colSpan = (settings.gridEndCol - settings.gridStartCol + 1)
        val rowSpan = (settings.gridEndRow - settings.gridStartRow + 1)

        val bannerWidth =
            maxWidth * (colSpan.toFloat() / settings.gridCols)

        val bannerHeight =
            maxHeight * (rowSpan.toFloat() / settings.gridRows)

        val offsetX =
            maxWidth * ((settings.gridStartCol - 1).toFloat() / settings.gridCols)

        val offsetY =
            maxHeight * ((settings.gridStartRow - 1).toFloat() / settings.gridRows)

        Box(
            modifier = Modifier
                .offset(x = offsetX, y = offsetY)
                .width(bannerWidth)
                .height(bannerHeight)
                .alpha(currentAlpha)
                .background(Color(android.graphics.Color.parseColor(settings.backgroundColorHex)),RoundedCornerShape(4.dp))
                .padding(settings.padding.dp),
            contentAlignment = Alignment.Center
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp),

                horizontalArrangement = when (settings.textAlignment) {
                    TextAlignment.LEFT -> Arrangement.Start
                    TextAlignment.CENTER -> Arrangement.Center
                    TextAlignment.RIGHT -> Arrangement.End
                },

                verticalAlignment = Alignment.CenterVertically
            ) {

                // --- Display Banner Photo if Enabled ---
                if (settings.isBannerPhotoEnabled) {
                    if (bannerBitmap != null) {
                        Image(
                            bitmap = bannerBitmap!!,
                            contentDescription = "Banner Image",
                            modifier = Modifier
                                .padding(end = 16.dp)
                                .size(64.dp)
                        )
                    } else {
                        // Fallback Placeholder if no photo selected
                        Box(
                            modifier = Modifier
                                .padding(end = 16.dp)
                                .size(64.dp)
                                .background(Color.Black.copy(alpha = 0.3f), RoundedCornerShape(8.dp)),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = "No Image\nSelected",
                                color = Color.White,
                                fontSize = 10.sp,
                                textAlign = TextAlign.Center
                            )
                        }
                    }
                }

                Text(
                    text = settings.message,
                    color = Color(android.graphics.Color.parseColor(settings.textColorHex)),
                    fontWeight = mappedWeight,
                    fontStyle = mappedStyle,
                    fontFamily = mappedFamily,
                    fontSize = (settings.fontSize * 0.35f).sp
                )
            }
        }
    }
}