"""
sim/hcmtp.py — HCMTP PC score computation (Li et al. 2023).

Computes the 41 raw objective metrics from CARLA telemetry (post-TOR window)
and applies the PCA loading weights from Li et al. (2023) IEEE TITS Table III
to produce PC1–PC9 scores.

See docs/hcmtp-metrics.md for the full reference, conversion factors, and
confidence levels for each metric.
"""

import logging
from typing import Any

import carla
import numpy as np

from .state import ctx

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# Conversion constants
# ═══════════════════════════════════════════════════════════════
# These match docs/hcmtp-metrics.md — adjust per hardware if needed
STEER_MAX_DEG = 450.0       # CARLA steer -1..+1 → degrees
BRAKE_MAX_MPA = 5.0        # CARLA brake 0..1 → MPa
THROTTLE_TO_PCT = 100.0    # CARLA throttle 0..1 → %

# ═══════════════════════════════════════════════════════════════
# PCA loading weights — Li et al. (2023) Table III
# Format: {metric_name: loading_weight}
# ═══════════════════════════════════════════════════════════════
# Note: Table III uses "YR" as a truncation of YRmax (confirmed by authors).
# "LaAmax_alone" is a formatting artifact — it is the regular LaAmax.
# See docs/hcmtp-metrics.md for full cross-reference.

PC1_WEIGHTS = {
    "SASD": -0.381, "SAmean": -0.381,
    "LaASD": -0.351, "LaAmax": -0.653,
    "YRSD": -0.337, "YRmean": -0.337,
    "Ymean": -0.299, "Ymax": -0.299,
    "LaVmean": -0.292, "LaVmax": -0.292,
    "YSD": -0.290,
    "SAmax": -0.267,
    "HFCS": -0.264,
    "YRmax": -0.251,
    "LaVSD": -0.241,
    "YASD": -0.112,
    "YAmean": -0.094, "YAmax": -0.094,
    "TLC": 0.056,
    "MRLD": 0.004,
}

PC2_WEIGHTS = {
    "Bmean": -0.498,
    "BSD": -0.470,
    "Bmax": -0.428,
    "LoASD": -0.328,
    "LoAmax": -0.235,
    "RTB": 0.332,
    "Ymean": 0.137, "Ymax": 0.137,
    "MRLD": 0.119,
    "RTA": 0.037,
    "YAmean": 0.019, "YAmax": 0.019,
    "LoAmean": 0.016,
    "RT": 0.012,
    "TLC": -0.037,
}

PC3_WEIGHTS = {
    "TCLC": 0.518,
    "TTC": 0.517,
    "DTC": 0.497,
    "TTBT": 0.465,
    "RTS": 0.214,
    "RTB": 0.115,
    "Bmean": 0.108,
    "MRLD": 0.103,
    "YAmean": -0.095, "YAmax": -0.095,
}

PC4_WEIGHTS = {
    "Thmean": 0.497,
    "Thmax": 0.494,
    "LoAmean": 0.377,
    "ThSD": 0.279,
    "MRLD": 0.156,
    "Ymean": 0.096, "Ymax": 0.096,
    "LoAmax": 0.028,
    "RTA": -0.336,
}

PC5_WEIGHTS = {
    "Ymean": 0.121, "Ymax": 0.121,
    "LoAmean": -0.064,
    "RTA": -0.088,
    "RTB": -0.118,
    "RT": -0.537,
    "TLC": -0.574,
    "RTS": -0.585,
}

PC6_WEIGHTS = {
    "YRSD": 0.617, "YRmean": 0.617,
    "LaASD": 0.604, "LaAmax": 0.604,
    "YAmean": 0.243, "YAmax": 0.243,
    "LoAmax": 0.066,
}

PC7_WEIGHTS = {
    "SASD": 0.442, "SAmean": 0.442,
    "Ymean": 0.153, "Ymax": 0.153,
    "MRLD": -0.022,
}

PC8_WEIGHTS = {
    "ECLmean": 0.657,
    "ECLmax": 0.550,
    "SDLP": 0.516,
    "YRmax": -0.103,
    "YAmean": -0.889, "YAmax": -0.889,
}

PC9_WEIGHTS = {
    "Ymean": 0.241, "Ymax": 0.241,
    "YAmean": 0.149, "YAmax": 0.149,
    "LaVmean": -0.871, "LaVmax": -0.871,
}

PC_WEIGHTS = [PC1_WEIGHTS, PC2_WEIGHTS, PC3_WEIGHTS, PC4_WEIGHTS,
              PC5_WEIGHTS, PC6_WEIGHTS, PC7_WEIGHTS, PC8_WEIGHTS, PC9_WEIGHTS]

# Metrics that cannot be computed yet
# HFCS — needs rolling FFT buffer of steering samples (deferred)
# TCLC — needs lane-change start/end detection (deferred)
UNCOMPUTABLE = {"HFCS", "TCLC"}

