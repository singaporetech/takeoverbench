# TakeoverBench

**A Research Dashboard for Takeover Requests (TOR) in Conditionally Automated Vehicles**

A lightweight, Flask-based research dashboard that interfaces with the CARLA Simulator. It provides researchers with a standardized environment to design, execute, and record Takeover Request (TOR) scenarios for human-machine interaction (HMI) and automated driving studies.

## Platform

**Runtime: Windows only.** CARLA, MQTT broker, and Flask all run natively on Windows.

## Features

* **Scenario Configuration:** Dynamically configure testing parameters including ego-vehicle speed, Time-To-Collision (TTC) thresholds, obstacle distance, and weather conditions without restarting the simulator.
* **Standardized Environments:** Designed to utilize CARLA's highway environments (e.g., Town06) to ensure consistent, interference-free straightaways for longitudinal takeover metrics.
* **Real-Time Telemetry & Video:** Streams a low-latency MJPEG video feed and 10Hz vehicle telemetry (Speed, Steering, Braking, TTC) directly to the browser dashboard.
* **Hardware Fidelity Scoring:** Built-in configuration checklist to calculate and log the physical setup's fidelity score based on standard dimensions (Visual, Motion, Physical) as defined by Wynne et al. (2019).
* **Automated Data Logging:** Automatically records vehicle states during the scenario and exports the run data to a structured CSV file for post-hoc analysis.
* **MQTT Integration:** Embedded MQTT broker (no external install needed). TOR messages appear in the dashboard Event Log — no separate terminal window needed. External HMI devices can connect to the broker at `127.0.0.1:1883`.

## Prerequisites

* **Windows 10/11** (64-bit)
* **CARLA Simulator:** Version 0.9.16
* **Additional Maps:** The `AdditionalMaps_0.9.16-Windows.zip` package is required to access highway environments (Town06).
* **Python:** 3.7–3.12 (3.13+ NOT supported by CARLA 0.9.16)
  * Install from [python.org/downloads](https://www.python.org/downloads/)
  * During install, keep **"py launcher"** checked (default)

### Python Dependencies

Install the required packages using pip:

```cmd
pip install -e .
```

**CARLA Python API:** The `carla` module is NOT available on PyPI for version 0.9.16. It must be installed from your CARLA installation:

```cmd
pip install C:\CARLA_0.9.16\PythonAPI\carla\dist\carla-0.9.16-cp312-cp312-win_amd64.whl
```

**IMPORTANT:** CARLA 0.9.16 requires **Python 3.7–3.12**. Python 3.13+ is NOT supported. The wheel filename indicates the target Python version (e.g. `cp312` = Python 3.12). Make sure your system Python matches the wheel version.

*(The startup script will attempt to auto-detect and install this. If detection fails, set `CARLA_PYTHON_EGG` in `.env` to the full path of your `.whl` or `.egg` file.)*

## Installation & Setup

### 1. Configure environment

Copy `.env.example` to `.env` and adjust values:

```cmd
copy .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `CARLA_HOST` | `127.0.0.1` | CARLA server address. |
| `CARLA_PORT` | `2000` | CARLA server port. |
| `FLASK_HOST` | `127.0.0.1` | Flask bind address. Set to `0.0.0.0` for LAN access. |
| `FLASK_PORT` | `5000` | Flask port. |
| `MQTT_HOST` | `127.0.0.1` | MQTT broker address. |
| `MQTT_PORT` | `1883` | MQTT broker port. |
| `CARLA_PYTHON_EGG` | *(auto-detect)* | Full path to `carla-*.egg`. Only needed if auto-detect fails. |

### 2. Start CARLA

Launch the CARLA server. Use Vulkan to avoid DirectX 11 memory access violations with RGB camera sensors:

```cmd
CarlaUE4.exe -vulkan
```

### 3. Start the Flask server

```cmd
start_server.bat
```

The script will:
- Activate venv if found
- Install Python dependencies (including embedded MQTT broker)
- Auto-detect and install CARLA Python API if needed
- Start the embedded MQTT broker + Flask server

### 4. Verify connection

Run the smoke test:

```cmd
python test_connection.py
```

Expected output:
```
Connecting to 127.0.0.1:2000
SUCCESS — connected to 127.0.0.1, map: /Game/Carla/Maps/Town06.Town06
```

## Usage

1. Navigate to `http://localhost:5000` in a web browser.
2. Ensure the dashboard indicates **CARLA CONNECTED**.
3. Use the left panel to define the **Scenario Configuration**.
4. Complete the **Hardware Fidelity Checklist** to lock in your physical simulator specifications.
5. Click **Start Scenario**. The server will automatically load the map (if not already loaded), spawn the ego vehicle on a clear highway segment, place the static obstacle vehicle ahead, and engage the autopilot at the target speed.
6. The system will automatically trigger a TOR when the calculated Time-To-Collision (TTC) drops below your configured threshold, broadcasting the event via MQTT. (You may also trigger this manually).
7. Click **End & Save Run** to terminate the scenario, destroy the actors, and save the CSV telemetry log.

## Event Log

The dashboard Event Log panel displays all MQTT messages in real-time, including:
- TOR_START broadcasts (auto-triggered or manual)
- Incoming MQTT messages on `takeoverbench/TOR_START`

No separate `mosquitto_sub` terminal window is needed — everything appears in the same terminal and dashboard.

## Data Output

Telemetry logs are saved automatically in the `\runs` directory. The CSV files are formatted as `run_[UUID]_telemetry.csv` and include the following headers recorded at 10Hz:

`timestamp`, `speed_ms`, `speed_kmh`, `steer`, `throttle`, `brake`, `loc_x`, `loc_y`, `ttc`

## References

* **SAE International.** (2021). *Taxonomy and Definitions for Terms Related to Driving Automation Systems for On-Road Motor Vehicles* (J3016_202104).
* **Wynne, R. A., Beanland, V., & Salmon, P. M.** (2019). Systematic review of driving simulator validation studies. *Ergonomics*, 62(10), 1255–1271.
