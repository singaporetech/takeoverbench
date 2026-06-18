#!/usr/bin/env python3
"""
test_hmi.py — Fake HMI app for testing the TakeoverBench HMI handshake.

Usage:
    python test_hmi.py              # connect to localhost:1883
    python test_hmi.py --host 192.168.1.34  # remote broker

What it does:
    - Connects to the MQTT broker
    - Subscribes to all 4 topics (ping, tor_start, tor_end, heartbeat)
    - Responds to each dashboard message automatically:
        ping      → pong + fake design JSON
        tor_start → tor_start_ack
        tor_end   → tor_end_ack
    - Sends heartbeat every 3 seconds
    - Logs all messages to terminal
    - Press Ctrl+C to stop
"""

import argparse
import json
import time
import threading
from datetime import datetime, timezone

TOPICS = ["takeoverbench/ping", "takeoverbench/tor_start",
          "takeoverbench/tor_end", "takeoverbench/heartbeat"]

FAKE_DESIGN = {
    "visual": {
        "bg_color": "#0055ff",
        "text": "TAKE OVER NOW",
        "text_color": "#ffffff"
    },
    "audio": {
        "sound": "alert_tone_1",
        "duration_s": 3.0
    }
}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def on_message(client, userdata, msg):
    """Handle incoming dashboard messages and respond."""
    topic = msg.topic
    try:
        payload = msg.payload.decode("utf-8")
        data = json.loads(payload)
        src = data.get("src", "")
        msg_type = data.get("type", "")

        if src != "dashboard":
            return  # only respond to dashboard messages

        print(f"  ← [{topic}] {payload}")

        if msg_type == "ping":
            # Step 1: Respond with pong + design
            response = {
                "src": "hmi",
                "type": "pong",
                "timestamp": timestamp(),
                "design": FAKE_DESIGN,
            }
            client.publish("takeoverbench/ping", json.dumps(response))
            print(f"  → [takeoverbench/ping] pong + design sent")

        elif msg_type == "tor_start":
            # Step 2: Acknowledge TOR start
            response = {
                "src": "hmi",
                "type": "tor_start_ack",
                "run_id": data.get("run_id", "?"),
                "timestamp": timestamp(),
            }
            client.publish("takeoverbench/tor_start", json.dumps(response))
            print(f"  → [takeoverbench/tor_start] tor_start_ack sent")

        elif msg_type == "tor_end":
            # Step 3: Acknowledge TOR end
            response = {
                "src": "hmi",
                "type": "tor_end_ack",
                "run_id": data.get("run_id", "?"),
                "timestamp": timestamp(),
            }
            client.publish("takeoverbench/tor_end", json.dumps(response))
            print(f"  → [takeoverbench/tor_end] tor_end_ack sent")

        elif msg_type == "heartbeat_ack":
            pass  # dashboard acknowledged our heartbeat, ignore

    except json.JSONDecodeError:
        print(f"  ← [{topic}] (non-JSON) {msg.payload.decode('utf-8', errors='replace')}")
    except Exception as e:
        print(f"  ⚠ Error: {e}")


def heartbeat_loop(client):
    """Send heartbeat every 3 seconds."""
    while True:
        time.sleep(3)
        payload = json.dumps({
            "src": "hmi",
            "type": "heartbeat",
            "timestamp": timestamp(),
        })
        client.publish("takeoverbench/heartbeat", payload)


def main():
    parser = argparse.ArgumentParser(description="Fake HMI app for TakeoverBench")
    parser.add_argument("--host", default="127.0.0.1", help="MQTT broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    args = parser.parse_args()

    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("paho-mqtt not installed. Run: pip install paho-mqtt")
        return

    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = on_message

    print(f"[HMI Test] Connecting to {args.host}:{args.port}...")
    try:
        client.connect(args.host, args.port, keepalive=60)
    except Exception as e:
        print(f"[HMI Test] Connection failed: {e}")
        return

    client.loop_start()

    for topic in TOPICS:
        client.subscribe(topic)
        print(f"[HMI Test] Subscribed to {topic}")

    # Start heartbeat in background thread
    t = threading.Thread(target=heartbeat_loop, args=(client,), daemon=True)
    t.start()
    print(f"[HMI Test] Heartbeat started (every 3s)")
    print(f"[HMI Test] Ready. Waiting for dashboard messages...")
    print(f"  (go to the dashboard and click \"Test HMI Connection\")")
    print()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[HMI Test] Stopping...")
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
