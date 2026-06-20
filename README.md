# TakeoverBench

![Python](https://img.shields.io/badge/python-3.10+-blue)
![CARLA](https://img.shields.io/badge/CARLA-0.9.16-blue)
![License](https://img.shields.io/badge/license-TBD-lightgrey)
![Status](https://img.shields.io/badge/status-research--prototype-yellow)

![TakeoverBench rig: CARLA monitor, steering wheel, Android tablet flashing TOR banner](docs/images/hero.jpg)

A benchmarking platform for **Takeover Requests (TOR)** in conditionally automated vehicles. TakeoverBench integrates scenario execution, takeover-alert triggering, HMI prototyping, telemetry capture, hardware-fidelity documentation, and automated report generation into a single, reproducible workflow.

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
- **Predefined Scenario Sets** — Run a complete experiment session with a familiarisation run and multiple experimental takeover conditions. Load a scenario set, press play, and the system handles the entire end-to-end flow: loading the map, spawning vehicles, engaging autopilot, auto-triggering the TOR when the TTC threshold is crossed, and logging telemetry — all without per-run micromanagement.
- **Hardware Fidelity Scoring** — Document your physical simulator setup and get a visual, motion, and physical fidelity score on a 1–5 scale based on this [Fidelity Framework](https://doi.org/10.1016/j.ssci.2019.04.004). The platform automatically flags hardware limitations and warns which metrics may not be reliably computable from your setup.
- **HCMTP-Aligned Telemetry** — Records 41 objective takeover metrics and reduces them to 9 principal performance dimensions using the [Human-Centred Comprehensive Measure of Take-Over Performance](https://doi.org/10.1109/tits.2022.3233623) framework.
- **PDF Reports** — Generate standardised session reports combining scenario parameters, hardware fidelity, and HCMTP component scores.

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
│   │   ├── java/.../          # Kotlin sources (MQTT, screens, UI)
│   │   ├── res/               # Resources (icons, themes, strings)
│   │   │   └── values/strings.xml   # App config (MQTT broker address)
│   └── build.gradle.kts       # Gradle build
├── docs/
│   └── hcmtp-metrics.md       # Full HCMTP metric mapping & PCA weights
└── README.md                  # This file
```

## System Requirements & Installation

TakeoverBench requires a **Windows 10/11** machine capable of running **CARLA 0.9.16**, and an **Android tablet or emulator**. A **Logitech G29** steering wheel is recommended.

Follow the dedicated setup guides for each component:

1. **[Dashboard Server Setup](./dashboard-server/README.md)**
2. **[HMI Customizer Setup](./hmi-customizer/README.md)**

## Running a Demo Session

1. **CARLA and HMI connection** — Launch CARLA and the HMI app on your tablet. Open the dashboard in your browser, press connect, and both components connect automatically.

   <img src="docs/images/setup-connection.gif" alt="Walkthrough: launching CARLA, connecting the HMI, and dashboard connection status" width="800">

2. **Configure fidelity** — Select your hardware setup in the setup wizard. For a basic demo without a wheel, choose **Keyboard** (the system will warn about degraded metrics, which is expected).

   <img src="docs/images/fidelity-keyboard.png" alt="Hardware fidelity checklist — selecting keyboard" width="800">

3. **Load and run a scenario** — Load **Preset 0: Training Familiarisation**, then click Start. The system auto-drives at 60 km/h and triggers the TOR on your tablet when the TTC threshold is crossed.

   <img src="docs/images/dashboard-queue.png" alt="Dashboard showing scenario queue and Start button" width="800">
   <img src="docs/images/hmi-tor-alert.png" alt="Android HMI displaying the takeover alert banner" width="800">

4. **Review results** — When the run ends, download the PDF report showing HCMTP performance scores.

   <img src="docs/images/report-pcs.png" alt="PDF report excerpt with PC scores" width="800">

## Contributing

This is an academic research project. Contributions, bug reports, and feature requests are welcome. Please open an issue or pull request on [GitHub](https://github.com/singaporetech/takeoverbench). For major changes, please open an issue first to discuss what you would like to change.

## License

This project is currently not licensed for public use. A license will be added prior to open-source release.
