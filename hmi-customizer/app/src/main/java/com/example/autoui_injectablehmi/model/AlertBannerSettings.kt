package com.example.autoui_injectablehmi.model

import com.example.autoui_injectablehmi.ui.screens.TextAlignment

data class AlertBannerSettings(
    val message: String = "DRIVER TAKEOVER REQUIRED",
    val backgroundColorHex: String = "#D32F2F", // Default Red
    val textColorHex: String = "#FFFFFF",       // Default White
    val fontSize: Int = 20,

    // 8x6 Grid System Coordinates (0-indexed)
    val gridStartCol: Int = 1,  // e.g., Column 2
    val gridEndCol: Int = 6,    // e.g., Column 7
    val gridStartRow: Int = 2,  // e.g., Row 3
    val gridEndRow: Int = 3,    // e.g., Row 4
    val gridCols: Int = 8,      // Total Columns
    val gridRows: Int = 6,      // Total Rows

    // Background Overlay
    val isOverlayEnabled: Boolean = false,
    val isOverlayPhotoEnabled: Boolean = false, // Background Overlay Photo
    val overlayPhotoSource: String = "",        // Background Overlay Photo URI
    val overlayColorHex: String = "#000000",
    val overlayOpacity: Float = 0.7f,

    // Animation
    val isBlinking: Boolean = false,

    // Typography & Banner Photo
    val fontWeight: String = "Bold",     // "Normal", "Bold", "ExtraBold"
    val fontStyle: String = "Normal",    // "Normal", "Italic"
    val fontFamily: String = "Default",  // "Default", "Monospace", "Serif"
    val padding: Int = 16,
    val isBannerPhotoEnabled: Boolean = false, // Banner Photo
    val bannerPhotoSource: String = "",        // Store Banner Photo URI

    // Audio Alert
    val isAudioEnabled: Boolean = false,
    val audioSource: String = "", // Empty string to store file URI

    val textAlignment: TextAlignment = TextAlignment.CENTER
)