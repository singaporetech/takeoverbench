"""
sim/mqtt.py
Unified MQTT manager for TakeoverBench.
Handles broker connection, TOR publish, and HMI message handling.
"""

import json
import logging
import threading
from datetime import datetime
from typing import Callable

import paho.mqtt.client as mqtt

from sim.constants import (
    MQTT_TOPIC_PING,
    MQTT_TOPIC_TOR_START,
    MQTT_TOPIC_TOR_END,
    MQTT_TOPIC_HEARTBEAT,
    MQTT_KEEPALIVE_S,
)

logger = logging.getLogger(__name__)


class MqttManager:
    """Single shared MQTT client for publishing TOR events and receiving HMI messages."""

    def __init__(self) -> None:
        self.client: mqtt.Client | None = None
        self._lock = threading.Lock()

    # ── Connection ────────────────────────────────────────────

    def connect(self, host: str = "127.0.0.1", port: int = 1883) -> bool:
        """Connect to the broker. No-op if already connected. Returns True on success."""
        if self.client is not None:
            return True
        with self._lock:
            if self.client is not None:
                return True
            try:
                c = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
                c.connect(host, port, keepalive=MQTT_KEEPALIVE_S)
                c.loop_start()
                for topic in (
                    MQTT_TOPIC_PING,
                    MQTT_TOPIC_TOR_START,
                    MQTT_TOPIC_TOR_END,
                    MQTT_TOPIC_HEARTBEAT,
                ):
                    c.subscribe(topic)
                self.client = c
                logger.info("Connected to MQTT broker at %s:%s", host, port)
                return True
            except Exception as e:
                logger.warning("MQTT connection failed: %s", e)
                self.client = None
                return False

    def stop(self) -> None:
        """Disconnect the client."""
        if self.client:
            try:
                self.client.disconnect()
            except Exception:
                pass
            self.client = None

    @property
    def available(self) -> bool:
        return bool(self.client) and self.client is not False

    # ── Message handler ───────────────────────────────────────

    def set_message_handler(self, handler: Callable | None) -> None:
        """Set the on_message callback (or clear it with ``None``)."""
        if self.client and handler:
            self.client.on_message = handler

    # ── Publish helpers ────────────────────────────────────────

    def publish_tor_start(self, run_id: str | None,
                          ttc: float = 0.0,
                          extra: dict | None = None) -> None:
        if not self.available:
            return
        payload = {
            "src": "dashboard",
            "type": "tor_start",
            "run_id": run_id or "unknown",
            "ttc": round(ttc, 2),
        }
        if extra:
            payload.update(extra)
        self._publish(MQTT_TOPIC_TOR_START, payload)

    def publish_tor_end(self, run_id: str | None, extra: dict | None = None) -> None:
        if not self.available:
            return
        payload = {
            "src": "dashboard",
            "type": "tor_end",
            "run_id": run_id or "unknown",
        }
        if extra:
            payload.update(extra)
        self._publish(MQTT_TOPIC_TOR_END, payload)

    def publish_ping(self, run_id: str = "test") -> None:
        if not self.available:
            return
        self._publish(MQTT_TOPIC_PING, {
            "src": "dashboard",
            "type": "ping",
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
        })

    def _publish(self, topic: str, payload: dict) -> None:
        try:
            self.client.publish(topic, json.dumps(payload))  # type: ignore
        except Exception:
            logger.debug("MQTT publish to %s failed", topic, exc_info=True)


# Module-level singleton (created by server.py startup)
mqtt_manager = MqttManager()
