# TakeoverBench

![Python](https://img.shields.io/badge/python-3.10+-blue)
![CARLA](https://img.shields.io/badge/CARLA-0.9.16-blue)
![License](https://img.shields.io/badge/license-TBD-lightgrey)
![Status](https://img.shields.io/badge/status-research--prototype-yellow)

A benchmarking platform for **Takeover Requests (TOR)** in automated vehicles. TakeoverBench integrates scenario execution, takeover-alert triggering, HMI prototyping, telemetry capture, hardware-fidelity documentation, and automated report generation into a single, reproducible workflow.

```
┌─────────────────────────────────────────────────────┐
│                     TakeoverBench                   │
│                                                     │
│  ┌──────────────┐   HTTP/WS    ┌─────────────────┐  │
│  │    CARLA     │◄────────────►│  Flask Backend  │  │
│  │  Simulator   │  Python API  │  (Dashboard)    │  │
│  └──────────────┘              └────────┬────────┘  │
│                                         │ MQTT      │
│                                ┌────────▼──────────┐│
│                                │   Android HMI     ││
│                                │  (Configurable)   ││
│                                └───────────────────┘│
└─────────────────────────────────────────────────────┘
```
## Key Features

- **Configurable HMI** — Test takeover-alert concepts on an Android tablet without building a new system for each design. Adjust message, colours, position, images, and audio, and prototype rapidly.
- **Predefined Scenario Sets** — Run a complete experiment session with a familiarisation run and multiple experimental takeover conditions. Load a scenario set, press play, and the system handles the entire end-to-end flow: loading the map, spawning vehicles, engaging autopilot, auto-triggering the TOR when the TTC threshold is crossed, and logging telemetry. All done without per-run micromanagement.
- **Hardware Fidelity Scoring** — Document your physical simulator setup and get a visual, motion, and physical fidelity score on a 1–5 scale based on this [Fidelity Framework](https://doi.org/10.1016/j.ssci.2019.04.004). The platform automatically flags hardware limitations and warns which metrics may not be reliably computable from your setup.
- **HCMTP Metrics** — Records 41 objective takeover metrics and reduces them to 9 principal categories using the [Human-Centred Comprehensive Measure of Take-Over Performance](https://doi.org/10.1109/tits.2022.3233623) framework.
- **PDF Report Generation** — Generate standardised session reports combining scenario parameters, hardware fidelity, and HCMTP component scores.

## Repository Structure

```
takeoverbench/
├── dashboard-server/          # Flask backend + CARLA integration
│   ├── server.py              # Main Flask application
│   ├── sim/                   # Simulation logic (controller, telemetry, HCMTP)
│   ├── static/                # Dashboard frontend (HTML/CSS/JS)
│   ├── templates/             # Jinja2 templates
│   ├── scripts/               # Utility scripts (calibration, spawn finding)
│   ├── tests/                 # Tests
│   └── pyproject.toml         # Python package configuration
├── hmi-customizer/            # Native Android HMI (Jetpack Compose)
│   ├── app/src/main/
│   │   ├── java/.../          # Kotlin sources
│   │   ├── res/               # Resources (icons, themes, strings)
│   │   │   └── values/strings.xml   # App config
│   └── build.gradle.kts       # Gradle build
├── docs/
│   ├── hcmtp-metrics.md       # Full HCMTP metric mapping & PCA weights
│        
└── README.md                  # This file
```

## Quick Start

### Prerequisites

- **Windows 10/11** (CARLA requirement)
- **CARLA Simulator 0.9.16** with `AdditionalMaps_0.9.16` (Town06 highway map)
- **Python 3.10–3.12** (CARLA 0.9.16 does not support 3.13+)
- **Android device or emulator** (API 24+)

### Dashboard Server

```bash
cd dashboard-server
pip install -e .
copy .env.example .env     # Edit as needed
```

Start CARLA with Vulkan:

```cmd
CarlaUE4.exe -vulkan
```

Start the dashboard:

```cmd
start_server.bat
```

Navigate to `http://localhost:5000`.

### HMI Customizer

1. Open `hmi-customizer/` in Android Studio and sync Gradle.
2. Set your MQTT broker address in [`app/src/main/res/values/strings.xml`](./hmi-customizer/app/src/main/res/values/strings.xml) by editing the `default_mqtt_broker` value (default: `tcp://10.200.33.205:1883`).
3. Run on your device or emulator. The app subscribes to takeover events and displays the configured alert banner.

## Contributing

This is an academic research project. Contributions, bug reports, and feature requests are welcome. Please open an issue or pull request on [GitHub](https://github.com/singaporetech/takeoverbench). For major changes, please open an issue first to discuss what you would like to change.

## License

This project is currently not licensed for public use. A license will be added prior to open-source release.
