package com.example.autoui_injectablehmi

import android.os.Handler
import android.os.Looper
import com.example.autoui_injectablehmi.viewmodel.DashboardViewModel
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

object NotificationService {

    private val heartbeatHandler = Handler(Looper.getMainLooper())

    private fun timestamp(): String {
        val formatter = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }
        return formatter.format(Date())
    }

    private val heartbeatRunnable = object : Runnable {
        override fun run() {
            val heartbeat = JSONObject().apply {
                put("src", "hmi")
                put("type", "heartbeat")
                put("timestamp", timestamp())
            }

            MQTTManager.publish("takeoverbench/heartbeat", heartbeat.toString())
            heartbeatHandler.postDelayed(this, 3000)
        }
    }

    fun initialise(viewModel: DashboardViewModel) {

        // --- 1. PING -> PONG ---
        MQTTManager.subscribe("takeoverbench/ping") { payload ->
            try {
                val msg = JSONObject(payload)

                // Ignore messages not meant for this block
                if (msg.optString("src") != "dashboard" || msg.optString("type") != "ping") {
                    return@subscribe
                }

                // Construct the Pong response using the dynamic configuration
                val pong = JSONObject().apply {
                    put("src", "hmi")
                    put("type", "pong")
                    put("timestamp", timestamp())

                    // Inject the full configuration object here
                    put("design", JsonManager.buildDesignJson(viewModel.bannerSettings.value))
                }

                MQTTManager.publish("takeoverbench/ping", pong.toString())
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }

        // --- 2. TOR START ---
        MQTTManager.subscribe("takeoverbench/tor_start") { payload ->
            try {
                val msg = JSONObject(payload)

                if (msg.optString("src") != "dashboard" || msg.optString("type") != "tor_start") {
                    return@subscribe
                }

                val runId = msg.optString("run_id")

                // SHOW ALERT ON SCREEN
                viewModel.triggerAlert()

                // SEND ACKNOWLEDGEMENT
                val ack = JSONObject().apply {
                    put("src", "hmi")
                    put("type", "tor_start_ack")
                    put("run_id", runId)
                    put("timestamp", timestamp())
                }

                MQTTManager.publish("takeoverbench/tor_start", ack.toString())
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }

        // --- 3. TOR END ---
        MQTTManager.subscribe("takeoverbench/tor_end") { payload ->
            try {
                val msg = JSONObject(payload)

                if (msg.optString("src") != "dashboard" || msg.optString("type") != "tor_end") {
                    return@subscribe
                }

                val runId = msg.optString("run_id")

                // CLEAR ALERT FROM SCREEN
                viewModel.clearAlert()

                // SEND ACKNOWLEDGEMENT
                val ack = JSONObject().apply {
                    put("src", "hmi")
                    put("type", "tor_end_ack")
                    put("run_id", runId)
                    put("timestamp", timestamp())
                }

                MQTTManager.publish("takeoverbench/tor_end", ack.toString())
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }

        // --- START HEARTBEAT LOOP ---
        heartbeatHandler.post(heartbeatRunnable)
    }
}