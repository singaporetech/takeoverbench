"""
sim/recording.py — Recording control and CSV export for TakeoverBench.

Manages the telemetry row buffer, run lifecycle (start/stop), and CSV
persistence with HCMTP PC-score and raw-metric columns.
"""

import csv
import logging
from typing import Any

import config

from .state import state, state_lock

logger = logging.getLogger(__name__)

telemetry_rows: list[dict[str, Any]] = []


def start_recording(run_id: str):
    """Reset the telemetry buffer and initialise state for a new recording run.

    Clears the row buffer, resets all TOR / reaction-time fields, and
    sets ``autopilot_engaged`` to True.
    """
    global telemetry_rows

    telemetry_rows = []

    with state_lock:
        state["recording"]        = True
        state["run_id"]           = run_id
        state["tor_triggered"]    = False
        state["tor_timestamp"]    = None
        state["tor_phase"]        = "idle"
        state["tor_countdown_s"]  = 0
        state["run_stopping"]     = False
        state["stop_started_ts"]  = None
        state["autopilot_engaged"] = True

    logger.info("Recording started: %s", run_id)


def stop_recording_and_save() -> tuple | None:
    """Stop recording, compute HCMTP PC scores + raw metrics, and save CSV.

    The CSV is saved to ``state["session_dir"]`` (created by
    :func:`config.get_session_dir`) with the filename
    ``{run_number:02d}_{run_id}_telemetry.csv``.

    Returns ``(filepath, pcs)`` on success, ``None`` if no data to save.
    """
    with state_lock:
        state["recording"] = False
        run_id = state["run_id"]
        rows   = list(telemetry_rows)
        tor_ts = state.get("tor_timestamp")

    # Clear the buffer so a subsequent `start_recording()` call starts fresh
    telemetry_rows.clear()

    if not run_id or not rows:
        logger.info("No data to save.")
        return None

    # ── Determine save path (BEFORE PC block — preset_id needed there) ──
    with state_lock:
        session_dir = state.get("session_dir") or config.RUNS_DIR
        run_number = len(state.get("session_runs", [])) + 1
        queue = list(state.get("preset_queue", []))
        preset_idx = state.get("active_preset_index", 0)
        preset_id = queue[preset_idx] if queue and preset_idx < len(queue) else None

    # ── Compute HCMTP raw metrics + PC scores ──
    raw = {}
    pcs = {}
    metric_order: list[str] = []
    try:
        from .hcmtp import ALL_METRICS, compute_pcs, compute_raw_metrics
        raw = compute_raw_metrics(rows, tor_ts)
        from .hcmtp import Standardizer as _Standardizer
        stdizers = _Standardizer.from_file()
        stdizer = (stdizers or {}).get(str(preset_id)) if stdizers else None
        pcs = compute_pcs(raw, standardizer=stdizer)
        if stdizer:
            logger.info("Standardized PC scores (preset %s baseline)", preset_id)
        else:
            logger.info("No calibration.json — using raw scores")
        with state_lock:
            state["last_pc_scores"] = dict(pcs)
        metric_order = [m for m in ALL_METRICS if m in raw]
    except Exception as e:
        logger.warning("PC computation failed: %s", e)

    fname = f"{run_number:02d}_{run_id}_telemetry.csv"
    filepath = session_dir / fname

    # ── CSV columns: telemetry fields + raw metrics + PC scores ──
    fieldnames = ["timestamp", "speed_ms", "speed_kmh",
                  "steer", "throttle", "brake", "loc_x", "loc_y", "yaw",
                  "ttc", "distance_m",
                  # raw CARLA ground-truth signals
                  "vel_x", "vel_y", "vel_z",
                  "acc_x", "acc_y", "acc_z",
                  "ang_vel_x", "ang_vel_y", "ang_vel_z",
                  "lead_long_m", "lead_lat_m",
                  "lane_id", "road_id", "lane_width_m", "lane_offset_signed_m",
                  "post_tor"]

    extra_columns = metric_order + [f"pc{i}" for i in range(1, 10)]

    # ── Build rows with raw metrics + PCs + preset_id ──
    export_rows = list(rows)
    for row in export_rows:
        if raw:
            row.update(raw)
        if pcs:
            row.update(pcs)
        row["preset_id"] = preset_id

    fieldnames_all = fieldnames + ["preset_id"] + extra_columns

    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames_all)
        writer.writeheader()
        writer.writerows(export_rows)

    logger.info("Saved %d rows \u2192 %s", len(rows), filepath)
    return filepath, pcs
