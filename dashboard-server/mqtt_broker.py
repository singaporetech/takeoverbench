"""
mqtt_broker.py
Embedded MQTT broker — no external Mosquitto install needed.
Auto-fallbacks to next available port if the configured port is blocked.
"""

import asyncio
import logging
import threading
import time
import socket

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MQTT 3.1 (MQIsdp) compatibility patch for amqtt
# amqtt only supports MQTT 3.1.1+ ("MQTT" protocol name), but some
# clients (HMI hardware, older libs) send the MQTT 3.1 protocol name
# "MQIsdp".  This patch normalises the name at parse time.
# ---------------------------------------------------------------------------
_mqtt31_patch_applied = False


def _apply_mqtt31_compat_patch():
    """Monkey-patch amqtt's CONNECT parser to accept MQTT 3.1 clients."""
    global _mqtt31_patch_applied
    if _mqtt31_patch_applied:
        return

    try:
        from amqtt.mqtt.connect import ConnectVariableHeader
    except ImportError:
        logger.warning("Cannot import ConnectVariableHeader — MQTT 3.1 compat patch skipped")
        return

    _original_from_stream = ConnectVariableHeader.from_stream

    @classmethod
    async def _patched_from_stream(cls, reader, fixed_header):
        result = await _original_from_stream(reader, fixed_header)
        if result.proto_name == "MQIsdp":
            logger.info(
                "MQTT 3.1 client detected (protocol name 'MQIsdp') — "
                "normalising to MQTT 3.1.1 ('MQTT')"
            )
            result.proto_name = "MQTT"
        return result

    ConnectVariableHeader.from_stream = _patched_from_stream
    _mqtt31_patch_applied = True
    logger.debug("MQTT 3.1 (MQIsdp) compatibility patch applied")


def _wait_for_port(host, port, timeout=10):
    """Block until the broker port is accepting connections.

    Uses ``127.0.0.1`` to probe even when *host* is ``0.0.0.0``
    (you cannot connect to ``0.0.0.0`` directly).
    """
    probe_host = "127.0.0.1" if host == "0.0.0.0" else host
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((probe_host, port), timeout=1):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.2)
    return False


def _port_is_free(host, port):
    """Check if a port is available for binding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def _find_free_port(host, start_port, max_attempts=20):
    """Find the next available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        if _port_is_free(host, port):
            return port
    return None


def start_broker(host="0.0.0.0", port=1883):
    """Start an embedded MQTT broker in a background daemon thread.

    Returns:
        tuple: (thread, actual_host, actual_port) on success
        None: if the broker failed to start
    """
    try:
        from amqtt.broker import Broker
    except ImportError:
        logger.warning("amqtt not installed — run: pip install amqtt")
        return None

    # Monkey-patch: normalize MQTT 3.1 protocol name "MQIsdp" → "MQTT" (3.1.1)
    # so that older clients (e.g. MQTT 3.1 HMI firmware) can connect.
    _apply_mqtt31_compat_patch()

    # First check if the configured port is available
    actual_port = _find_free_port(host, port)
    if actual_port is None:
        logger.error("No available port found starting from %s:%s", host, port)
        return None

    if actual_port != port:
        logger.info("Port %s is blocked, falling back to %s", port, actual_port)

    async def _run_async(bind_host, bind_port):
        config = {
            "listeners": {
                "default": {
                    "type": "tcp",
                    "bind": f"{bind_host}:{bind_port}",
                }
            },
            "plugins": {
                "amqtt.plugins.authentication.AnonymousAuthPlugin": {
                    "allow_anonymous": True,
                },
            },
        }
        broker = Broker(config)
        await broker.start()
        logger.info("MQTT broker running on %s:%s", bind_host, bind_port)
        while True:
            await asyncio.sleep(3600)

    def _run():
        asyncio.run(_run_async(host, actual_port))

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    if _wait_for_port(host, actual_port):
        logger.info("Ready — accepting connections on %s:%s", host, actual_port)
        return (t, host, actual_port)
    else:
        logger.warning("Broker did not start in time on %s:%s", host, actual_port)
        return None
