"""Unit tests for HCMTP raw metric computation.

Each test feeds synthetic telemetry with a hand-computable expected value, so
the metric definitions are pinned by arithmetic rather than by inspection.
Rows include the raw CARLA signals added in the telemetry schema upgrade;
``test_legacy_rows_still_compute`` covers the fallback path for older CSVs.
"""
from __future__ import annotations

import math

from sim.hcmtp import ALL_METRICS, Standardizer, compute_pcs, compute_raw_metrics

RAW_KEYS = (
    "vel_x", "vel_y", "vel_z",
    "acc_x", "acc_y", "acc_z",
    "ang_vel_x", "ang_vel_y", "ang_vel_z",
    "lead_long_m", "lead_lat_m", "post_tor",
)


def row(t: float, **kw) -> dict:
    base = {
        "timestamp": t,
        "speed_ms": 20.0,
        "speed_kmh": 72.0,
        "steer": 0.0,
        "throttle": 0.0,
        "brake": 0.0,
        "loc_x": 0.0,
        "loc_y": 0.0,
        "yaw": 0.0,
        "ttc": 999.0,
        "distance_m": 999.0,
        "vel_x": 20.0, "vel_y": 0.0, "vel_z": 0.0,
        "acc_x": 0.0, "acc_y": 0.0, "acc_z": 0.0,
        "ang_vel_x": 0.0, "ang_vel_y": 0.0, "ang_vel_z": 0.0,
        "lead_long_m": 999.0, "lead_lat_m": 999.0,
        "post_tor": 1,
    }
    base.update(kw)
    return base


def test_yaw_angle_relative_to_tor():
    # Constant heading must read as ~0 deviation, not the compass value.
    rows = [row(t, yaw=180.0) for t in (0.0, 0.1, 0.2)]
    m = compute_raw_metrics(rows, tor_ts=0.0)
    assert m["Ymax"] == 0.0
    assert m["Ymean"] == 0.0

    # A 5 degree heading change must read as 5 degrees.
    rows = [row(0.0, yaw=180.0), row(0.1, yaw=182.5), row(0.2, yaw=185.0)]
    m = compute_raw_metrics(rows, tor_ts=0.0)
    assert m["Ymax"] == 5.0


def test_lateral_velocity_projection():
    # Driving straight: zero lateral velocity.
    rows = [row(t, vel_x=20.0, vel_y=0.0) for t in (0.0, 0.1, 0.2)]
    m = compute_raw_metrics(rows, tor_ts=0.0)
    assert m["LaVmean"] == 0.0

    # yaw=0 -> body lateral axis is world +Y, so vel_y=1.0 => 1.0 m/s.
    rows = [row(t, vel_x=20.0, vel_y=1.0) for t in (0.0, 0.1, 0.2)]
    m = compute_raw_metrics(rows, tor_ts=0.0)
    assert m["LaVmean"] == 1.0
    assert m["LaVmax"] == 1.0


def test_yaw_rate_gyro_in_degrees_passes_through():
    # CARLA on this rig reports angular velocity in deg/s. Heading changes
    # 0.5° per 0.1 s = 5 °/s and the gyro agrees, so it must pass through
    # unchanged (regression: it used to be multiplied by 180/π).
    rows = [row(0.0, yaw=0.0, ang_vel_z=5.0),
            row(0.1, yaw=0.5, ang_vel_z=5.0),
            row(0.2, yaw=1.0, ang_vel_z=5.0)]
    m = compute_raw_metrics(rows, tor_ts=0.0)
    assert abs(m["YRmean"] - 5.0) < 1e-6


def test_yaw_rate_gyro_in_radians_is_converted():
    # Same motion, but the gyro reports rad/s (CARLA's documented unit):
    # 5 °/s == 0.0872665 rad/s. The auto-detect must normalise it to 5 °/s.
    rad = math.radians(5.0)
    rows = [row(0.0, yaw=0.0, ang_vel_z=rad),
            row(0.1, yaw=0.5, ang_vel_z=rad),
            row(0.2, yaw=1.0, ang_vel_z=rad)]
    m = compute_raw_metrics(rows, tor_ts=0.0)
    assert abs(m["YRmean"] - 5.0) < 1e-3


def test_lateral_acceleration_projection():
    rows = [row(t, acc_y=2.0) for t in (0.0, 0.1, 0.2)]
    m = compute_raw_metrics(rows, tor_ts=0.0)
    assert m["LaAmax"] == 2.0
    assert m["LaAmean"] == 2.0


def test_longitudinal_acceleration_projection():
    rows = [row(t, acc_x=1.5) for t in (0.0, 0.1, 0.2)]
    m = compute_raw_metrics(rows, tor_ts=0.0)
    assert m["LoAmax"] == 1.5


