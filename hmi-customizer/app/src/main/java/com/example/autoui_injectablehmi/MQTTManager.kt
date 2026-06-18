package com.example.autoui_injectablehmi

import org.eclipse.paho.client.mqttv3.*

object MQTTManager {

    private const val BROKER =
        "tcp://10.200.33.205" +
                ":1883"

    private val client = MqttClient(
        BROKER,
        "AndroidTablet_${System.currentTimeMillis()}",
        null
    )

    private val listeners =
        mutableMapOf<String, MutableList<(String) -> Unit>>()

    fun connect() {
        try {
            if (client.isConnected) return

            val options = MqttConnectOptions().apply {
                isAutomaticReconnect = true
                isCleanSession = true
                connectionTimeout = 10
            }

            client.setCallback(
                object : MqttCallback {

                    override fun connectionLost(cause: Throwable?) {
                        cause?.printStackTrace()
                    }

                    override fun deliveryComplete(token: IMqttDeliveryToken?) {
                    }

                    override fun messageArrived(
                        topic: String?,
                        message: MqttMessage?
                    ) {
                        if (topic == null) return

                        val payload =
                            message?.toString() ?: ""

                        listeners[topic]?.forEach {
                            it(payload)
                        }
                    }
                }
            )

            client.connect(options)

        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    fun subscribe(
        topic: String,
        callback: (String) -> Unit
    ) {

        if (!client.isConnected) return

        listeners.getOrPut(topic) {
            mutableListOf()
        }.add(callback)

        client.subscribe(topic)
    }

    fun publish(
        topic: String,
        message: String
    ) {

        if (!client.isConnected) return

        client.publish(
            topic,
            MqttMessage(
                message.toByteArray()
            )
        )
    }
}