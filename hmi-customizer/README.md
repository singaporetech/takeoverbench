# TakeoverBench — HMI Customizer

![Kotlin](https://img.shields.io/badge/Kotlin-2.0+-blue)
![Compose](https://img.shields.io/badge/Jetpack%20Compose-2024.09-blue)
![MQTT](https://img.shields.io/badge/MQTT-Paho-orange)
![License](https://img.shields.io/badge/license-TBD-lightgrey)

A native Android tablet application for prototyping and testing **takeover alert concepts** in conditionally automated driving studies. The HMI connects to the TakeoverBench dashboard server over MQTT, receives takeover events, and displays fully configurable visual and audio alerts — all without building a new app for each design iteration.

## Quick Start

### Prerequisites

- **Android device or emulator** (API 24+)
- **Android Studio** (latest stable)
- **TakeoverBench Dashboard Server** running with MQTT broker enabled

### Setup

1. Open `hmi-customizer/` in Android Studio and sync Gradle.
2. Configure the MQTT broker address in [`app/src/main/res/values/strings.xml](./app/src/main/res/values/strings.xml):

   ```xml
   <string name="default_mqtt_broker">tcp://YOUR_SERVER_IP:1883</string>
   ```

3. Build and run on your device or tablet.

The app connects to the broker on launch, subscribes to takeover events, and begins sending heartbeat messages.

## MQTT Topics

| Topic | Direction | Purpose |
|-------|-----------|---------|
| `takeoverbench/heartbeat` | HMI → Broker | 3-second keepalive |
| `takeoverbench/ping` | Broker ↔ HMI | Connection test; HMI responds with full design configuration |
| `takeoverbench/tor_start` | Broker → HMI (subscribe), HMI → Broker (publish ack) | Takeover request triggered |
| `takeoverbench/tor_end` | Broker → HMI (subscribe), HMI → Broker (publish ack) | Takeover request cleared |

The HMI responds to pings with a `design` payload containing the full alert configuration — visual settings, grid position, overlay, and media assets.

## Configuration Guide

The settings screen organises all configurable properties into seven panels:

### 0. Saved Profiles
Save the current configuration as a named profile. Load any saved profile from the dropdown. Delete unwanted profiles.

### 1. Content and Animation
Set the takeover alert message, text alignment (left, centre, right), enable flashing animation, and optionally add a banner image.

### 2. Banner Position
An interactive 8×6 grid for placing the banner. Tap to select a single cell or drag to select a range.

### 3. Background Overlay
Toggle screen dimming, adjust opacity, choose an overlay colour, and optionally add a full-screen overlay image.

### 4. Typography
Adjust font size (12–100sp), weight (Normal, Bold, ExtraBold), and style (Normal, Italic).

### 5. Colours
Pick the banner background colour and the alert message text colour using the built-in HSV colour picker.

### 6. Audio Alert
Enable audio playback during takeover events and select an MP3 file from the device. The audio loops while the alert is active.