def test_mrld_uses_longitudinal_distance():
    rows = [row(t, lead_long_m=10.0, lead_lat_m=0.0) for t in (0.0, 0.1, 0.2)]
    m = compute_raw_metrics(rows, tor_ts=0.0)
    assert m["MRLD"] == 10.0


def test_lead_metrics_ignore_other_lane_after_overtake():
    # Lead directly ahead in-lane, then the ego changes lane and passes it.
    # The longitudinal gap crosses zero, but that is a clean overtake, not a
    # near-miss: the lead is now a lane to the side.
    rows = [
        row(0.0, lead_long_m=30.0, lead_lat_m=0.0, ttc=3.0, distance_m=30.0),
        row(0.1, lead_long_m=10.0, lead_lat_m=0.0, ttc=1.0, distance_m=10.0),
        row(0.2, lead_long_m=-5.0, lead_lat_m=-3.5, ttc=999.0, distance_m=6.1),
    ]
    m = compute_raw_metrics(rows, tor_ts=0.0)
    assert m["MRLD"] == 10.0   # closest same-lane approach, not 0
    assert m["TTC"] == 1.0
    assert m["DTC"] == 10.0


def test_lead_metrics_undefined_without_same_lane_lead():
    # Lead never in the ego's lane -> no valid safety metrics (999 sentinel).
    rows = [row(t, lead_long_m=10.0, lead_lat_m=-3.5) for t in (0.0, 0.1, 0.2)]
    m = compute_raw_metrics(rows, tor_ts=0.0)
    assert m["MRLD"] == 999.0
    assert m["TTC"] == 999.0


def test_dtc_is_distance_at_min_ttc():
    rows = [
        row(0.0, ttc=5.0, lead_long_m=50.0, lead_lat_m=0.0),
        row(0.1, ttc=1.0, lead_long_m=10.0, lead_lat_m=0.0),
        row(0.2, ttc=3.0, lead_long_m=30.0, lead_lat_m=0.0),
    ]
    m = compute_raw_metrics(rows, tor_ts=0.0)
    assert m["TTC"] == 1.0
    assert m["DTC"] == 10.0


def test_post_tor_filtering_without_tor_ts():
    rows = [
        row(0.0, post_tor=0, yaw=90.0),
        row(0.1, post_tor=1, yaw=10.0),
        row(0.2, post_tor=1, yaw=10.0),
    ]
    m = compute_raw_metrics(rows, tor_ts=None)
    # Only the two post_tor rows count; yaw reference is the first of those.
    assert m["Ymax"] == 0.0


def test_reaction_uses_absolute_thresholds():
    rows = [
        row(0.0, steer=0.0, brake=0.0, throttle=0.0),
        row(0.1, steer=0.0, brake=0.0, throttle=0.0),
        row(0.2, steer=0.05, brake=0.0, throttle=0.0),  # 22.5 deg > 2 deg
    ]
    m = compute_raw_metrics(rows, tor_ts=0.0)
    assert m["RTS"] == 0.2


def test_reaction_censored_when_no_input():
    # No input at all: censored at the window length, never 0.0 s.
    rows = [row(t) for t in (0.0, 0.1, 0.2)]
    m = compute_raw_metrics(rows, tor_ts=0.0)
    assert m["RTS"] == 0.2
    assert m["RTB"] == 0.2
    assert m["RTA"] == 0.2
    assert m["RT"] == 0.2


def test_rt_is_minimum_of_channels():
    rows = [
        row(0.0),
        row(0.1, brake=0.2),      # RTB = 0.1
        row(0.2, steer=0.05),     # RTS = 0.2
        row(0.3, throttle=0.10),  # RTA = 0.3
    ]
    m = compute_raw_metrics(rows, tor_ts=0.0)
    assert m["RTB"] == 0.1
    assert m["RTS"] == 0.2
    assert m["RTA"] == 0.3
    assert m["RT"] == 0.1


def test_hfcs_pure_band_sine():
    # A pure 0.45 Hz steering oscillation sits inside the 0.3-0.6 Hz band.
    dt = 1.0 / 30.0
    rows = [
        row(i * dt, steer=0.1 * math.sin(2 * math.pi * 0.45 * i * dt))
        for i in range(300)  # 10 s
    ]
    m = compute_raw_metrics(rows, tor_ts=0.0)
    assert m["HFCS"] > 0.8


def test_hfcs_zero_when_no_steering():
    rows = [row(i * 0.033, steer=0.0) for i in range(60)]
    m = compute_raw_metrics(rows, tor_ts=0.0)
    assert m["HFCS"] == 0.0


