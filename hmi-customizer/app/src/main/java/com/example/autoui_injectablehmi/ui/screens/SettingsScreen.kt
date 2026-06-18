package com.example.autoui_injectablehmi.ui.screens

import com.example.autoui_injectablehmi.R
import android.content.Intent
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.autoui_injectablehmi.viewmodel.DashboardViewModel
import com.example.autoui_injectablehmi.ui.components.AdvancedColorPicker
import com.example.autoui_injectablehmi.ui.components.GridSelector
import androidx.compose.foundation.Image
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import android.graphics.ImageDecoder
import android.os.Build
import android.provider.MediaStore
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.material.icons.automirrored.filled.FormatAlignLeft
import androidx.compose.material.icons.automirrored.filled.FormatAlignRight
import androidx.compose.material.icons.filled.FormatAlignCenter
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton

@Composable
fun EditorSection(
    number: String,
    title: String,
    subtitle: String,
    summary: String? = null,
    expanded: Boolean,
    onExpand: () -> Unit,
    content: @Composable ColumnScope.() -> Unit
) {
    val circleColor by animateColorAsState(
        targetValue = if (expanded)
            MaterialTheme.colorScheme.primary
        else
            MaterialTheme.colorScheme.surfaceVariant,
        label = "circleColor"
    )
    val textColor by animateColorAsState(
        targetValue = if (expanded)
            MaterialTheme.colorScheme.onPrimary
        else
            MaterialTheme.colorScheme.onSurfaceVariant,
        label = "textColor"
    )

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .animateContentSize(),
        shape = RoundedCornerShape(0.dp), // flat inside the side panel
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (expanded)
                MaterialTheme.colorScheme.surfaceContainer
            else
                MaterialTheme.colorScheme.surface
        )
    ) {
        Column {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onExpand() }
                    .padding(horizontal = 16.dp, vertical = 14.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    contentAlignment = Alignment.Center,
                    modifier = Modifier
                        .size(28.dp)
                        .clip(CircleShape)
                        .background(circleColor)
                ) {
                    Text(
                        text = number,
                        color = textColor,
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold
                    )
                }

                Spacer(Modifier.width(10.dp))

                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = title,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold
                    )
                    Text(
                        text = subtitle,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    if (!expanded && !summary.isNullOrBlank()) {
                        Spacer(Modifier.height(3.dp))
                        Text(
                            text = summary,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.primary,
                            fontWeight = FontWeight.Medium
                        )
                    }
                }

                Icon(
                    imageVector = if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.size(18.dp)
                )
            }

            HorizontalDivider(
                color = MaterialTheme.colorScheme.outlineVariant,
                thickness = 0.5.dp
            )

            AnimatedVisibility(visible = expanded) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp),
                    content = content
                )
            }
        }
    }
}

enum class TextAlignment {
    LEFT,
    CENTER,
    RIGHT
}

