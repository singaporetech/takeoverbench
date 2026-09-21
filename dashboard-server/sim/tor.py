"""
sim/tor.py — TOR (Take-Over Request) firing, reaction detection, and TTC.

Manages the TOR lifecycle: auto-fire when TTC drops below threshold,
human-reaction detection (HCMTP-aligned thresholds), and auto-end timers
that trigger scenario cleanup after ``post_tor_drive_s`` seconds.
"""

import logging
import math
import threading
import time
from typing import Any

import carla

from .constants import TOR_END_BUFFER_S
from .state import ctx, state, state_lock

logger = logging.getLogger(__name__)


def fire_tor(ctrl: Any) -> None:
    """Fire the TOR event: disengage autopilot, start auto-end timer."""
    from .mqtt import mqtt_manager

    now = time.time()
    with state_lock:
        state["tor_triggered"]    = True
        state["tor_timestamp"]    = now
        state["autopilot_engaged"] = False
        state["tor_phase"]        = "coasting"
        # Read post_tor_drive_s from the current preset config
        post_tor_drive_s = state["scenario_config"].get("post_tor_drive_s", 10)
        state["tor_countdown_s"]  = post_tor_drive_s

    # Hand over: hold the speed the car had at the TOR until the driver acts,
    # so the scenario cannot be passed by doing nothing. Recorded driver input
    # is reset so the cruise throttle is never read as a reaction.
    veh = ctx["vehicle"]
    cruise_target = None
    if veh is not None:
        try:
            v = veh.get_velocity()
            cruise_target = math.sqrt(v.x**2 + v.y**2 + v.z**2)
            veh.apply_control(carla.VehicleControl(
                steer=0.0,
                throttle=float(getattr(ctrl, "throttle", 0.0)),
                brake=0.0,
                reverse=False,
            ))
        except Exception:
            logger.debug("Could not set up cruise hold at TOR", exc_info=True)

    with state_lock:
        state["cruise_target_ms"] = cruise_target
        state["human_control"] = {"steer": 0.0, "throttle": 0.0, "brake": 0.0}

    logger.info("TOR fired — autopilot disengaged, auto-end in %ss", post_tor_drive_s)

    mqtt_manager.publish_tor_start(
        state.get("run_id"),
        ttc=state.get("latest_telemetry", {}).get("ttc", 0),
    )

    # ── Auto-end timers ──
    # Timer 1: TOR_END at post_tor_drive_s - 0.5s
    # Timer 2: auto-end at post_tor_drive_s (telemetry loop detects)
    tor_end_delay = max(TOR_END_BUFFER_S, post_tor_drive_s - TOR_END_BUFFER_S)

    def _tor_end_now():
        """Fire TOR_END (MQTT + phase) ~0.5s before auto-end."""
        mqtt_manager.publish_tor_end(state.get("run_id"))
        with state_lock:
            if state.get("tor_phase") == "coasting":
                state["tor_phase"] = "tor_end"
                logger.info("TOR_END (phase=tor_end) %ss after TOR", post_tor_drive_s)
            else:
                logger.info("TOR_END skipped (phase=%s)", state.get("tor_phase"))

    def _auto_end_now():
        """Begin the end-of-run stop. Telemetry ends the run once halted."""
        with state_lock:
            if state.get("tor_phase") in ("coasting", "tor_end"):
                state["tor_phase"] = "stopping"
                state["run_stopping"] = True
                state["stop_started_ts"] = time.time()
                state["tor_countdown_s"] = 0
                logger.info("Stopping (%ss after TOR)", post_tor_drive_s)
            else:
                logger.info("Auto-end cancelled (phase=%s)", state.get("tor_phase"))

    logger.info("Starting timers: TOR_END in %.1fs, auto-end in %ss", tor_end_delay, post_tor_drive_s)
    threading.Timer(tor_end_delay, _tor_end_now).start()
    threading.Timer(post_tor_drive_s, _auto_end_now).start()


def calculate_ttc() -> float:
    """Time-to-collision from the longitudinal gap and closing speed.

    Uses the lead vehicle's position projected onto the ego's forward axis
    (not straight-line distance) divided by the closing speed.
    """
    if ctx["vehicle"] is None or ctx["lead_vehicle"] is None:
        return 999.0
    try:
        ego_loc = ctx["vehicle"].get_location()
        lead_loc = ctx["lead_vehicle"].get_location()
        t = ctx["vehicle"].get_transform()
        v = ctx["vehicle"].get_velocity()
        speed = math.sqrt(v.x**2 + v.y**2 + v.z**2)
        if speed < 0.5:
            return 999.0

        yaw = math.radians(t.rotation.yaw)
        rel_x = lead_loc.x - ego_loc.x
        rel_y = lead_loc.y - ego_loc.y
        gap = rel_x * math.cos(yaw) + rel_y * math.sin(yaw)
        if gap <= 0:
            return 999.0

        lead_v = ctx["lead_vehicle"].get_velocity()
        lead_speed = math.sqrt(lead_v.x**2 + lead_v.y**2 + lead_v.z**2)
        closing = speed - lead_speed
        if closing <= 0.1:
            return 999.0
        return round(gap / closing, 2)
    except Exception:
        return 999.0
