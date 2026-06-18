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
from .state import state, state_lock, ctx
from .constants import TOR_END_BUFFER_S

logger = logging.getLogger(__name__)

# HCMTP-aligned reaction detection thresholds (Li et al. 2023)
# RTS: 2° at the steering wheel. STEER_MAX_DEG=450° (simulator lock-to-lock),
# so 2/450 = 0.0044 on CARLA's -1..+1 scale.
RTS_THRESHOLD = 0.0044  # steer > 2° (2° / 450° max = 0.0044)
RTB_THRESHOLD = 0.10    # brake pedal > 10%
RTA_THRESHOLD = 0.05    # throttle > 5%

watching_for_reaction: bool = False


def fire_tor(ctrl: Any) -> None:
    """Fire the TOR event: disengage autopilot, start auto-end timer."""
    global watching_for_reaction
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
        # Reset reaction state fields
        state["rts"] = None
        state["rtb"] = None
        state["rta"] = None
        state["reaction_time_s"] = None
        state["reaction_input"] = None

        watching_for_reaction = True
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
        """Trigger auto-end. Telemetry loop detects the phase and handles it."""
        with state_lock:
            if state.get("tor_phase") in ("coasting", "tor_end"):
                state["tor_phase"] = "auto_ended"
                state["tor_countdown_s"] = 0
                logger.info("Auto-end (%ss after TOR)", post_tor_drive_s)
            else:
                logger.info("Auto-end cancelled (phase=%s)", state.get("tor_phase"))

    logger.info("Starting timers: TOR_END in %.1fs, auto-end in %ss", tor_end_delay, post_tor_drive_s)
    threading.Timer(tor_end_delay, _tor_end_now).start()
    threading.Timer(post_tor_drive_s, _auto_end_now).start()


def check_reaction(ctrl: Any) -> None:
    """
    Detect HUMAN input after TOR using a hardware delta.

    Uses a 100ms grace period to let the physical steering wheel/pedals
    sync to CARLA before locking in the baseline resting state.  This
    prevents the \"hardware snap\" where autopilot ghost commands are
    misinterpreted as a human reaction.
    """
    global watching_for_reaction
    now = time.time()

    with state_lock:
        tor_ts = state.get("tor_timestamp", now)
        elapsed = now - tor_ts

        # 1. The 100ms Hardware Sync Window
        # Constantly overwrite the baseline until 100ms has passed.
        if elapsed < 0.100:
            state["human_baseline_steer"] = ctrl.steer
            state["human_baseline_throttle"] = ctrl.throttle
            state["human_baseline_brake"] = ctrl.brake
            return  # skip detection during grace period

        # 2. Physically settled baselines
        baseline_steer    = state.get("human_baseline_steer", 0.0)
        baseline_throttle = state.get("human_baseline_throttle", 0.0)
        baseline_brake    = state.get("human_baseline_brake", 0.0)

        # 3. Independent delta checks
        if state.get("rts") is None and abs(ctrl.steer - baseline_steer) > RTS_THRESHOLD:
            state["rts"] = round(elapsed, 3)

        if state.get("rtb") is None and (ctrl.brake - baseline_brake) > RTB_THRESHOLD:
            state["rtb"] = round(elapsed, 3)

        if state.get("rta") is None and abs(ctrl.throttle - baseline_throttle) > RTA_THRESHOLD:
            state["rta"] = round(elapsed, 3)

        # 4. Global reaction time — locks on the FIRST detected input
        if state.get("reaction_time_s") is None:
            if state.get("rts") is not None:
                state["reaction_time_s"] = state["rts"]
                state["reaction_input"]  = "steer"
            elif state.get("rtb") is not None:
                state["reaction_time_s"] = state["rtb"]
                state["reaction_input"]  = "brake"
            elif state.get("rta") is not None:
                state["reaction_time_s"] = state["rta"]
                state["reaction_input"]  = "throttle"


def calculate_ttc() -> float:
    """Calculate time-to-collision based on current distance and speed."""
    if ctx["vehicle"] is None or ctx["lead_vehicle"] is None:
        return 999.0
    try:
        ego_loc  = ctx["vehicle"].get_location()
        lead_loc = ctx["lead_vehicle"].get_location()
        distance = ego_loc.distance(lead_loc)
        v        = ctx["vehicle"].get_velocity()
        speed    = math.sqrt(v.x**2 + v.y**2 + v.z**2)
        if speed < 0.5:
            return 999.0
        return round(distance / speed, 2)
    except Exception:
        return 999.0