# All 41 metric keys, in order
ALL_METRICS = [
    "RTS", "RTB", "RTA", "RT", "TTBT",
    "SAmax", "SAmean", "SASD",
    "Bmax", "Bmean", "BSD",
    "Thmax", "Thmean", "ThSD",
    "LaAmax", "LaAmean", "LaASD",
    "YRmax", "YRmean", "YRSD",
    "Ymax", "Ymean", "YSD",
    "LaVmax", "LaVmean", "LaVSD",
    "YAmax", "YAmean", "YASD",
    "LoAmax", "LoAmean", "LoASD",
    "MRLD", "HFCS",
    "TTC", "DTC",
    "TLC", "TCLC",
    "ECLmax", "ECLmean", "SDLP",
]


class Standardizer:
    """Z-score standardization using a static population baseline.

    Use ``Standardizer.from_file("calibration.json")`` to load
    pre-computed μ/σ per preset.  Returns a dict ``{preset_id: Standardizer}``
    or ``None`` if no file is available.
    """

    def __init__(self):
        self.means: dict[str, float] = {}
        self.stds: dict[str, float] = {}
        self.calibrated = False

    @classmethod
    def from_file(cls, path: str = "calibration.json") -> "dict | None":
        """Load Standardizers from a JSON calibration file.

        Supports both flat (``{"means": ..., "stds": ...}``) and per-preset
        (``{"1": {"means": ..., "stds": ...}}``) formats.

        Returns a dict ``{preset_id: Standardizer}`` or ``None``.
        """
        import json
        import os
        if not os.path.isfile(path):
            return None
        try:
            with open(path) as f:
                data = json.load(f)

            result: dict[str, "Standardizer"] = {}

            # Detect format: flat ({"means":...}) or per-preset ({"1": {"means":...}})
            if "means" in data:
                # Single flat format — back-compat
                obj = cls()
                obj.means = {k: float(v) for k, v in data["means"].items()}
                obj.stds = {k: float(v) for k, v in data["stds"].items()}
                obj.calibrated = True
                result["0"] = obj
            else:
                # Per-preset format
                for preset_id, info in data.items():
                    obj = cls()
                    obj.means = {k: float(v) for k, v in info["means"].items()}
                    obj.stds = {k: float(v) for k, v in info["stds"].items()}
                    obj.calibrated = True
                    result[preset_id] = obj

            return result if result else None
        except Exception:
            return None

    def calibrate(self, raw_metrics_list: list[dict]) -> None:
        """Calibrate using a list of raw metrics dicts from the calibration period."""
        if not raw_metrics_list:
            return

        keys = raw_metrics_list[0].keys()
        MIN_SIGMA = 0.1  # prevents z-score explosions from near-zero autopilot variance
        for key in keys:
            values = [m[key] for m in raw_metrics_list]
            self.means[key] = float(np.mean(values))
            sigma = float(np.std(values))
            self.stds[key] = sigma if sigma > MIN_SIGMA else MIN_SIGMA

        self.calibrated = True

    def z_score(self, metrics: dict) -> dict:
        """Standardize a metrics dict."""
        result = {}
        for key, val in metrics.items():
            mu = self.means.get(key, 0.0)
            sigma = self.stds.get(key, 1.0)
            result[key] = (val - mu) / sigma
        return result


def get_default_metrics() -> dict[str, float]:
    """Return a dict with all 41 metrics set to 0.0."""
    return {k: 0.0 for k in ALL_METRICS}


