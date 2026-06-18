package com.example.autoui_injectablehmi

import org.eclipse.paho.client.mqttv3.*

object MQTTManager {

    private lateinit var clientId: String
    private var client: MqttClient? = null

    private val listeners =
        mutableMapOf<String, MutableList<(String) -> Unit>>()

    fun connect(brokerUrl: String = "tcp://localhost:1883") {
        try {
            if (client?.isConnected == true) return

            clientId = "AndroidTablet_${System.currentTimeMillis()}"
            client = MqttClient(brokerUrl, clientId, null)

            val options = MqttConnectOptions().apply {
                isAutomaticReconnect = true
                isCleanSession = true
                connectionTimeout = 10
            }

            client?.setCallback(
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

            client?.connect(options)

        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    fun subscribe(
        topic: String,
        callback: (String) -> Unit
    ) {

        val c = client ?: return
        if (!c.isConnected) return

        listeners.getOrPut(topic) {
            mutableListOf()
        }.add(callback)

        c.subscribe(topic)
    }

    fun publish(
        topic: String,
        message: String
    ) {

        val c = client ?: return
        if (!c.isConnected) return

        c.publish(
            topic,
            MqttMessage(
                message.toByteArray()
            )
        )
    }
}