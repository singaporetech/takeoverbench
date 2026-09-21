"""
sim/telemetry.py — 10 Hz CARLA telemetry polling loop.

Reads vehicle state from CARLA each tick, dispatches TOR firing and reaction
detection to :mod:`sim.tor`, and records rows via :mod:`sim.recording`.
"""

import logging
import math
import time

import carla

from . import hud as _hud
from .constants import (
    STOP_SPEED_THRESHOLD_MS,
    STOP_TIMEOUT_S,
    TELEMETRY_INTERVAL_S,
    ExperimentPhase,
)
from .state import ctx, state, state_lock
from .summary import build_run_summary

logger = logging.getLogger(__name__)


def telemetry_loop() -> None:
    """Poll CARLA at 10 Hz.  Runs as daemon thread from connection.py."""
    from . import recording as _rec
    from . import tor as _tor

    while True:
        if not state.get("connected"):
            time.sleep(0.05)
            continue

        # ── Auto-end: timer expired, end the scenario ──
        if state.get("tor_phase") == "auto_ended":
            # Capture rows BEFORE end_scenario clears them
            saved_rows = list(_rec.telemetry_rows)
            from .scenario import end_scenario
            try:
                end_scenario()

                # ── Phase transition to protocol ──
                with state_lock:
                    if state.get("experiment_phase") == ExperimentPhase.IDLE:
                        state["experiment_phase"] = ExperimentPhase.PROTOCOL
                        logger.info("First run complete → Protocol ready")

                # ── Capture run summary ──
                rows = saved_rows
                if rows:
                    with state_lock:
                        summary = build_run_summary(
                            rows,
                            run_id=state.get("run_id"),
                            run_number=len(state.get("session_runs", [])) + 1,
                            participant_id=state.get("participant_id", ""),
                            scenario_set=state.get("active_set_name", ""),
                            config=dict(state.get("scenario_config", {})),
                            hardware=dict(state.get("hardware_config", {})),
                            tor_triggered=state.get("tor_triggered", False),
                            pc_scores=state.get("last_pc_scores", {}),
                        )
                    with state_lock:
                        state["session_runs"].append(summary)

                # ── Advance queue to next preset ──
                with state_lock:
                    queue = list(state.get("preset_queue", []))
                    idx = state.get("active_preset_index", 0)
                    new_idx = idx + 1
                    state["active_preset_index"] = new_idx
                    if queue and new_idx < len(queue):
                        from .presets import get_preset, preset_to_scenario_config
                        next_p = get_preset(queue[new_idx])
                        if next_p:
                            state["scenario_config"].update(preset_to_scenario_config(next_p))

                logger.info("Auto-end: run saved, queue advanced")

                # ── Participant-facing message in the CARLA window ──
                if queue and new_idx < len(queue):
                    _hud.set_message("SCENARIO COMPLETE — please wait for the next run")
                elif queue:
                    _hud.set_message("SESSION COMPLETE — thank you for participating")
                else:
                    _hud.set_message("SCENARIO COMPLETE")

                # ── Auto-save PDF if the set is complete ──
                if queue and new_idx >= len(queue) and state.get("active_set_id"):
                    try:
                        from .report import generate_session_report
                        pdf_dir = state.get("session_dir")
                        hw_cfg  = dict(state.get("hardware_config", {}))
                        runs    = list(state.get("session_runs", []))
                        if runs and pdf_dir:
                            generate_session_report(runs, hw_cfg, output_dir=str(pdf_dir))
                            logger.info("Auto-generated session report at end of set")

                        # Clear the queue to signal the set is over — the client will
                        # disable the START SCENARIO button and show an empty queue.
                        state["preset_queue"] = []
                        state["active_preset_index"] = 0
                        state["active_set_id"] = None
                        state["active_set_name"] = None
                    except Exception as pdf_err:
                        logger.error("Auto-PDF generation failed: %s", pdf_err)
            except Exception as e:
                logger.error("Auto-end error: %s", e)
            continue

        # Tick the world to advance simulation (synchronous mode)
        if ctx["world"] is not None and state.get("connected"):
            ctx["world"].tick()

            # Update spectator camera immediately after tick — no thread, no race
            update = ctx.get("spectator_update")
            if update:
                update()

            # Keep the participant-facing message on screen (redrawn each tick)
            _hud.draw(ctx["world"])

        # ── Manual stop (evaluator pressed Stop on the dashboard) ──
        if state.get("manual_stop_requested"):
            with state_lock:
                state["manual_stop_requested"] = False
            try:
                from .scenario import end_scenario
                end_scenario()
                _hud.clear_message()
                logger.info("Scenario stopped manually by evaluator")
            except Exception as e:
                logger.error("Manual stop failed: %s", e)
            continue

        # ── End-of-run stopping: wait for the ego to halt, then finish ──
        if state.get("tor_phase") == "stopping":
            speed_ms = 0.0
            if ctx["vehicle"] is not None:
                try:
                    v = ctx["vehicle"].get_velocity()
                    speed_ms = math.sqrt(v.x**2 + v.y**2 + v.z**2)
                except Exception:
                    speed_ms = 0.0
            started = state.get("stop_started_ts") or time.time()
            if speed_ms < STOP_SPEED_THRESHOLD_MS or (time.time() - started) > STOP_TIMEOUT_S:
                with state_lock:
                    state["run_stopping"] = False
                    state["tor_phase"] = "auto_ended"
            time.sleep(TELEMETRY_INTERVAL_S)
            continue

        if ctx["vehicle"] is not None and state.get("scenario_running"):
            try:
                if not ctx["vehicle"].is_alive:
                    continue

                v         = ctx["vehicle"].get_velocity()
                acc       = ctx["vehicle"].get_acceleration()
                ang_vel   = ctx["vehicle"].get_angular_velocity()
                speed_ms  = math.sqrt(v.x**2 + v.y**2 + v.z**2)
                ctrl      = ctx["vehicle"].get_control()
                loc       = ctx["vehicle"].get_location()
                t         = ctx["vehicle"].get_transform()
                ttc       = _tor.calculate_ttc()

                # Driver input, recorded separately from the applied control so
                # the cruise-hold throttle is never mistaken for a reaction.
                with state_lock:
                    human = dict(state.get("human_control") or {})

                # Relative position of the lead vehicle, projected onto the
                # ego's body axes (forward / lateral). 999 = no lead vehicle.
                dist_m = 999.0
                lead_long_m = 999.0
                lead_lat_m = 999.0
                if ctx["lead_vehicle"]:
                    lead_loc = ctx["lead_vehicle"].get_location()
                    dist_m = loc.distance(lead_loc)
                    rel_x = lead_loc.x - loc.x
                    rel_y = lead_loc.y - loc.y
                    yaw_rad = math.radians(t.rotation.yaw)
                    cos_y, sin_y = math.cos(yaw_rad), math.sin(yaw_rad)
                    lead_long_m = rel_x * cos_y + rel_y * sin_y
                    lead_lat_m = -rel_x * sin_y + rel_y * cos_y

                # Lane geometry, stored so lane metrics are reproducible offline.
                lane_id = -1
                road_id = -1
                lane_width_m = 999.0
                lane_offset_signed_m = 999.0
                if ctx["world"] is not None:
                    try:
                        wp = ctx["world"].get_map().get_waypoint(
                            loc, project_to_road=True, lane_type=carla.LaneType.Driving
                        )
                        if wp is not None:
                            lane_id = int(wp.lane_id)
                            road_id = int(wp.road_id)
                            lane_width_m = round(float(wp.lane_width), 3)
                            wp_yaw = math.radians(wp.transform.rotation.yaw)
                            rel_x = loc.x - wp.transform.location.x
                            rel_y = loc.y - wp.transform.location.y
                            # Signed offset along the lane's right-hand vector.
                            lane_offset_signed_m = round(
                                rel_x * math.sin(wp_yaw) - rel_y * math.cos(wp_yaw), 3
                            )
                    except Exception:
                        logger.debug("Lane waypoint lookup failed", exc_info=True)

                row = {
                    "timestamp": round(time.time(), 3),
                    "speed_ms":  round(speed_ms, 3),
                    "speed_kmh": round(speed_ms * 3.6, 1),
                    "steer":     round(ctrl.steer, 4),
                    "throttle":  round(ctrl.throttle, 4),
                    "brake":     round(ctrl.brake, 4),
                    # ── Driver input (independent of the applied control) ──
                    "human_steer":    round(float(human.get("steer", 0.0)), 4),
                    "human_throttle": round(float(human.get("throttle", 0.0)), 4),
                    "human_brake":    round(float(human.get("brake", 0.0)), 4),
                    "loc_x":     round(loc.x, 2),
                    "loc_y":     round(loc.y, 2),
                    "yaw":       round(t.rotation.yaw, 2),
                    "ttc":       round(ttc, 3),
                    "distance_m": round(dist_m, 2),
                    # ── Raw CARLA ground-truth signals (for paper-exact metrics) ──
                    "vel_x": round(v.x, 3),
                    "vel_y": round(v.y, 3),
                    "vel_z": round(v.z, 3),
                    "acc_x": round(acc.x, 3),
                    "acc_y": round(acc.y, 3),
                    "acc_z": round(acc.z, 3),
                    "ang_vel_x": round(ang_vel.x, 4),
                    "ang_vel_y": round(ang_vel.y, 4),
                    "ang_vel_z": round(ang_vel.z, 4),
                    "lead_long_m": round(lead_long_m, 2),
                    "lead_lat_m": round(lead_lat_m, 2),
                    "lane_id": lane_id,
                    "road_id": road_id,
                    "lane_width_m": lane_width_m,
                    "lane_offset_signed_m": lane_offset_signed_m,
                    "post_tor": 1 if state.get("tor_timestamp") is not None else 0,
                }

                with state_lock:
                    state["latest_telemetry"] = row
                    if state["recording"]:
                        _rec.telemetry_rows.append(dict(row))

                # ── Auto-TOR check ──
                with state_lock:
                    tor_ttc       = state["scenario_config"]["tor_ttc"]
                    already_fired = state["tor_triggered"]

                if not already_fired and ttc < tor_ttc:
                    _tor.fire_tor(ctrl)

                # ── Auto-end countdown — update every telemetry tick ──
                with state_lock:
                    if state.get("tor_phase") == "coasting" and state.get("tor_timestamp"):
                        elapsed = time.time() - state["tor_timestamp"]
                        post_tor_drive = state["scenario_config"].get("post_tor_drive_s", 10)
                        remaining = max(0, round(post_tor_drive - elapsed, 1))
                        state["tor_countdown_s"] = remaining

            except Exception as e:
                logger.warning("Telemetry poll error: %s", e)

        time.sleep(TELEMETRY_INTERVAL_S)
