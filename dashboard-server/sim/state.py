"""
Shared state and global references for CARLA simulation modules.
"""
import threading
from typing import Any

from sim.constants import ExperimentPhase

state: dict[str, Any] = {
    # ── Connection ──
    "connected": False,
    "available_vehicles": [],

    # ── Scenario lifecycle ──
    "scenario_running": False,
    "recording": False,
    "run_id": None,

    # ── Scenario config ──
    "scenario_config": {
        "map": "Town06",
        "speed_kmh": 90,
        "tor_ttc": 5.0,
        "weather": "ClearNoon",
        "vehicle_id": "vehicle.tesla.model3",
        "camera_mode": "chase",
        "sae_level": "L3",
        "obstacle_distance": 150,
    },

    # ── Telemetry ──
    "latest_telemetry": {},
    "frame_bytes": None,

    # ── TOR state ──
    "tor_triggered": False,
    "tor_timestamp": None,
    "tor_phase": "idle",   # idle / coasting / tor_end / stopping / auto_ended
    "tor_countdown_s": 0,  # seconds remaining on auto-end timer
    "run_stopping": False,  # True while braking to a halt at end of run
    "stop_started_ts": None,

    # ── Teleop / manual control ──
    # True  = PID controller driving (pre-TOR autopilot phase)
    # False = human driving (post-TOR takeover phase)
    "autopilot_engaged": True,

    # ── Hardware fidelity ──
    "hardware_config": {},
    "hardware_locked": False,

    # ── Scenario queue ──
    "preset_queue": [],
    "active_preset_index": 0,
    "active_set_id": None,      # scenario set currently loaded (None = manual)
    "active_set_name": None,    # human-readable set name

    # ── Participant tracking ──
    "participant_id": "",

    # ── Session runs — appended on each end-scenario ──
    "session_runs": [],

    # ── Experiment phase ──
    "experiment_phase": ExperimentPhase.IDLE,

    # ── HMI (Human-Machine Interface) ──
    "hmi_connected": False,
    "hmi_design": {},
    "last_heartbeat_ts": None,
}

state_lock = threading.Lock()

ctx: dict[str, Any] = {
    "client": None,
    "world": None,
    "vehicle": None,
    "lead_vehicle": None,
    "camera": None,
    "spectator_thread": None,
    "control_thread": None,
    "spectator_mode": None,
}