def test_lane_change_tclc_and_ecl_window():
    import statistics

    offsets = [0.0, 0.0, 0.0, 0.0, 0.0, 1.5, 0.2, -0.1, 0.05, 0.0]
    lanes = [1, 1, 1, 1, 1, 2, 2, 2, 2, 2]
    rows = [
        row(i * 0.1, lane_offset_signed_m=o, lane_id=lane, lane_width_m=3.5)
        for i, (o, lane) in enumerate(zip(offsets, lanes))
    ]
    m = compute_raw_metrics(rows, tor_ts=0.0)
    # Lane change at index 5 (t=0.5), centred in the new lane at index 6 (t=0.6).
    assert m["TCLC"] == 0.1
    # ECL window = offsets from index 6 onward: max |offset| = 0.2.
    assert m["ECLmax"] == 0.2
    assert m["SDLP"] == round(statistics.pstdev(offsets), 3)


def test_standardizer_skips_provenance(tmp_path):
    import json

    from sim.hcmtp import Standardizer

    path = tmp_path / "cal.json"
    path.write_text(json.dumps({
        "1": {
            "name": "Preset 1", "n": 2, "sources": ["s"],
            "means": {"RTS": 1.0}, "stds": {"RTS": 0.5},
        },
        "_provenance": {"commit": "abc", "generated_at": "now"},
    }))
    stdizers = Standardizer.from_file(str(path))
    assert stdizers is not None
    assert set(stdizers) == {"1"}
    assert stdizers["1"].means["RTS"] == 1.0


def test_standardizer_missing_file(tmp_path):
    from sim.hcmtp import Standardizer

    assert Standardizer.from_file(str(tmp_path / "nope.json")) is None


def test_metrics_use_driver_input_not_applied_control():
    # The applied control is full throttle (post-TOR cruise hold), but the
    # driver has not touched anything: reaction must be censored, and the
    # throttle metric must reflect the driver (0), not the cruise throttle.
    rows = [
        row(t, throttle=1.0, human_steer=0.0, human_throttle=0.0, human_brake=0.0)
        for t in (0.0, 0.1, 0.2)
    ]
    m = compute_raw_metrics(rows, tor_ts=0.0)
    assert m["RTA"] == 0.2
    assert m["Thmax"] == 0.0
    assert m["SAmax"] == 0.0


def test_reaction_uses_human_input():
    rows = [
        row(0.0, human_steer=0.0, human_throttle=0.0, human_brake=0.0),
        row(0.1, human_steer=0.05, human_throttle=0.0, human_brake=0.0),
    ]
    m = compute_raw_metrics(rows, tor_ts=0.0)
    assert m["RTS"] == 0.1


def test_legacy_rows_still_compute():
    # Old CSVs have none of the raw signal columns; must not crash.
    legacy = [
        {"timestamp": 0.0, "speed_ms": 20.0, "steer": 0.0, "throttle": 0.0,
         "brake": 0.0, "loc_x": 0.0, "loc_y": 0.0, "yaw": 180.0,
         "ttc": 4.0, "distance_m": 80.0},
        {"timestamp": 0.1, "speed_ms": 20.0, "steer": 0.0, "throttle": 0.0,
         "brake": 0.0, "loc_x": 0.0, "loc_y": 0.0, "yaw": 180.5,
         "ttc": 3.0, "distance_m": 60.0},
    ]
    m = compute_raw_metrics(legacy, tor_ts=0.0)
    assert m["Ymax"] >= 0.0
    assert m["LaVmean"] >= 0.0
    assert m["MRLD"] == 60.0  # falls back to Euclidean distance_m


def _calibrated_standardizer() -> Standardizer:
    st = Standardizer()
    st.means = {k: 0.0 for k in ALL_METRICS}
    st.stds = {k: 1.0 for k in ALL_METRICS}
    st.calibrated = True
    return st


def test_undefined_metrics_do_not_contribute_to_pcs():
    # TTC/DTC/MRLD use 999 as the "undefined" sentinel. Z-scoring it used to
    # give z≈999, so PC3 (TTC 0.517 + DTC 0.497) exploded to ~1000.
    st = _calibrated_standardizer()
    metrics = {k: 0.0 for k in ALL_METRICS}
    metrics["TTC"] = 999.0
    metrics["DTC"] = 999.0
    metrics["MRLD"] = 999.0
    pcs = compute_pcs(metrics, st)
    assert pcs["pc3"] == 0.0


def test_defined_metrics_still_contribute_to_pcs():
    st = _calibrated_standardizer()
    metrics = {k: 0.0 for k in ALL_METRICS}
    metrics["TTC"] = 1.0   # z = 1.0
    metrics["DTC"] = 999.0  # undefined -> skipped
    metrics["MRLD"] = 999.0  # undefined -> skipped
    pcs = compute_pcs(metrics, st)
    assert abs(pcs["pc3"] - 0.517) < 1e-6
