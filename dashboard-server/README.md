# TakeoverBench — Dashboard Server

![Python](https://img.shields.io/badge/python-3.10+-blue)
![CARLA](https://img.shields.io/badge/CARLA-0.9.16-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-lightgrey)

A Flask-based research dashboard for running and evaluating **Takeover Request (TOR)** experiments in conditionally automated vehicles. It interfaces with the CARLA simulator to execute controlled highway scenarios, capture high-resolution telemetry, compute HCMTP performance scores, and generate structured session reports.

## Quick Start

### Prerequisites

- **Windows 10/11** (CARLA requirement)
- **CARLA Simulator 0.9.16** with `AdditionalMaps_0.9.16` (Town06 highway map)
- **Python 3.10–3.12** (CARLA 0.9.16 does not support 3.13+)

### Installation

```bash
cd dashboard-server
pip install -e .
copy .env.example .env     # Edit as needed
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CARLA_HOST` | `127.0.0.1` | CARLA server address |
| `CARLA_PORT` | `2000` | CARLA server port |
| `FLASK_HOST` | `127.0.0.1` | Flask bind address. Set to `0.0.0.0` for LAN access |
| `FLASK_PORT` | `5000` | Flask port |
| `MQTT_HOST` | `127.0.0.1` | MQTT broker address |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `CARLA_PYTHON_EGG` | auto-detect | Full path to CARLA `.whl` or `.egg` (only if auto-detect fails) |

### Running

Start CARLA with Vulkan:

```cmd
CarlaUE4.exe -vulkan
```

Start the dashboard:

```cmd
start_server.bat
```

The script will:
- Activate venv if found
- Install Python dependencies (including embedded MQTT broker)
- Auto-detect and install the CARLA Python API if needed
- Start the embedded MQTT broker and Flask server

Navigate to `http://localhost:5000`.

### Verify Connection

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
2. Complete the **Setup Wizard** — enter participant ID, connect to CARLA, test HMI connection.
3. Complete the **Hardware Fidelity Checklist** to lock in your physical simulator specifications.
4. Load a **Scenario Set** (e.g., "Set A — Standard Protocol" with 6 presets).
5. Click **Start Scenario**. The system auto-loads the map, spawns vehicles, engages autopilot, and triggers the takeover request when the TTC threshold is reached. The run ends automatically.
6. When all scenarios are complete, click **Session Report** to download the PDF.

### Event Log

The dashboard Event Log panel displays all MQTT messages in real-time, including TOR_START broadcasts and incoming messages on `takeoverbench/TOR_START`. No separate terminal window is needed.

## Data Flow

```
Setup → CARLA connected, HMI connected, hardware locked
   │
   v
Load scenario set → queue populated with presets
   │
   v
Start scenario
   ├── Load map, set weather
   ├── Spawn ego vehicle + lead obstacle
   ├── Engage PID autopilot at target speed
   ├── Attach camera (chase or POV)
   ├── Begin telemetry recording (10 Hz)
   │
   v
Telemetry loop (30 Hz tick)
   ├── World tick → spectator update → camera frame
   ├── Poll vehicle state (speed, steer, throttle, brake, TTC)
   ├── If TTC < threshold → fire TOR
   │     ├── Disengage autopilot
   │     ├── Publish TOR_START via MQTT
   │     ├── Detect reaction (steer/brake/throttle)
   │     └── After response window → publish TOR_END
   └── Detect auto-ended → end scenario
         ├── Compute HCMTP raw metrics + PC scores
         ├── Save CSV telemetry log
         ├── Build run summary
         └── Advance to next preset or finish set
   │
   v
Set complete → generate PDF session report
```

## HCMTP Performance Metrics

TakeoverBench implements the **Human-Centred Comprehensive Measure of Take-Over Performance**, which reduces 41 objective takeover metrics into 9 principal components:

| Component | Variance | What It Measures |
|-----------|----------|-----------------|
| PC1 — Lateral Control | - | Steering smoothness and yaw stability |
| PC2 — Longitudinal Brake | — | Braking intensity and consistency |
| PC3 — Distance Security | — | TTC/DTC margins and collision avoidance |
| PC4 — Longitudinal Throttle | — | Throttle smoothness |
| PC5 — Reaction Time | — | Speed of steering/braking/throttle response |
| PC6 — Lateral Fine Control | — | High-frequency yaw and lateral corrections |
| PC7 — Lateral Composite | — | Steering amplitude |
| PC8 — Lane Keeping | — | Lane centre deviation |
| PC9 — Lateral Velocity | — | Side-to-side movement stability |

See [`docs/hcmtp-metrics.md`](../docs/hcmtp-metrics.md) for the full metric definitions, PCA loading weights, and conversion factors.

## Hardware Fidelity Scoring

Before each session, the setup wizard records the physical simulator configuration across three dimensions (based on the Wynne et al. driving simulator fidelity framework):

| Dimension | Options (score 1–5) |
|-----------|-------------------|
| **Visual** | Single screen → Large single → Multi-screen 180° → Multi-screen 270° → Projector 270° |
| **Motion** | None → Partial → Full 6-DOF |
| **Physical** | Keyboard → Wheel only → Wheel + pedals + seat → Partial cab → Full cab |

The platform displays warnings when certain metrics cannot be reliably computed from the selected hardware.

## API Endpoints

| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/` | Redirect to setup or dashboard |
| GET | `/setup` | Hardware setup wizard |
| GET | `/video_feed` | MJPEG camera stream |
| POST | `/connect-carla` | Connect to CARLA simulator |
| POST | `/disconnect-carla` | Disconnect CARLA |
| GET | `/status` | Full server state |
| GET | `/fidelity-rules` | Fidelity scoring rules |
| POST | `/configure-hardware` | Lock hardware configuration |
| POST | `/reset-hardware` | Return to setup |
| GET | `/presets` | List scenario presets |
| GET | `/scenario-sets` | List built-in sets |
| POST | `/load-scenario-set` | Queue a scenario set |
| POST | `/start-scenario` | Begin scenario execution |
| GET | `/download-report` | Generate and download PDF |
| GET | `/api/hmi-status` | HMI connection state |
| POST | `/api/hmi-test` | HMI connection test |
| GET | `/event-log` | Server-side event ring buffer |

## Presets and Scenario Sets

Six built-in presets:

| ID | Name | Speed | TTC | Obstacle Distance | Weather |
|----|------|-------|-----|-------------------|---------|
| 0 | Training Familiarisation | 60 km/h | 3.0s | — | Clear Noon |
| 1 | Easy Highway | 80 km/h | 3.0s | 450m | Clear Noon |
| 2 | Moderate Highway | 90 km/h | 3.0s | 500m | Clear Noon |
| 3 | Hard Highway | 100 km/h | 3.0s | 500m | Clear Noon |
| 4 | Adverse Rain | 80 km/h | 3.0s | 450m | Hard Rain |
| 5 | Adverse Sunset | 80 km/h | 3.0s | 450m | Clear Sunset |

**Set A — Standard Protocol** runs all 6 presets sequentially (~5 minutes total).

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/hcmtp_calibrate.py` | Computes population baseline μ/σ from recorded CSV files for Z-score standardisation |
| `scripts/find_spawns.py` | Visualises CARLA spawn points with numbered markers to select highway positions |
| `scripts/install_carla_api.py` | Installs the CARLA Python API from `.env` path |

## Testing

```bash
pytest tests/
```

- `test_hmi.py` — Simulates a fake HMI device over MQTT to validate the ping/pong handshake, TOR acknowledgement, and heartbeat protocol.
- `test_report.py` — Generates a synthetic PDF report with 5 curated run profiles to verify report formatting and PC marker rendering.
