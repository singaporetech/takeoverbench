"""
sim/constants.py
Centralised constants for TakeoverBench.
All shared magic numbers, timings, and defaults live here — never in application code.
"""

from enum import Enum

# ── MQTT ──
MQTT_TOPIC_PING      = "takeoverbench/ping"
MQTT_TOPIC_TOR_START = "takeoverbench/tor_start"
MQTT_TOPIC_TOR_END   = "takeoverbench/tor_end"
MQTT_TOPIC_HEARTBEAT = "takeoverbench/heartbeat"
MQTT_KEEPALIVE_S = 60

# ── Network / CARLA Connection ──
CARLA_CONNECT_RETRIES = 5
CARLA_CLIENT_TIMEOUT_S = 20.0
CARLA_RETRY_DELAY_S = 5.0
CARLA_MAP_LOAD_WAIT_S = 2.0
PORT_SCAN_MAX_ATTEMPTS = 20
PORT_POLL_INTERVAL_S = 0.2
PORT_WAIT_TIMEOUT_S = 10

# ── HMI ──
HMI_HEARTBEAT_INTERVAL_S = 3
HMI_HEARTBEAT_TIMEOUT_S = 15
HMI_PING_TIMEOUT_S = 15
HMI_ACK_TIMEOUT_S = 5
HMI_TEST_STEP_GAP_S = 5

# ── Experiment Phases ──
class ExperimentPhase(str, Enum):
    IDLE = "idle"
    PROTOCOL = "protocol"
    DONE = "done"

# ── Scenario Defaults ──
# Fire TOR_END slightly before auto-end so HMI returns to idle state
TOR_END_BUFFER_S = 0.5
# End-of-run: brake to a halt before removing the ego vehicle
STOP_SPEED_THRESHOLD_MS = 0.5
STOP_TIMEOUT_S = 4.0

# A sample is flagged as a collision when horizontal acceleration exceeds this.
# Normal driving/braking is well under 10 m/s^2; collision spikes are >100.
COLLISION_ACCEL_THRESHOLD_MS = 30.0
TELEMETRY_INTERVAL_S = 0.033  # ~30 Hz
CONTROLLER_INTERVAL_S = 0.033 # ~30 Hz
SPAWN_RETRY_COUNT = 20

# ── Post-TOR cruise hold ──
# After the TOR the vehicle holds its speed until the driver acts, so the
# scenario cannot be "beaten" by doing nothing. Gains/deadzones below.
CRUISE_KP = 0.15
HUMAN_STEER_DEADZONE = 0.02
HUMAN_THROTTLE_DEADZONE = 0.05
HUMAN_BRAKE_DEADZONE = 0.05

# ── PID Controller ──
# Steering gain — how aggressively to turn toward the next waypoint
PID_KP_STEER = 0.8
# Speed proportional gain
PID_KP_SPEED = 0.15
# Speed integral gain — prevents steady-state speed offset
PID_KI_SPEED = 0.05
# Baseline throttle factor (per m/s of target speed)
PID_THROTTLE_FF_FACTOR = 0.012
# Waypoint look-ahead distance in metres
PID_LOOK_AHEAD_M = 10.0
# If speed exceeds target by more than this (m/s), apply brake
PID_OVERSPEED_BRAKE_THRESHOLD = -3.0
# Emergency full brake if lead vehicle is closer than this
PID_SAFETY_BRAKE_DIST_M = 5.0
# Only trigger safety brake above this speed — avoids false triggers at standstill
PID_SAFETY_BRAKE_MIN_SPEED = 2.0

# ── Camera ──
CAMERA_WIDTH        = 800
CAMERA_HEIGHT       = 450
CAMERA_FOV          = 90
CAMERA_JPEG_QUALITY = 75

# POV camera — driver's eye position (metres relative to vehicle centre)
CAMERA_POV_X = 0.5
CAMERA_POV_Y = 0.0
CAMERA_POV_Z = 1.4

# Chase camera — behind and above the vehicle
CAMERA_CHASE_X      = -20.0
CAMERA_CHASE_Y      = 0.0
CAMERA_CHASE_Z      = 7.0
CAMERA_CHASE_PITCH  = -10

# Spectator initial placement before the follow loop takes over
CAMERA_SPECTATOR_INITIAL_Z      = 5.0
CAMERA_SPECTATOR_INITIAL_PITCH  = -20
