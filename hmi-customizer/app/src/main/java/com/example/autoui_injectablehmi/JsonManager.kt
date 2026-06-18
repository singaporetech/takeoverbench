package com.example.autoui_injectablehmi

import com.example.autoui_injectablehmi.model.AlertBannerSettings
import org.json.JSONObject

object JsonManager {

    // Removed the private currentSettings variable to make this function pure and stateless.
    // Now you just pass the current settings directly when you need the JSON.
    fun buildDesignJson(s: AlertBannerSettings): JSONObject {
        return JSONObject().apply {
            put("visual", JSONObject().apply {
                put("message", s.message)
                put("bg_color", s.backgroundColorHex)
                put("text_color", s.textColorHex)
                put("font_size", s.fontSize)
                put("font_weight", s.fontWeight)
                put("font_style", s.fontStyle)
                put("font_family", s.fontFamily)
                put("blinking", s.isBlinking)
                put("padding", s.padding)
            })

            put("grid", JSONObject().apply {
                put("start_col", s.gridStartCol)
                put("end_col", s.gridEndCol)
                put("start_row", s.gridStartRow)
                put("end_row", s.gridEndRow)
                put("total_cols", s.gridCols)
                put("total_rows", s.gridRows)
            })

            put("overlay", JSONObject().apply {
                put("enabled", s.isOverlayEnabled)
                put("color", s.overlayColorHex)
                put("opacity", s.overlayOpacity)
                put("photo_enabled", s.isOverlayPhotoEnabled)
                put("photo_source", s.overlayPhotoSource)
            })

            put("media", JSONObject().apply {
                put("audio_enabled", s.isAudioEnabled)
                put("audio_source", s.audioSource)
                put("banner_photo_enabled", s.isBannerPhotoEnabled)
                put("banner_photo_source", s.bannerPhotoSource)
            })
        }
    }
}