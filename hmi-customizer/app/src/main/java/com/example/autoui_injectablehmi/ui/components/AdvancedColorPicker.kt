package com.example.autoui_injectablehmi.ui.components

import android.content.Context
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

@Composable
fun AdvancedColorPicker(
    label: String,
    initialHex: String,
    onColorChanged: (String) -> Unit
) {
    // 1. Setup Local SharedPreferences for the Color Palette
    val context = LocalContext.current
    val sharedPreferences = context.getSharedPreferences("custom_color_palette", Context.MODE_PRIVATE)

    // Load saved palette or fallback to the default 16 colors
    val savedPaletteStr = sharedPreferences.getString("saved_colors", null)
    val initialPalette = if (savedPaletteStr != null) {
        savedPaletteStr.split(",")
    } else {
        listOf(
            "#F44336", "#FF8A80", "#D32F2F", "#2196F3", "#FFC107", "#FF5722", "#D7CCC8", "#000000",
            "#2E7D32", "#4CAF50", "#81C784", "#009688", "#00BCD4", "#9C27B0", "#CE93D8", "#FFFFFF"
        )
    }

    // Convert to a mutable state list so the UI updates when we add a color
    val presetColors = remember { mutableStateListOf(*initialPalette.toTypedArray()) }

    // Safely parse the initial hex
    val parsedColor = try {
        android.graphics.Color.parseColor(if (!initialHex.startsWith("#")) "#$initialHex" else initialHex)
    } catch (e: Exception) {
        android.graphics.Color.RED
    }

    // Convert to HSV (Hue, Saturation, Value) for the Canvas
    val hsvArray = FloatArray(3)
    android.graphics.Color.colorToHSV(parsedColor, hsvArray)

    var hue by remember { mutableFloatStateOf(hsvArray[0]) }
    var saturation by remember { mutableFloatStateOf(hsvArray[1]) }
    var value by remember { mutableFloatStateOf(hsvArray[2]) }

    var hexString by remember { mutableStateOf(initialHex.uppercase()) }

    // Sync HSV changes to the Hex string and notify parent
    LaunchedEffect(hue, saturation, value) {
        val colorInt = android.graphics.Color.HSVToColor(floatArrayOf(hue, saturation, value))
        val newHex = String.format("#%06X", 0xFFFFFF and colorInt)
        if (newHex != hexString) {
            hexString = newHex
            onColorChanged(newHex)
        }
    }

    // Function to save the current color to the grid
    fun saveColorToPalette() {
        if (!presetColors.contains(hexString)) {
            presetColors.add(0, hexString) // Add to the front of the list
            if (presetColors.size > 16) {
                // Safely remove the last item using its exact index
                presetColors.removeAt(presetColors.size - 1)
            }
            // Save to device memory
            sharedPreferences.edit().putString("saved_colors", presetColors.joinToString(",")).apply()
        }
    }

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(label, modifier = Modifier.weight(1f), fontWeight = FontWeight.Bold)
            Box(
                modifier = Modifier
                    .size(32.dp)
                    .background(
                        Color(android.graphics.Color.HSVToColor(floatArrayOf(hue, saturation, value))),
                        RoundedCornerShape(4.dp)
                    )
                    .border(1.dp, Color.Gray, RoundedCornerShape(4.dp))
            )
        }

        // 1. 2D Color Canvas (Saturation & Value)
        Canvas(
            modifier = Modifier
                .fillMaxWidth()
                .height(150.dp)
                .clip(RoundedCornerShape(8.dp))
                .pointerInput(Unit) {
                    detectDragGestures { change, _ ->
                        saturation = (change.position.x / size.width).coerceIn(0f, 1f)
                        value = 1f - (change.position.y / size.height).coerceIn(0f, 1f)
                    }
                }
                .pointerInput(Unit) {
                    detectTapGestures { offset ->
                        saturation = (offset.x / size.width).coerceIn(0f, 1f)
                        value = 1f - (offset.y / size.height).coerceIn(0f, 1f)
                    }
                }
        ) {
            drawRect(color = Color.hsv(hue, 1f, 1f))
            drawRect(brush = Brush.horizontalGradient(colors = listOf(Color.White, Color.Transparent)))
            drawRect(brush = Brush.verticalGradient(colors = listOf(Color.Transparent, Color.Black)))

            val selectorX = saturation * size.width
            val selectorY = (1f - value) * size.height
            drawCircle(color = Color.White, radius = 8.dp.toPx(), center = Offset(selectorX, selectorY), style = Stroke(width = 2.dp.toPx()))
            drawCircle(color = Color.Black, radius = 8.dp.toPx(), center = Offset(selectorX, selectorY), style = Stroke(width = 1.dp.toPx()))
        }

        // 2. Hue Slider (Color Spectrum)
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(24.dp)
                .background(
                    brush = Brush.horizontalGradient(
                        colors = listOf(
                            Color.hsv(0f, 1f, 1f), Color.hsv(60f, 1f, 1f),
                            Color.hsv(120f, 1f, 1f), Color.hsv(180f, 1f, 1f),
                            Color.hsv(240f, 1f, 1f), Color.hsv(300f, 1f, 1f),
                            Color.hsv(360f, 1f, 1f)
                        )
                    ),
                    shape = RoundedCornerShape(12.dp)
                )
        ) {
            Slider(
                value = hue,
                onValueChange = { hue = it },
                valueRange = 0f..360f,
                colors = SliderDefaults.colors(
                    thumbColor = Color.White,
                    activeTrackColor = Color.Transparent,
                    inactiveTrackColor = Color.Transparent
                ),
                modifier = Modifier.fillMaxWidth()
            )
        }

        // 3. HEX Input Field
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text("HEX Code:", style = MaterialTheme.typography.bodyMedium)
            OutlinedTextField(
                value = hexString,
                onValueChange = { newValue ->
                    val cleanValue = if (newValue.startsWith("#")) newValue else "#$newValue"
                    hexString = cleanValue.uppercase()

                    if (cleanValue.length == 7 || cleanValue.length == 9) {
                        try {
                            val colorInt = android.graphics.Color.parseColor(cleanValue)
                            val newHsv = FloatArray(3)
                            android.graphics.Color.colorToHSV(colorInt, newHsv)
                            hue = newHsv[0]
                            saturation = newHsv[1]
                            value = newHsv[2]
                            onColorChanged(cleanValue.uppercase())
                        } catch (e: Exception) { }
                    }
                },
                singleLine = true,
                modifier = Modifier.weight(1f)
            )
        }

        // 4. Saved Colors / Dynamic Presets
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text("Saved Colors", style = MaterialTheme.typography.bodyMedium, color = Color.Gray)

            // The new Save Button
            Text(
                text = "+ Add Current",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.Bold,
                modifier = Modifier
                    .clickable { saveColorToPalette() }
                    .padding(vertical = 4.dp, horizontal = 8.dp)
            )
        }

        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            // Renders the dynamic mutable state list
            presetColors.toList().chunked(8).forEach { rowColors ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    rowColors.forEach { colorHex ->
                        Box(
                            modifier = Modifier
                                .size(22.dp)
                                .background(
                                    Color(android.graphics.Color.parseColor(colorHex)),
                                    RoundedCornerShape(4.dp)
                                )
                                .border(1.dp, Color.LightGray, RoundedCornerShape(4.dp))
                                .clickable {
                                    val colorInt = android.graphics.Color.parseColor(colorHex)
                                    val newHsv = FloatArray(3)
                                    android.graphics.Color.colorToHSV(colorInt, newHsv)
                                    hue = newHsv[0]
                                    saturation = newHsv[1]
                                    value = newHsv[2]
                                }
                        )
                    }
                }
            }
        }
    }
}