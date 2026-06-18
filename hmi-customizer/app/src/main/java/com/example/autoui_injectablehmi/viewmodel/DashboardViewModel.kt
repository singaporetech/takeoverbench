package com.example.autoui_injectablehmi.viewmodel

import android.app.Application
import android.media.MediaPlayer
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import com.example.autoui_injectablehmi.model.AlertBannerSettings
import com.example.autoui_injectablehmi.repository.BannerSettingsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class DashboardViewModel(application: Application) : AndroidViewModel(application) {

    private val repository = BannerSettingsRepository(application)
    private var mediaPlayer: MediaPlayer? = null // Handles audio playback

    // Current active UI configuration
    private val _bannerSettings = MutableStateFlow(repository.getSettings())
    val bannerSettings: StateFlow<AlertBannerSettings> = _bannerSettings.asStateFlow()

    // Holds the map of all saved custom profiles
    private val _savedProfiles = MutableStateFlow(repository.getSavedProfiles())
    val savedProfiles: StateFlow<Map<String, AlertBannerSettings>> = _savedProfiles.asStateFlow()

    // Holds the visibility state triggered by MQTT
    private val _isAlertVisible = MutableStateFlow(false)
    val isAlertVisible: StateFlow<Boolean> = _isAlertVisible.asStateFlow()

    // --- Active Settings ---
    fun updateSettings(newSettings: AlertBannerSettings) {
        repository.saveSettings(newSettings)
        _bannerSettings.value = newSettings
    }

    // --- Profile Management ---
    fun saveAsProfile(profileName: String, settings: AlertBannerSettings) {
        repository.saveProfile(profileName, settings)
        _savedProfiles.value = repository.getSavedProfiles() // Refresh the map
    }

    fun loadProfile(profileName: String) {
        val loadedSettings = _savedProfiles.value[profileName]
        if (loadedSettings != null) {
            updateSettings(loadedSettings)
        }
    }

    fun deleteProfile(profileName: String) {
        repository.deleteProfile(profileName)
        _savedProfiles.value = repository.getSavedProfiles() // Refresh the map
    }

    // --- MQTT Actions ---
    fun triggerAlert() {
        _isAlertVisible.value = true

        // --- Play Audio Alert if enabled ---
        val settings = _bannerSettings.value
        if (settings.isAudioEnabled && settings.audioSource.isNotBlank()) {
            try {
                mediaPlayer?.release()
                mediaPlayer = MediaPlayer().apply {
                    setDataSource(getApplication(), Uri.parse(settings.audioSource))
                    prepare()
                    isLooping = true // Alert sound loops until cleared
                    start()
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }

    fun clearAlert() {
        _isAlertVisible.value = false

        // --- Stop Audio Alert ---
        try {
            mediaPlayer?.stop()
            mediaPlayer?.release()
            mediaPlayer = null
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }
}