@Composable
fun LivePreviewPanel(
    message: String,
    isBlinking: Boolean,
    bgColorHex: String,
    txtColorHex: String,
    fontSize: Float,
    fontWeight: String,
    fontStyle: String,
    gridStartCol: Int,
    gridEndCol: Int,
    gridStartRow: Int,
    gridEndRow: Int,
    isOverlayEnabled: Boolean,
    overlayOpacity: Float,
    isBannerPhotoEnabled: Boolean,
    bannerPhotoSource: String,
    overlayColorHex: String,
    isOverlayPhotoEnabled: Boolean,
    overlayPhotoSource: String,
    isAudioEnabled: Boolean,
    audioSource: String,
    textAlignment: TextAlignment,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current

    var previewPlayer by remember {
        mutableStateOf<android.media.MediaPlayer?>(null)
    }

    LaunchedEffect(audioSource) {

        if (
            isAudioEnabled &&
            audioSource.isNotBlank()
        ) {

            try {

                previewPlayer?.release()

                previewPlayer =
                    android.media.MediaPlayer().apply {
                        setDataSource(
                            context,
                            Uri.parse(audioSource)
                        )
                        prepare()
                        start()
                    }

            } catch (_: Exception) {
            }
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            previewPlayer?.release()
        }
    }

    var bannerBitmap by remember {
        mutableStateOf<ImageBitmap?>(null)
    }

    LaunchedEffect(bannerPhotoSource) {
        if (isBannerPhotoEnabled && bannerPhotoSource.isNotBlank()) {
            try {
                val uri = Uri.parse(bannerPhotoSource)

                val bitmap =
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                        ImageDecoder.decodeBitmap(
                            ImageDecoder.createSource(
                                context.contentResolver,
                                uri
                            )
                        )
                    } else {
                        @Suppress("DEPRECATION")
                        MediaStore.Images.Media.getBitmap(
                            context.contentResolver,
                            uri
                        )
                    }

                bannerBitmap = bitmap.asImageBitmap()
            } catch (e: Exception) {
                bannerBitmap = null
            }
        } else {
            bannerBitmap = null
        }
    }
    var overlayBitmap by remember {
        mutableStateOf<ImageBitmap?>(null)
    }

    LaunchedEffect(overlayPhotoSource, isOverlayPhotoEnabled) {

        if (
            isOverlayPhotoEnabled &&
            overlayPhotoSource.isNotBlank()
        ) {

            try {

                val uri = Uri.parse(overlayPhotoSource)

                val bitmap =
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                        ImageDecoder.decodeBitmap(
                            ImageDecoder.createSource(
                                context.contentResolver,
                                uri
                            )
                        )
                    } else {
                        @Suppress("DEPRECATION")
                        MediaStore.Images.Media.getBitmap(
                            context.contentResolver,
                            uri
                        )
                    }

                overlayBitmap = bitmap.asImageBitmap()

            } catch (_: Exception) {
                overlayBitmap = null
            }

        } else {
            overlayBitmap = null
        }
    }
    // Normalise hex: strip any existing '#' then always prepend one,
    // so both "FFCC00" and "#FFCC00" from AdvancedColorPicker work.
    val bgColor = remember(bgColorHex) {
        runCatching {
            Color(android.graphics.Color.parseColor("#${bgColorHex.trimStart('#')}"))
        }.getOrElse { Color(0xFFFFCC00) }
    }
    val txtColor = remember(txtColorHex) {
        runCatching {
            Color(android.graphics.Color.parseColor("#${txtColorHex.trimStart('#')}"))
        }.getOrElse { Color.Black }
    }

    val overlayColor = remember(overlayColorHex) {
        try {
            Color(android.graphics.Color.parseColor(overlayColorHex))
        } catch (_: Exception) {
            Color.Black
        }
    }

    // Flashing animation — pulses the banner alpha when isBlinking is true
    val infiniteTransition = rememberInfiniteTransition(label = "blink")
    val blinkAlpha by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue  = 0f,
        animationSpec = infiniteRepeatable(
            animation  = tween(durationMillis = 600, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "blinkAlpha"
    )
    val bannerAlpha = if (isBlinking) blinkAlpha else 1f

    val fWeight = when (fontWeight) {
        "Bold" -> FontWeight.Bold
        "ExtraBold" -> FontWeight.ExtraBold
        else -> FontWeight.Normal
    }
    val fStyle = if (fontStyle == "Italic") FontStyle.Italic else FontStyle.Normal

    val cols = 8
    val rows = 6

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.4f))
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // Header label
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                "Live Preview",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurface
            )
        }

        Spacer(Modifier.height(28.dp))

        // Screen simulation frame
        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(16f / 9f),
            shape = RoundedCornerShape(12.dp),
            border = BorderStroke(2.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.4f)),
            color = Color.Transparent
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .clip(RoundedCornerShape(12.dp))
            ) {
                Image(
                    painter = painterResource(id = R.drawable.home),
                    contentDescription = "Dashboard Preview",
                    modifier = Modifier.matchParentSize(),
                    contentScale = ContentScale.FillBounds
                )
                // Overlay dim
                if (isOverlayEnabled) {

                    // Draw photo first
                    if (isOverlayPhotoEnabled && overlayBitmap != null) {
                        Image(
                            bitmap = overlayBitmap!!,
                            contentDescription = null,
                            modifier = Modifier.fillMaxSize(),
                            contentScale = ContentScale.Crop
                        )
                    }

                    // Then draw colour tint on top
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .background(
                                overlayColor.copy(alpha = overlayOpacity)
                            )
                    )
                }

                // Grid-positioned banner
                // gridStartCol/Row are 1-based (1..cols, 1..rows)
                // Convert to 0-based fractions for layout
                val colSpan = (gridEndCol - gridStartCol + 1).coerceAtLeast(1)
                val rowSpan = (gridEndRow - gridStartRow + 1).coerceAtLeast(1)
                val colOffsetFrac = (gridStartCol - 1).toFloat() / cols
                val rowOffsetFrac = (gridStartRow - 1).toFloat() / rows
                val colSizeFrac   = colSpan.toFloat() / cols
                val rowSizeFrac   = rowSpan.toFloat() / rows

                BoxWithConstraints(modifier = Modifier.fillMaxSize()) {
                    val rawBannerX = maxWidth * colOffsetFrac
                    val rawBannerY = maxHeight * rowOffsetFrac

                    val bannerW = maxWidth * colSizeFrac
                    val bannerH = maxHeight * rowSizeFrac

                    val bannerX = rawBannerX.coerceIn(0.dp, maxWidth - bannerW)
                    val bannerY = rawBannerY.coerceIn(0.dp, maxHeight - bannerH)

                    Box(
                        modifier = Modifier
                            .absoluteOffset(x = bannerX, y = bannerY)
                            .width(bannerW)
                            .height(bannerH)
                            .graphicsLayer { alpha = bannerAlpha }
                            .background(bgColor, RoundedCornerShape(4.dp)),
                        contentAlignment = Alignment.Center
                    ) {

                        Row(
                            modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp),
                            horizontalArrangement = when (textAlignment) {
                                TextAlignment.LEFT -> Arrangement.Start
                                TextAlignment.CENTER -> Arrangement.Center
                                TextAlignment.RIGHT -> Arrangement.End
                            },
                            verticalAlignment = Alignment.CenterVertically
                        ){

                            if (isBannerPhotoEnabled && bannerBitmap != null) {

                                Image(
                                    bitmap = bannerBitmap!!,
                                    contentDescription = null,
                                    modifier = Modifier
                                        .padding(end = 16.dp)
                                        .size(64.dp),
                                    contentScale = ContentScale.Fit
                                )

                                Spacer(modifier = Modifier.width(12.dp))
                            }

                            Text(
                                text = message.ifBlank { "Banner message" },
                                color = txtColor,
                                fontSize = (fontSize * 0.25f).sp,
                                fontWeight = fWeight,
                                fontStyle = fStyle)
                        }
                    }
                }
            }
        }

        Spacer(Modifier.height(20.dp))

        // Summary chips
        Surface(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(10.dp),
            color = MaterialTheme.colorScheme.surface,
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)
        ) {
            Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(
                    "Current Configuration",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                HorizontalDivider(thickness = 0.5.dp, color = MaterialTheme.colorScheme.outlineVariant)
                PreviewStat("Position", "Col ${gridStartCol}–${gridEndCol}, Row ${gridStartRow}–${gridEndRow}")
                PreviewStat("Size", "${gridEndCol - gridStartCol + 1} × ${gridEndRow - gridStartRow + 1} cells")
                PreviewStat("Typography", "${fontSize.toInt()}sp · $fontWeight · $fontStyle")
                PreviewStat("Background", "#$bgColorHex")
                PreviewStat("Text color", "#$txtColorHex")
                PreviewStat("Animation", if (isBlinking) "Flashing" else "Static")
                PreviewStat("Overlay", if (isOverlayEnabled) "${(overlayOpacity * 100).toInt()}% dim" else "Off")
            }
        }
    }
}

