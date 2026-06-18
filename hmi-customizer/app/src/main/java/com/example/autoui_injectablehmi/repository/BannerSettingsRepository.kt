package com.example.autoui_injectablehmi.repository

import android.content.Context
import android.content.SharedPreferences
import com.example.autoui_injectablehmi.model.AlertBannerSettings

class BannerSettingsRepository(context: Context) {
    private val prefs: SharedPreferences = context.getSharedPreferences(
        "tor_banner_prefs",
        Context.MODE_PRIVATE
    )

    // --- Current Active Settings ---
    fun getSettings(): AlertBannerSettings {
        return loadSettingsWithPrefix("")
    }

    fun saveSettings(settings: AlertBannerSettings) {
        saveSettingsWithPrefix("", settings)
    }

    // --- Saved Profiles Management ---
    fun getSavedProfiles(): Map<String, AlertBannerSettings> {
        // Retrieve the list of saved profile names
        val names = prefs.getStringSet("profile_names", emptySet()) ?: emptySet()
        val map = mutableMapOf<String, AlertBannerSettings>()

        for (name in names) {
            // Load the settings using the profile name as a prefix
            map[name] = loadSettingsWithPrefix("prof_${name}_")
        }
        return map
    }

    fun saveProfile(profileName: String, settings: AlertBannerSettings) {
        // Copy the set to avoid a known SharedPreferences bug
        val names = prefs.getStringSet("profile_names", emptySet())?.toMutableSet() ?: mutableSetOf()
        names.add(profileName)

        prefs.edit().putStringSet("profile_names", names).apply()
        saveSettingsWithPrefix("prof_${profileName}_", settings)
    }

    fun deleteProfile(profileName: String) {
        val names = prefs.getStringSet("profile_names", emptySet())?.toMutableSet() ?: mutableSetOf()
        names.remove(profileName)

        prefs.edit().putStringSet("profile_names", names).apply()
    }

    // --- Helper Methods ---
    private fun loadSettingsWithPrefix(prefix: String): AlertBannerSettings {
        return AlertBannerSettings(
            message = prefs.getString("${prefix}message", "DRIVER TAKEOVER REQUIRED") ?: "DRIVER TAKEOVER REQUIRED",
            backgroundColorHex = prefs.getString("${prefix}bg_color", "#D32F2F") ?: "#D32F2F",
            textColorHex = prefs.getString("${prefix}text_color", "#FFFFFF") ?: "#FFFFFF",
            fontSize = prefs.getInt("${prefix}font_size", 20),

            // Grid Settings
            gridStartCol = prefs.getInt("${prefix}grid_start_col", 1),
            gridEndCol = prefs.getInt("${prefix}grid_end_col", 6),
            gridStartRow = prefs.getInt("${prefix}grid_start_row", 2),
            gridEndRow = prefs.getInt("${prefix}grid_end_row", 3),
            gridCols = prefs.getInt("${prefix}grid_cols", 8),
            gridRows = prefs.getInt("${prefix}grid_rows", 6),

            // Background Overlay Settings
            isOverlayEnabled = prefs.getBoolean("${prefix}is_overlay_enabled", false),
            isOverlayPhotoEnabled = prefs.getBoolean("${prefix}is_overlay_photo_enabled", false),
            overlayPhotoSource = prefs.getString("${prefix}overlay_photo_source", "") ?: "",
            overlayColorHex = prefs.getString("${prefix}overlay_color", "#000000") ?: "#000000",
            overlayOpacity = prefs.getFloat("${prefix}overlay_opacity", 0.7f),

            isBlinking = prefs.getBoolean("${prefix}is_blinking", false),
            fontWeight = prefs.getString("${prefix}font_weight", "Bold") ?: "Bold",
            fontStyle = prefs.getString("${prefix}font_style", "Normal") ?: "Normal",
            fontFamily = prefs.getString("${prefix}font_family", "Default") ?: "Default",
            padding = prefs.getInt("${prefix}padding", 16),

            // Banner Photo Elements
            isBannerPhotoEnabled = prefs.getBoolean("${prefix}is_banner_photo_enabled", false),
            bannerPhotoSource = prefs.getString("${prefix}banner_photo_source", "") ?: "",

            // Audio Alert
            isAudioEnabled = prefs.getBoolean("${prefix}is_audio_enabled", false),
            audioSource = prefs.getString("${prefix}audio_source", "") ?: ""
        )
    }

    private fun saveSettingsWithPrefix(prefix: String, settings: AlertBannerSettings) {
        prefs.edit()
            .putString("${prefix}message", settings.message)
            .putString("${prefix}bg_color", settings.backgroundColorHex)
            .putString("${prefix}text_color", settings.textColorHex)
            .putInt("${prefix}font_size", settings.fontSize)

            // Grid Settings
            .putInt("${prefix}grid_start_col", settings.gridStartCol)
            .putInt("${prefix}grid_end_col", settings.gridEndCol)
            .putInt("${prefix}grid_start_row", settings.gridStartRow)
            .putInt("${prefix}grid_end_row", settings.gridEndRow)
            .putInt("${prefix}grid_cols", settings.gridCols)
            .putInt("${prefix}grid_rows", settings.gridRows)

            // Background Overlay Settings
            .putBoolean("${prefix}is_overlay_enabled", settings.isOverlayEnabled)
            .putBoolean("${prefix}is_overlay_photo_enabled", settings.isOverlayPhotoEnabled)
            .putString("${prefix}overlay_photo_source", settings.overlayPhotoSource)
            .putString("${prefix}overlay_color", settings.overlayColorHex)
            .putFloat("${prefix}overlay_opacity", settings.overlayOpacity)

            .putBoolean("${prefix}is_blinking", settings.isBlinking)
            .putString("${prefix}font_weight", settings.fontWeight)
            .putString("${prefix}font_style", settings.fontStyle)
            .putString("${prefix}font_family", settings.fontFamily)
            .putInt("${prefix}padding", settings.padding)

            // Banner Photo Elements
            .putBoolean("${prefix}is_banner_photo_enabled", settings.isBannerPhotoEnabled)
            .putString("${prefix}banner_photo_source", settings.bannerPhotoSource)

            // Audio Alert
            .putBoolean("${prefix}is_audio_enabled", settings.isAudioEnabled)
            .putString("${prefix}audio_source", settings.audioSource)
            .apply()
    }
}