def compute_raw_metrics(rows: list[dict], tor_ts: float | None) -> dict:
    """Compute the 41 raw objective metrics from telemetry rows.

    Metrics in :attr:`UNCOMPUTABLE` (HFCS, TCLC) are set to 0.0.
    """
    default = get_default_metrics()

    if tor_ts is None or not rows:
        return default

    # Filter rows after TOR
    post_tor = [r for r in rows if r["timestamp"] >= tor_ts]
    if not post_tor:
        return get_default_metrics()

    # ── Extract arrays ──
    n = len(post_tor)
    steer_norm  = np.array([r.get("steer", 0.0) for r in post_tor])
    brake_norm  = np.array([r.get("brake", 0.0) for r in post_tor])
    throttle_norm = np.array([r.get("throttle", 0.0) for r in post_tor])
    speed_ms    = np.array([r.get("speed_ms", 0.0) for r in post_tor])
    ttc_vals    = np.array([r.get("ttc", 999.0) for r in post_tor])
    dist_m      = np.array([r.get("distance_m", 999.0) for r in post_tor])
    timestamps  = np.array([r.get("timestamp", 0.0) for r in post_tor])
    yaw_deg     = np.array([r.get("yaw", 0.0) for r in post_tor])

    # ── Convert to physical units ──
    steer_deg   = steer_norm * STEER_MAX_DEG          # °
    brake_mpa   = brake_norm * BRAKE_MAX_MPA          # MPa
    throttle_pct = throttle_norm * THROTTLE_TO_PCT    # %

    # ── Time derivatives ──
    dt = np.diff(timestamps)
    dt = np.where(dt < 0.001, 0.001, dt)  # avoid div-by-zero

    # Yaw rate (°/s) — first derivative of yaw
    yaw_rate_deg_s = np.zeros(n)
    if n > 1:
        yaw_diff = np.diff(yaw_deg)
        yaw_diff = (yaw_diff + 180) % 360 - 180  # normalise to [-180, 180]
        yaw_rate_deg_s[1:] = yaw_diff / dt
        yaw_rate_deg_s[0] = yaw_rate_deg_s[1]

    # Yaw acceleration (°/s²) — second derivative
    yaw_accel_deg_s2 = np.zeros(n)
    if n > 2:
        yaw_accel_deg_s2[1:-1] = np.diff(yaw_rate_deg_s[1:]) / dt[:-1]
        yaw_accel_deg_s2[0] = yaw_accel_deg_s2[1]
        yaw_accel_deg_s2[-1] = yaw_accel_deg_s2[-2]
        # 5-frame moving average to suppress artificial spikes from tiny dt
        window = min(5, n)
        kernel = np.ones(window) / window
        yaw_accel_deg_s2 = np.convolve(yaw_accel_deg_s2, kernel, mode='same')

    # Longitudinal acceleration (m/s²) — dv/dt
    lo_accel = np.zeros(n)
    if n > 1:
        lo_accel[1:] = np.diff(speed_ms) / dt
        lo_accel[0] = lo_accel[1]
        if n > 5:
            lo_accel = np.convolve(lo_accel, np.ones(5)/5, mode='same')

    # Lateral acceleration — yaw_rate × speed (small-angle approximation)
    yaw_rate_rad = np.radians(yaw_rate_deg_s)
    lat_accel = yaw_rate_rad * speed_ms                # m/s²
    lat_vel = lat_accel * np.mean(dt) if n > 1 else np.zeros(n)  # m/s

    # ── Lane-based metrics ──
    lane_offsets = []
    lane_widths = []
    carla_map = None
    try:
        carla_map = ctx["world"].get_map()
    except Exception:
        pass

    if carla_map is not None:
        for r in post_tor:
            try:
                loc = carla.Location(x=r.get("loc_x", 0), y=r.get("loc_y", 0))
                wp = carla_map.get_waypoint(
                    loc, project_to_road=True, lane_type=carla.LaneType.Driving,
                )
                if wp:
                    offset = loc.distance(wp.transform.location)
                    lane_offsets.append(float(offset))
                    lane_widths.append(float(wp.lane_width))
                else:
                    lane_offsets.append(0.0)
                    lane_widths.append(3.5)
            except Exception:
                lane_offsets.append(0.0)
                lane_widths.append(3.5)
    else:
        lane_offsets = [0.0] * n
        lane_widths = [3.5] * n

    lane_offsets_arr = np.array(lane_offsets)
    lane_widths_arr = np.array(lane_widths)

    # ── Metric values ──
    # Reaction times (from telemetry metadata — already detected by tor.py)
    rt = next((r.get("reaction_time_s", 0) for r in post_tor
              if r.get("reaction_time_s") is not None), 0.0)
    rts = next((r.get("rts", 0) for r in post_tor if r.get("rts") is not None), 0.0)
    rtb = next((r.get("rtb", 0) for r in post_tor if r.get("rtb") is not None), 0.0)
    rta = next((r.get("rta", 0) for r in post_tor if r.get("rta") is not None), 0.0)

    m = get_default_metrics()

    # 1-4. Reaction times
    m["RTS"] = rts
    m["RTB"] = rtb
    m["RTA"] = rta
    m["RT"] = rt

    # 5. TTBT — time to lane boundary at TOR moment (first post-TOR row)
    if n > 0 and lane_widths[0] > 0 and abs(lat_vel[0]) > 0.001:
        dist_to_edge = (lane_widths[0] / 2) - lane_offsets[0]
        if dist_to_edge > 0:
            m["TTBT"] = round(dist_to_edge / abs(lat_vel[0]), 3)

    # 6-8. Steering amplitude
    m["SAmax"] = round(float(np.max(np.abs(steer_deg))), 3)
    m["SAmean"] = round(float(np.mean(np.abs(steer_deg))), 3)
    m["SASD"] = round(float(np.std(steer_deg)), 3)

    # 9-11. Brake pressure
    m["Bmax"] = round(float(np.max(brake_mpa)), 3)
    m["Bmean"] = round(float(np.mean(brake_mpa)), 3)
    m["BSD"] = round(float(np.std(brake_mpa)), 3)

    # 12-14. Throttle
    m["Thmax"] = round(float(np.max(throttle_pct)), 3)
    m["Thmean"] = round(float(np.mean(throttle_pct)), 3)
    m["ThSD"] = round(float(np.std(throttle_pct)), 3)

    # 15-17. Lateral acceleration
    m["LaAmax"] = round(float(np.max(np.abs(lat_accel))), 3)
    m["LaAmean"] = round(float(np.mean(np.abs(lat_accel))), 3)
    m["LaASD"] = round(float(np.std(lat_accel)), 3)

    # 18-20. Yaw rate
    m["YRmax"] = round(float(np.max(np.abs(yaw_rate_deg_s))), 3)
    m["YRmean"] = round(float(np.mean(np.abs(yaw_rate_deg_s))), 3)
    m["YRSD"] = round(float(np.std(yaw_rate_deg_s)), 3)

    # 21-23. Yaw angle (unwrapped to handle -180/180 boundary)
    yaw_unwrapped = np.unwrap(np.radians(yaw_deg)) * (180 / np.pi)
    m["Ymax"] = round(float(np.max(np.abs(yaw_unwrapped))), 3)
    m["Ymean"] = round(float(np.mean(np.abs(yaw_unwrapped))), 3)
    m["YSD"] = round(float(np.std(yaw_unwrapped)), 3)

    # 24-26. Lateral velocity
    m["LaVmax"] = round(float(np.max(np.abs(lat_vel))), 3)
    m["LaVmean"] = round(float(np.mean(np.abs(lat_vel))), 3)
    m["LaVSD"] = round(float(np.std(lat_vel)), 3)

    # 27-29. Yaw acceleration
    m["YAmax"] = round(float(np.max(np.abs(yaw_accel_deg_s2))), 3)
    m["YAmean"] = round(float(np.mean(np.abs(yaw_accel_deg_s2))), 3)
    m["YASD"] = round(float(np.std(yaw_accel_deg_s2)), 3)

    # 30-32. Longitudinal acceleration
    m["LoAmax"] = round(float(np.max(np.abs(lo_accel))), 3)
    m["LoAmean"] = round(float(np.mean(np.abs(lo_accel))), 3)
    m["LoASD"] = round(float(np.std(lo_accel)), 3)

    # 33. Min relative distance
    m["MRLD"] = round(float(np.min(dist_m)), 3)

    # 34. HFCS — deferred (needs rolling FFT buffer)
    m["HFCS"] = 0.0

    # 35. TTC (min after TOR)
    valid_ttc = ttc_vals[ttc_vals < 998]
    m["TTC"] = round(float(np.min(valid_ttc)), 3) if len(valid_ttc) > 0 else 999.0

    # 36. DTC = TTC × speed
    m["DTC"] = round(m["TTC"] * float(np.mean(speed_ms)), 3) if m["TTC"] < 999 else 999.0

    # 37. TLC — min time to lane crossing (dynamic, post-TOR)
    tlc_vals = []
    for i in range(n):
        if lane_widths[i] > 0 and abs(lat_vel[i]) > 0.001:
            dist_to_edge = (lane_widths[i] / 2) - lane_offsets[i]
            if dist_to_edge > 0:
                tlc_vals.append(dist_to_edge / abs(lat_vel[i]))
    m["TLC"] = round(float(min(tlc_vals)), 3) if tlc_vals else 999.0

    # 38. TCLC — deferred (needs lane-change detection)
    m["TCLC"] = 0.0

    # 39-41. Lane centre error and lateral position (approx, waypoint-based)
    m["ECLmax"] = round(float(np.max(lane_offsets_arr)), 3)
    m["ECLmean"] = round(float(np.mean(lane_offsets_arr)), 3)
    m["SDLP"] = round(float(np.std(lane_offsets_arr)), 3)

    return m


def compute_pcs(raw_metrics: dict, standardizer: Standardizer | None = None) -> dict:
    """Compute PC1–PC9 from raw objective metrics.

    If standardizer is provided, z-scores are used. Otherwise raw values
    (not recommended — scores will be in arbitrary units).
    """
    if standardizer and standardizer.calibrated:
        metrics = standardizer.z_score(raw_metrics)
    else:
        metrics = raw_metrics
        logger.warning("No calibration — using raw values. Scores may be unreliable.")

    pcs = {}
    for i, weights in enumerate(PC_WEIGHTS, 1):
        total = 0.0
        for name, weight in weights.items():
            total += weight * metrics.get(name, 0.0)
        pcs[f"pc{i}"] = round(total, 6)

    # Log accuracy warnings for partial PCs
    logger.warning("PC3: partial (~48% accuracy, TCLC=0)")

    return pcs
