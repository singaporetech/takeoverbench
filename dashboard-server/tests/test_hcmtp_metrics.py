"""Unit tests for HCMTP raw metric computation.

Each test feeds synthetic telemetry with a hand-computable expected value, so
the metric definitions are pinned by arithmetic rather than by inspection.
Rows include the raw CARLA signals added in the telemetry schema upgrade;
``test_legacy_rows_still_compute`` covers the fallback path for older CSVs.
"""
from __future__ import annotations

import math

from sim.hcmtp import compute_raw_metrics

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


def test_yaw_rate_from_gyro():
    # 0.5 rad/s == 28.648 deg/s
    rows = [row(t, ang_vel_z=0.5) for t in (0.0, 0.1, 0.2)]
    m = compute_raw_metrics(rows, tor_ts=0.0)
    assert m["YRmean"] == round(math.degrees(0.5), 3)


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
    rows = [row(t, lead_long_m=10.0) for t in (0.0, 0.1, 0.2)]
    m = compute_raw_metrics(rows, tor_ts=0.0)
    assert m["MRLD"] == 10.0


def test_dtc_is_distance_at_min_ttc():
    rows = [
        row(0.0, ttc=5.0, lead_long_m=50.0),
        row(0.1, ttc=1.0, lead_long_m=10.0),
        row(0.2, ttc=3.0, lead_long_m=30.0),
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