@Composable
private fun PreviewStat(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
    }
}


@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    viewModel: DashboardViewModel,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val currentSettings by viewModel.bannerSettings.collectAsState()
    var lastSavedSettings by remember(currentSettings) {
        mutableStateOf(currentSettings)
    }
    val profiles by viewModel.savedProfiles.collectAsState()

    // ── Local UI States ────────────────────────────────────────────────────
    var message by remember { mutableStateOf(currentSettings.message) }
    var isBlinking by remember { mutableStateOf(currentSettings.isBlinking) }

    var gridStartCol by remember { mutableIntStateOf(currentSettings.gridStartCol) }
    var gridEndCol by remember { mutableIntStateOf(currentSettings.gridEndCol) }
    var gridStartRow by remember { mutableIntStateOf(currentSettings.gridStartRow) }
    var gridEndRow by remember { mutableIntStateOf(currentSettings.gridEndRow) }

    var isOverlayEnabled by remember { mutableStateOf(currentSettings.isOverlayEnabled) }
    var isOverlayPhotoEnabled by remember { mutableStateOf(currentSettings.isOverlayPhotoEnabled) }
    var overlayPhotoSource by remember { mutableStateOf(currentSettings.overlayPhotoSource) }
    var overlayColorHex by remember { mutableStateOf(currentSettings.overlayColorHex) }
    var overlayOpacity by remember { mutableFloatStateOf(currentSettings.overlayOpacity) }

    var fontSize by remember { mutableFloatStateOf(currentSettings.fontSize.toFloat()) }
    var fontWeight by remember { mutableStateOf(currentSettings.fontWeight) }
    var fontStyle by remember { mutableStateOf(currentSettings.fontStyle) }

    var bgColorHex by remember { mutableStateOf(currentSettings.backgroundColorHex) }
    var txtColorHex by remember { mutableStateOf(currentSettings.textColorHex) }

    var isBannerPhotoEnabled by remember { mutableStateOf(currentSettings.isBannerPhotoEnabled) }
    var bannerPhotoSource by remember { mutableStateOf(currentSettings.bannerPhotoSource) }
    var isAudioEnabled by remember { mutableStateOf(currentSettings.isAudioEnabled) }
    var audioSource by remember { mutableStateOf(currentSettings.audioSource) }

    var expandedSection by remember { mutableStateOf<Int?>(null) }
    var textAlignment by remember {
        mutableStateOf(TextAlignment.CENTER)
    }

    // ── File Pickers ───────────────────────────────────────────────────────
    val audioLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        uri?.let {
            context.contentResolver.takePersistableUriPermission(it, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            audioSource = it.toString()
        }
    }
    val bannerPhotoLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        uri?.let {
            context.contentResolver.takePersistableUriPermission(it, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            bannerPhotoSource = it.toString()
        }
    }
    val overlayPhotoLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        uri?.let {
            context.contentResolver.takePersistableUriPermission(it, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            overlayPhotoSource = it.toString()
        }
    }


    // ── Sync when profile loaded externally ───────────────────────────────
    LaunchedEffect(currentSettings) {
        message = currentSettings.message
        isBlinking = currentSettings.isBlinking
        gridStartCol = currentSettings.gridStartCol
        gridEndCol = currentSettings.gridEndCol
        gridStartRow = currentSettings.gridStartRow
        gridEndRow = currentSettings.gridEndRow
        isOverlayEnabled = currentSettings.isOverlayEnabled
        isOverlayPhotoEnabled = currentSettings.isOverlayPhotoEnabled
        overlayPhotoSource = currentSettings.overlayPhotoSource
        overlayColorHex = currentSettings.overlayColorHex
        overlayOpacity = currentSettings.overlayOpacity
        fontSize = currentSettings.fontSize.toFloat()
        fontWeight = currentSettings.fontWeight
        fontStyle = currentSettings.fontStyle
        bgColorHex = currentSettings.backgroundColorHex
        txtColorHex = currentSettings.textColorHex
        isBannerPhotoEnabled = currentSettings.isBannerPhotoEnabled
        bannerPhotoSource = currentSettings.bannerPhotoSource
        isAudioEnabled = currentSettings.isAudioEnabled
        audioSource = currentSettings.audioSource
        textAlignment = currentSettings.textAlignment
    }

    // ── Build live preview settings object ────────────────────────────────
    val previewSettings = currentSettings.copy(
        message = message,
        isBlinking = isBlinking,
        gridStartCol = gridStartCol,
        gridEndCol = gridEndCol,
        gridStartRow = gridStartRow,
        gridEndRow = gridEndRow,
        isOverlayEnabled = isOverlayEnabled,
        isOverlayPhotoEnabled = isOverlayPhotoEnabled,
        overlayPhotoSource = overlayPhotoSource,
        overlayColorHex = overlayColorHex,
        overlayOpacity = overlayOpacity,
        fontSize = fontSize.toInt(),
        fontWeight = fontWeight,
        fontStyle = fontStyle,
        backgroundColorHex = bgColorHex,
        textColorHex = txtColorHex,
        isBannerPhotoEnabled = isBannerPhotoEnabled,
        bannerPhotoSource = bannerPhotoSource,
        isAudioEnabled = isAudioEnabled,
        audioSource = audioSource,
        textAlignment = textAlignment
    )


    // ── Root layout: top toolbar + split body ─────────────────────────────
    Column(modifier = modifier.fillMaxSize()) {

        // ── Top toolbar ───────────────────────────────────────────────────
        Surface(
            modifier = Modifier.fillMaxWidth(),
            color = MaterialTheme.colorScheme.surface,
            shadowElevation = 2.dp
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    "Experiment Control Panel",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f)
                )

                // Unsaved-changes badge
                val hasUnsavedChanges = previewSettings != lastSavedSettings

                if (hasUnsavedChanges) {
                    Surface(
                        shape = RoundedCornerShape(6.dp),
                        color = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.7f),
                        modifier = Modifier.padding(end = 12.dp)
                    ) {
                        Text(
                            "  Unsaved changes  ",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onErrorContainer,
                            modifier = Modifier.padding(vertical = 3.dp)
                        )
                    }
                }

                Button(
                    onClick = {
                        viewModel.updateSettings(previewSettings)
                        lastSavedSettings = previewSettings
                    },
                    contentPadding = PaddingValues(horizontal = 20.dp, vertical = 8.dp)
                ) {
                    Icon(Icons.Default.Check, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("Save Layout", style = MaterialTheme.typography.labelMedium)
                }
            }
        }

        // ── Split body: left panel + right preview ────────────────────────
        Row(modifier = Modifier.fillMaxSize()) {

            // ── LEFT PANEL — settings accordion ───────────────────────────
            Column(
                modifier = Modifier
                    .width(340.dp)
                    .fillMaxHeight()
            ) {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.surface,
                    border = BorderStroke(
                        width = 1.dp,
                        color = MaterialTheme.colorScheme.outlineVariant
                    )
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .verticalScroll(rememberScrollState())
                    ) {

                        // ── Panel header ──────────────────────────────────
                        Text(
                            "Properties",
                            style = MaterialTheme.typography.labelLarge,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)
                        )

                        HorizontalDivider(
                            color = MaterialTheme.colorScheme.outlineVariant,
                            thickness = 0.5.dp
                        )

                        // ── 0. Saved Profiles ─────────────────────────────
                        var profileDropExpanded by remember { mutableStateOf(false) }
                        var selectedProfileName by remember { mutableStateOf("") }
                        var newProfileName by remember { mutableStateOf("") }

                        EditorSection(
                            number = "0",
                            title = "Saved Profiles",
                            subtitle = "Load or save configurations",
                            summary = selectedProfileName.ifBlank { "${profiles.size} profiles" },
                            expanded = expandedSection == 0,
                            onExpand = { expandedSection = if (expandedSection == 0) null else 0 }
                        ) {
                            ExposedDropdownMenuBox(
                                expanded = profileDropExpanded,
                                onExpandedChange = { profileDropExpanded = it }
                            ) {
                                OutlinedTextField(
                                    value = selectedProfileName.ifEmpty { "Select a profile…" },
                                    onValueChange = {},
                                    readOnly = true,
                                    label = { Text("Load configuration") },
                                    trailingIcon = {
                                        Row(verticalAlignment = Alignment.CenterVertically) {
                                            ExposedDropdownMenuDefaults.TrailingIcon(expanded = profileDropExpanded)
                                            if (selectedProfileName.isNotBlank() && profiles.containsKey(selectedProfileName)) {
                                                IconButton(
                                                    onClick = {
                                                        viewModel.deleteProfile(selectedProfileName)
                                                        selectedProfileName = ""
                                                    },
                                                    modifier = Modifier.size(32.dp)
                                                ) {
                                                    Icon(
                                                        Icons.Default.Delete,
                                                        contentDescription = "Delete",
                                                        tint = MaterialTheme.colorScheme.error,
                                                        modifier = Modifier.size(16.dp)
                                                    )
                                                }
                                            }
                                        }
                                    },
                                    modifier = Modifier
                                        .menuAnchor()
                                        .fillMaxWidth(),
                                    textStyle = MaterialTheme.typography.bodySmall
                                )
                                ExposedDropdownMenu(
                                    expanded = profileDropExpanded,
                                    onDismissRequest = { profileDropExpanded = false }
                                ) {
                                    if (profiles.isEmpty()) {
                                        DropdownMenuItem(
                                            text = { Text("No saved profiles yet") },
                                            onClick = { profileDropExpanded = false }
                                        )
                                    } else {
                                        profiles.keys.forEach { name ->
                                            DropdownMenuItem(
                                                text = { Text(name) },
                                                onClick = {
                                                    selectedProfileName = name
                                                    viewModel.loadProfile(name)
                                                    profileDropExpanded = false
                                                }
                                            )
                                        }
                                    }
                                }
                            }

                            Spacer(Modifier.height(4.dp))

                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                OutlinedTextField(
                                    value = newProfileName,
                                    onValueChange = { newProfileName = it },
                                    label = { Text("New profile name") },
                                    modifier = Modifier.weight(1f),
                                    singleLine = true,
                                    textStyle = MaterialTheme.typography.bodySmall
                                )
                                FilledTonalButton(
                                    onClick = {
                                        if (newProfileName.isNotBlank()) {
                                            viewModel.saveAsProfile(newProfileName, previewSettings)
                                            selectedProfileName = newProfileName
                                            newProfileName = ""
                                        }
                                    },
                                    enabled = newProfileName.isNotBlank(),
                                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp)
                                ) {
                                    Text("Save", style = MaterialTheme.typography.labelMedium)
                                }
                            }
                        }

                        // ── 1. Content & Animation ────────────────────────
                        EditorSection(
                            number = "1",
                            title = "Content & Animation",
                            subtitle = "Message, flash and banner image",
                            summary = "${if (isBlinking) "Flashing" else "Static"} • " +
                                    when {
                                        !isBannerPhotoEnabled -> "No image"
                                        bannerPhotoSource.isBlank() -> "Image (no file)"
                                        else -> "Image set"
                                    },
                            expanded = expandedSection == 1,
                            onExpand = { expandedSection = if (expandedSection == 1) null else 1 }
                        ) {
                            OutlinedTextField(
                                value = message,
                                onValueChange = { message = it },
                                label = { Text("Warning message") },
                                modifier = Modifier.fillMaxWidth(),
                                textStyle = MaterialTheme.typography.bodySmall,
                                minLines = 2
                            )
                            Spacer(Modifier.height(12.dp))
                            Text(
                                "Text Alignment",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )

                            Row(
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {

                                FilledTonalIconButton(
                                    onClick = { textAlignment = TextAlignment.LEFT },
                                    colors = IconButtonDefaults.filledTonalIconButtonColors(
                                        containerColor =
                                            if (textAlignment == TextAlignment.LEFT)
                                                MaterialTheme.colorScheme.primaryContainer
                                            else
                                                MaterialTheme.colorScheme.surfaceVariant
                                    )
                                ) {
                                    Icon(
                                        Icons.AutoMirrored.Filled.FormatAlignLeft,
                                        contentDescription = "Left"
                                    )
                                }

                                FilledTonalIconButton(
                                    onClick = { textAlignment = TextAlignment.CENTER },
                                    colors = IconButtonDefaults.filledTonalIconButtonColors(
                                        containerColor =
                                            if (textAlignment == TextAlignment.CENTER)
                                                MaterialTheme.colorScheme.primaryContainer
                                            else
                                                MaterialTheme.colorScheme.surfaceVariant
                                    )
                                ) {
                                    Icon(
                                        Icons.Filled.FormatAlignCenter,
                                        contentDescription = "Center"
                                    )
                                }

                                FilledTonalIconButton(
                                    onClick = { textAlignment = TextAlignment.RIGHT },
                                    colors = IconButtonDefaults.filledTonalIconButtonColors(
                                        containerColor =
                                            if (textAlignment == TextAlignment.RIGHT)
                                                MaterialTheme.colorScheme.primaryContainer
                                            else
                                                MaterialTheme.colorScheme.surfaceVariant
                                    )
                                ) {
                                    Icon(
                                        Icons.AutoMirrored.Filled.FormatAlignRight,
                                        contentDescription = "Right"
                                    )
                                }
                            }
                            Spacer(Modifier.height(8.dp))

                            SettingsToggleRow("Flashing animation", isBlinking) { isBlinking = it }
                            SettingsToggleRow("Banner image", isBannerPhotoEnabled) {
                                isBannerPhotoEnabled = it
                                if (!it) bannerPhotoSource = ""
                            }

                            if (isBannerPhotoEnabled) {
                                FilePickerRow(
                                    label = "Banner image",
                                    source = bannerPhotoSource,
                                    onClear = { bannerPhotoSource = "" },
                                    onBrowse = { bannerPhotoLauncher.launch(arrayOf("image/*")) }
                                )
                            }
                        }

                        // ── 2. Banner Position ────────────────────────────
                        EditorSection(
                            number = "2",
                            title = "Banner Position",
                            subtitle = "Drag grid to place banner",
                            summary = "${gridEndCol - gridStartCol + 1}×${gridEndRow - gridStartRow + 1} area at (${gridStartCol},${gridStartRow})",
                            expanded = expandedSection == 2,
                            onExpand = { expandedSection = if (expandedSection == 2) null else 2 }
                        ) {
                            Text(
                                "Drag to select the banner area on the 8×6 grid.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            // GridSelector uses 0-based indices internally.
                            // currentSettings stores 1-based values (col 1..8, row 1..6).
                            // Convert: subtract 1 going in, add 1 coming out.
                            GridSelector(
                                cols = 8,
                                rows = 6,
                                startCol = (gridStartCol - 1).coerceIn(0, 7),
                                endCol   = (gridEndCol   - 1).coerceIn(0, 7),
                                startRow = (gridStartRow - 1).coerceIn(0, 5),
                                endRow   = (gridEndRow   - 1).coerceIn(0, 5),
                                onSelectionChanged = { sc, ec, sr, er ->
                                    // sc/ec/sr/er come back as 0-based → store as 1-based
                                    gridStartCol = sc + 1; gridEndCol = ec + 1
                                    gridStartRow = sr + 1; gridEndRow = er + 1
                                }
                            )
                        }

                        // ── 3. Background Overlay ─────────────────────────
                        EditorSection(
                            number = "3",
                            title = "Background Overlay",
                            subtitle = "Screen dimming and overlay image",
                            summary = if (!isOverlayEnabled) "Off"
                            else "On · ${(overlayOpacity * 100).toInt()}% opacity",
                            expanded = expandedSection == 3,
                            onExpand = { expandedSection = if (expandedSection == 3) null else 3 }
                        ) {
                            SettingsToggleRow("Enable screen dimming", isOverlayEnabled) { isOverlayEnabled = it }

                            if (isOverlayEnabled) {
                                Text(
                                    "Opacity: ${(overlayOpacity * 100).toInt()}%",
                                    style = MaterialTheme.typography.bodySmall
                                )
                                Slider(
                                    value = overlayOpacity,
                                    onValueChange = { overlayOpacity = it },
                                    valueRange = 0f..1f
                                )

                                SettingsToggleRow("Overlay photo", isOverlayPhotoEnabled) {
                                    isOverlayPhotoEnabled = it
                                    if (!it) overlayPhotoSource = ""
                                }

                                if (isOverlayPhotoEnabled) {
                                    FilePickerRow(
                                        label = "Overlay image",
                                        source = overlayPhotoSource,
                                        onClear = { overlayPhotoSource = "" },
                                        onBrowse = { overlayPhotoLauncher.launch(arrayOf("image/*")) }
                                    )
                                }

                                AdvancedColorPicker(
                                    label = "Overlay Color",
                                    initialHex = overlayColorHex
                                ) { overlayColorHex = it }
                            }
                        }

                        // ── 4. Typography ─────────────────────────────────
                        EditorSection(
                            number = "4",
                            title = "Typography",
                            subtitle = "Font size, weight and style",
                            summary = "${fontSize.toInt()}sp · $fontWeight · $fontStyle",
                            expanded = expandedSection == 4,
                            onExpand = { expandedSection = if (expandedSection == 4) null else 4 }
                        ) {
                            Text(
                                "Font size: ${fontSize.toInt()}sp",
                                style = MaterialTheme.typography.bodySmall
                            )
                            Slider(
                                value = fontSize,
                                onValueChange = { fontSize = it },
                                valueRange = 12f..100f
                            )

                            Text("Font weight", style = MaterialTheme.typography.bodySmall)
                            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                listOf("Normal", "Bold", "ExtraBold").forEach { w ->
                                    FilterChip(
                                        selected = fontWeight == w,
                                        onClick = { fontWeight = w },
                                        label = { Text(w, style = MaterialTheme.typography.labelSmall) }
                                    )
                                }
                            }

                            Text("Font style", style = MaterialTheme.typography.bodySmall)
                            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                listOf("Normal", "Italic").forEach { s ->
                                    FilterChip(
                                        selected = fontStyle == s,
                                        onClick = { fontStyle = s },
                                        label = { Text(s, style = MaterialTheme.typography.labelSmall) }
                                    )
                                }
                            }
                        }

                        // ── 5. Colors ─────────────────────────────────────
                        EditorSection(
                            number = "5",
                            title = "Colors",
                            subtitle = "Banner background and text color",
                            summary = "BG: #$bgColorHex · Text: #$txtColorHex",
                            expanded = expandedSection == 5,
                            onExpand = { expandedSection = if (expandedSection == 5) null else 5 }
                        ) {
                            AdvancedColorPicker(
                                label = "Banner background",
                                initialHex = bgColorHex
                            ) { bgColorHex = it }

                            AdvancedColorPicker(
                                label = "Banner text color",
                                initialHex = txtColorHex
                            ) { txtColorHex = it }
                        }

                        // ── 6. Audio ──────────────────────────────────────
                        EditorSection(
                            number = "6",
                            title = "Audio Alert",
                            subtitle = "MP3 alert sound",
                            summary = when {
                                !isAudioEnabled -> "Off"
                                audioSource.isBlank() -> "On · no file"
                                else -> "On · file loaded"
                            },
                            expanded = expandedSection == 6,
                            onExpand = { expandedSection = if (expandedSection == 6) null else 6 }
                        ) {
                            SettingsToggleRow("Enable audio alert", isAudioEnabled) {
                                isAudioEnabled = it
                                if (!it) audioSource = ""
                            }

                            if (isAudioEnabled) {
                                FilePickerRow(
                                    label = "MP3 audio file",
                                    source = audioSource,
                                    onClear = { audioSource = "" },
                                    onBrowse = { audioLauncher.launch(arrayOf("audio/*")) }
                                )
                            }
                        }

                        // Bottom spacer inside scroll
                        Spacer(Modifier.height(32.dp))
                    }
                }
            }

            // ── RIGHT PANEL — live preview ────────────────────────────────
            LivePreviewPanel(
                message = message,
                isBlinking = isBlinking,
                bgColorHex = bgColorHex,
                txtColorHex = txtColorHex,
                fontSize = fontSize,
                fontWeight = fontWeight,
                fontStyle = fontStyle,
                gridStartCol = gridStartCol,
                gridEndCol = gridEndCol,
                gridStartRow = gridStartRow,
                gridEndRow = gridEndRow,
                isOverlayEnabled = isOverlayEnabled,
                overlayOpacity = overlayOpacity,
                isBannerPhotoEnabled = isBannerPhotoEnabled,
                bannerPhotoSource = bannerPhotoSource,
                overlayColorHex = overlayColorHex,
                isOverlayPhotoEnabled = isOverlayPhotoEnabled,
                overlayPhotoSource = overlayPhotoSource,
                audioSource = audioSource,
                isAudioEnabled = isAudioEnabled,
                textAlignment = textAlignment,

                modifier = Modifier
                    .weight(1f)
                    .fillMaxHeight()
            )
        }
    }
}

@Composable
private fun SettingsToggleRow(label: String, checked: Boolean, onToggle: (Boolean) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(label, style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
        Switch(
            checked = checked,
            onCheckedChange = onToggle,
            modifier = Modifier.height(28.dp)
        )
    }
}

@Composable
private fun FilePickerRow(
    label: String,
    source: String,
    onClear: () -> Unit,
    onBrowse: () -> Unit
) {
    val displayName = remember(source) {
        try {
            Uri.parse(source).lastPathSegment?.substringAfterLast("/") ?: "File"
        } catch (_: Exception) {
            "File"
        }
    }

    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.padding(10.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    if (source.isBlank()) "No file selected" else displayName,
                    style = MaterialTheme.typography.bodySmall
                )
                Text(
                    label,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            if (source.isNotBlank()) {
                IconButton(onClick = onClear, modifier = Modifier.size(32.dp)) {
                    Icon(
                        Icons.Default.Delete,
                        contentDescription = "Remove",
                        tint = MaterialTheme.colorScheme.error,
                        modifier = Modifier.size(16.dp)
                    )
                }
            }
            TextButton(
                onClick = onBrowse,
                contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp)
            ) {
                Text(
                    if (source.isBlank()) "Browse" else "Replace",
                    style = MaterialTheme.typography.labelSmall
                )
            }
        }
    }
}
