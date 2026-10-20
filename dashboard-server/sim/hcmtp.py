"""
sim/hcmtp.py — HCMTP PC score computation (Li et al. 2023).

Computes the 41 raw objective metrics from CARLA telemetry (post-TOR window)
and applies the PCA loading weights from Li et al. (2023) IEEE TITS Table III
to produce PC1–PC9 scores.

See docs/hcmtp-metrics.md for the full reference, conversion factors, and
confidence levels for each metric.
"""

import logging
from pathlib import Path

import carla
import numpy as np

from .constants import LANE_HALF_WIDTH_M
from .state import ctx

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# Conversion constants
# ═══════════════════════════════════════════════════════════════
# These match docs/hcmtp-metrics.md — adjust per hardware if needed
STEER_MAX_DEG = 450.0       # CARLA steer -1..+1 → degrees
BRAKE_MAX_MPA = 5.0        # CARLA brake 0..1 → MPa
THROTTLE_TO_PCT = 100.0    # CARLA throttle 0..1 → %

# Reaction-time thresholds (Li et al. 2023, Table II) — absolute values
STEER_RT_THRESHOLD_DEG = 2.0   # steering wheel turned more than 2°
BRAKE_RT_THRESHOLD = 0.10      # brake pedal more than 10%
THROTTLE_RT_THRESHOLD = 0.05   # accelerator more than 5%

# Lane-change detection for TCLC / ECL (paper gives one-line definitions)
LANE_CHANGE_CENTER_TOL_M = 0.3   # "centred in the new lane"

# Sentinel written for a metric that is undefined for this run (e.g. TTC with
# no in-lane lead). Values at/above this must never be z-scored or they
# dominate the PC scores.
UNDEFINED_METRIC_MIN = 998.0
# HFCS steering power band (Li et al. 2023, Table II)
HFCS_BAND_HZ = (0.3, 0.6)

# ═══════════════════════════════════════════════════════════════
# PCA loading weights — Li et al. (2023) Table III
# Format: {metric_name: loading_weight}
# ═══════════════════════════════════════════════════════════════
# Source of truth: Li et al. (2023), Table III, p. 4243.
# DOI: 10.1109/TITS.2022.3233623
# IMPORTANT: Table III lists every metric as its OWN row. There are no
# "(incl.)" pairs. Adjacent metrics (e.g. Ymax vs Ymean, YAmax vs YAmean,
# SAmean vs SASD, YRmean vs YRSD, LaVmean vs LaVmax, LaAmean vs LaAmax vs
# LaASD) carry DIFFERENT loadings on DIFFERENT PCs — never copy one onto
# the other. Transcribed 2026-09-21 from the PDF; verify against p. 4243.

PC1_WEIGHTS = {
    "SAmax": -0.267,
    "SASD": -0.381,
    "LaAmax": -0.302,
    "LaASD": -0.351,
    "YRmax": -0.251,
    "YRSD": -0.337,
    "Ymax": -0.299,
    "YSD": -0.290,
    "LaVmax": -0.292,
    "LaVSD": -0.241,
    "YAmean": -0.094,
    "YASD": -0.112,
    "MRLD": 0.004,
    "HFCS": -0.264,
    "TLC": 0.056,
}

PC2_WEIGHTS = {
    "Bmax": -0.428,
    "Bmean": -0.498,
    "BSD": -0.470,
    "RTB": 0.332,
    "RTA": 0.037,
    "RT": 0.012,
    "Ymean": 0.137,
    "YAmean": 0.019,
    "LoAmax": -0.235,
    "LoAmean": 0.016,
    "LoASD": -0.328,
    "MRLD": 0.119,
    "TLC": -0.037,
}

PC3_WEIGHTS = {
    "RTS": 0.214,
    "RTB": 0.115,
    "TTBT": 0.465,
    "Bmean": 0.108,
    "YAmean": -0.095,
    "MRLD": 0.103,
    "TTC": 0.517,
    "DTC": 0.497,
    "TCLC": 0.518,
}

PC4_WEIGHTS = {
    "RTA": -0.336,
    "Thmax": 0.494,
    "Thmean": 0.497,
    "ThSD": 0.279,
    "Ymean": 0.096,
    "LoAmax": 0.028,
    "LoAmean": 0.377,
    "MRLD": 0.156,
}

PC5_WEIGHTS = {
    "RTS": -0.585,
    "RTB": -0.118,
    "RTA": -0.088,
    "RT": -0.537,
    "Ymean": 0.121,
    "LoAmean": -0.064,
    "TLC": -0.574,
}

PC6_WEIGHTS = {
    "SAmean": 0.442,
    "LaAmean": 0.604,
    "YRmean": 0.617,
    "YAmean": 0.243,
    "LoAmax": 0.066,
}

PC7_WEIGHTS = {
    "Ymean": 0.153,
    "MRLD": -0.022,
    "ECLmax": 0.550,
    "ECLmean": 0.657,
    "SDLP": 0.516,
}

PC8_WEIGHTS = {
    "YRmax": -0.103,
    "YAmax": -0.889,
    "YAmean": 0.149,
}

PC9_WEIGHTS = {
    "Ymean": 0.241,
    "LaVmean": -0.871,
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
    def from_file(cls, path: "str | Path | None" = None) -> "dict | None":
        """Load Standardizers from a JSON calibration file.

        ``path`` defaults to ``dashboard-server/calibration.json`` and any
        relative path is resolved against the project root — **not** the
        working directory, so the server behaves the same however it is
        launched.

        Supports both flat (``{"means": ...}``) and per-preset
        (``{"1": {"means": ...}}``) formats. Returns
        ``{preset_id: Standardizer}`` or ``None``.
        """
        import json

        project_root = Path(__file__).resolve().parent.parent
        cal_path = Path(path) if path is not None else project_root / "calibration.json"
        if not cal_path.is_absolute():
            cal_path = project_root / cal_path
        if not cal_path.is_file():
            return None
        try:
            with cal_path.open() as f:
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
                # Per-preset format (skip provenance/metadata entries)
                for preset_id, info in data.items():
                    if not isinstance(info, dict) or "means" not in info or "stds" not in info:
                        continue
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


def _optional_array(rows: list[dict], key: str):
    """Return a float array for *key*, or ``None`` if any row lacks it.

    Used for the raw CARLA signals added in the telemetry schema upgrade;
    returns ``None`` for older CSVs so callers can fall back to the previous
    approximation.
    """
    values = [r.get(key) for r in rows]
    if not values or any(v is None for v in values):
        return None
    try:
        return np.array([float(v) for v in values])
    except (TypeError, ValueError):
        return None


def _detect_lane_change(lane_ids, lane_offsets_abs, n: int):
    """Return ``(start_idx, done_idx)`` for the first lane change, or ``None``.

    A lane change starts at the first sample whose CARLA waypoint ``lane_id``
    differs from the previous sample, and is considered complete when the
    vehicle is back within :data:`LANE_CHANGE_CENTER_TOL_M` of the new lane
    centre. ``lane_ids`` is ``None`` for legacy CSVs (no detection).
    """
    if lane_ids is None or n < 2:
        return None
    start = None
    for i in range(1, n):
        if lane_ids[i] >= 0 and lane_ids[i - 1] >= 0 and lane_ids[i] != lane_ids[i - 1]:
            start = i
            break
    if start is None:
        return None
    for j in range(start, n):
        if abs(lane_offsets_abs[j]) <= LANE_CHANGE_CENTER_TOL_M:
            return (start, j)
    return (start, n - 1)


def compute_raw_metrics(rows: list[dict], tor_ts: float | None) -> dict:
    """Compute the 41 raw objective metrics from telemetry rows.

    Metrics in :attr:`UNCOMPUTABLE` (HFCS, TCLC) are set to 0.0.
    """
    default = get_default_metrics()

    if not rows:
        return default

    # Filter rows after TOR. Prefer the explicit post_tor flag (new schema);
    # fall back to the TOR timestamp (old CSVs / live computation).
    if tor_ts is None:
        post_tor = [r for r in rows if r.get("post_tor")]
    else:
        post_tor = [r for r in rows if r["timestamp"] >= tor_ts]
    if not post_tor:
        return default

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

    # Optional raw CARLA signals (present only in runs recorded after the
    # schema upgrade). ``None`` = old CSV → use the legacy approximation.
    vel_x = _optional_array(post_tor, "vel_x")
    vel_y = _optional_array(post_tor, "vel_y")
    acc_x = _optional_array(post_tor, "acc_x")
    acc_y = _optional_array(post_tor, "acc_y")
    ang_vel_z = _optional_array(post_tor, "ang_vel_z")
    lead_long = _optional_array(post_tor, "lead_long_m")

    # Driver input: use human_* when present (the applied control may be the
    # post-TOR cruise hold). Older CSVs fall back to the applied control.
    human_steer = _optional_array(post_tor, "human_steer")
    human_brake = _optional_array(post_tor, "human_brake")
    human_throttle = _optional_array(post_tor, "human_throttle")
    driver_steer = human_steer if human_steer is not None else steer_norm
    driver_brake = human_brake if human_brake is not None else brake_norm
    driver_throttle = human_throttle if human_throttle is not None else throttle_norm

    # ── Convert to physical units ──
    steer_deg   = driver_steer * STEER_MAX_DEG        # °
    brake_mpa   = driver_brake * BRAKE_MAX_MPA        # MPa
    throttle_pct = driver_throttle * THROTTLE_TO_PCT  # %

    # ── Time derivatives ──
    dt = np.diff(timestamps)
    dt = np.where(dt < 0.001, 0.001, dt)  # avoid div-by-zero

    # Yaw angle relative to the TOR onset (°)
    yaw_unwrapped = np.unwrap(np.radians(yaw_deg)) * (180.0 / np.pi)
    yaw_rel_deg = yaw_unwrapped - yaw_unwrapped[0] if n else np.zeros(n)

    # Yaw rate (°/s) — heading-derived rate is unambiguously °/s.
    yaw_rate_from_yaw = np.zeros(n)
    if n > 1:
        yaw_diff = np.diff(yaw_deg)
        yaw_diff = (yaw_diff + 180) % 360 - 180  # normalise to [-180, 180]
        yaw_rate_from_yaw[1:] = yaw_diff / dt
        yaw_rate_from_yaw[0] = yaw_rate_from_yaw[1]

    # Prefer the gyro (much smoother derivative than differencing a rounded
    # yaw), but its unit is build-dependent: CARLA documents rad/s, yet many
    # builds report deg/s. Rather than assume, compare the gyro magnitude with
    # the heading-derived rate (a factor of 180/π ≈ 57.3 apart) and normalise
    # to °/s. Assuming the wrong unit here inflates every yaw metric ~57×.
    if ang_vel_z is not None:
        gyro = np.asarray(ang_vel_z, dtype=float)
        ref = float(np.median(np.abs(yaw_rate_from_yaw)))
        got = float(np.median(np.abs(gyro)))
        if got > 1e-6 and ref > 1e-6:
            ratio = got / ref
            # ratio ≈ π/180 → gyro is rad/s; ratio ≈ 1 → already deg/s
            if abs(ratio - np.pi / 180.0) < abs(ratio - 1.0):
                yaw_rate_deg_s = gyro * (180.0 / np.pi)
            else:
                yaw_rate_deg_s = gyro
        else:
            yaw_rate_deg_s = gyro
    else:
        yaw_rate_deg_s = yaw_rate_from_yaw

    # Yaw acceleration (°/s²) — derivative of the yaw rate
    yaw_accel_deg_s2 = np.zeros(n)
    if n > 1:
        yaw_accel_deg_s2 = np.gradient(yaw_rate_deg_s, timestamps)

    # Body-frame accelerations (m/s²) and velocities (m/s)
    yaw_rad = np.radians(yaw_deg)
    cos_y, sin_y = np.cos(yaw_rad), np.sin(yaw_rad)

    if acc_x is not None and acc_y is not None:
        acc_fwd = acc_x * cos_y + acc_y * sin_y
        acc_lat = -acc_x * sin_y + acc_y * cos_y
    else:
        # Legacy fallback: differentiate speed; lateral = yaw_rate × speed
        acc_fwd = np.zeros(n)
        if n > 1:
            acc_fwd[1:] = np.diff(speed_ms) / dt
            acc_fwd[0] = acc_fwd[1]
            if n > 5:
                acc_fwd = np.convolve(acc_fwd, np.ones(5) / 5, mode="same")
        acc_lat = np.radians(yaw_rate_deg_s) * speed_ms

    if vel_x is not None and vel_y is not None:
        vel_lat = -vel_x * sin_y + vel_y * cos_y
    else:
        # Legacy fallback: one-tick increment of lateral acceleration
        vel_lat = acc_lat * np.mean(dt) if n > 1 else np.zeros(n)

    # ── Lane-based metrics ──
    # Prefer the geometry stored at record time (reproducible offline); fall
    # back to querying the CARLA map when only loc_x/loc_y are available.
    stored_off = _optional_array(post_tor, "lane_offset_signed_m")
    stored_width = _optional_array(post_tor, "lane_width_m")
    lane_ids = _optional_array(post_tor, "lane_id")

    use_stored = (
        stored_off is not None
        and stored_width is not None
        and bool(np.all(np.abs(stored_off) < 900.0))
        and bool(np.all(np.abs(stored_width) < 900.0))
    )

    if use_stored:
        lane_offsets_signed = stored_off
        lane_widths = [float(w) for w in stored_width]
    else:
        lane_offsets_signed = np.zeros(n)
        lane_widths = []
        carla_map = None
        try:
            carla_map = ctx["world"].get_map()
        except Exception:
            pass
        if carla_map is not None:
            offs: list[float] = []
            for r in post_tor:
                try:
                    loc = carla.Location(x=r.get("loc_x", 0), y=r.get("loc_y", 0))
                    wp = carla_map.get_waypoint(
                        loc, project_to_road=True, lane_type=carla.LaneType.Driving,
                    )
                    if wp:
                        offs.append(float(loc.distance(wp.transform.location)))
                        lane_widths.append(float(wp.lane_width))
                    else:
                        offs.append(0.0)
                        lane_widths.append(3.5)
                except Exception:
                    offs.append(0.0)
                    lane_widths.append(3.5)
            lane_offsets_signed = np.array(offs)
        else:
            lane_widths = [3.5] * n

    lane_offsets = list(np.abs(lane_offsets_signed))
    lane_offsets_arr = np.abs(lane_offsets_signed)

    # ── Metric values ──
    m = get_default_metrics()

    # 1-4. Reaction times — paper Table II absolute thresholds, measured from
    # the TOR. A channel that never crosses is censored at the window length
    # (not 0.0, which would look like an instantaneous reaction).
    t0 = float(tor_ts) if tor_ts is not None else float(timestamps[0])
    window_s = max(0.0, float(timestamps[-1] - t0)) if n else 0.0
    steer_thresh = STEER_RT_THRESHOLD_DEG / STEER_MAX_DEG

    def _first_cross_after_tor(mask: "np.ndarray") -> float:
        hits = np.nonzero(mask)[0]
        return float(timestamps[hits[0]] - t0) if hits.size else window_s

    rts = _first_cross_after_tor(driver_steer > steer_thresh)
    rtb = _first_cross_after_tor(driver_brake > BRAKE_RT_THRESHOLD)
    rta = _first_cross_after_tor(driver_throttle > THROTTLE_RT_THRESHOLD)

    m["RTS"] = round(rts, 3)
    m["RTB"] = round(rtb, 3)
    m["RTA"] = round(rta, 3)
    m["RT"] = round(min(rts, rtb, rta), 3)

    # 5. TTBT — time to lane boundary at TOR moment (first post-TOR row)
    if n > 0 and lane_widths[0] > 0 and abs(vel_lat[0]) > 0.001:
        dist_to_edge = (lane_widths[0] / 2) - lane_offsets[0]
        if dist_to_edge > 0:
            m["TTBT"] = round(dist_to_edge / abs(vel_lat[0]), 3)

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

    # 15-17. Lateral acceleration (measured CARLA acceleration)
    m["LaAmax"] = round(float(np.max(np.abs(acc_lat))), 3)
    m["LaAmean"] = round(float(np.mean(np.abs(acc_lat))), 3)
    m["LaASD"] = round(float(np.std(acc_lat)), 3)

    # 18-20. Yaw rate (measured gyro when available)
    m["YRmax"] = round(float(np.max(np.abs(yaw_rate_deg_s))), 3)
    m["YRmean"] = round(float(np.mean(np.abs(yaw_rate_deg_s))), 3)
    m["YRSD"] = round(float(np.std(yaw_rate_deg_s)), 3)

    # 21-23. Yaw angle relative to the TOR onset
    m["Ymax"] = round(float(np.max(np.abs(yaw_rel_deg))), 3)
    m["Ymean"] = round(float(np.mean(np.abs(yaw_rel_deg))), 3)
    m["YSD"] = round(float(np.std(yaw_rel_deg)), 3)

    # 24-26. Lateral velocity (measured CARLA velocity)
    m["LaVmax"] = round(float(np.max(np.abs(vel_lat))), 3)
    m["LaVmean"] = round(float(np.mean(np.abs(vel_lat))), 3)
    m["LaVSD"] = round(float(np.std(vel_lat)), 3)

    # 27-29. Yaw acceleration
    m["YAmax"] = round(float(np.max(np.abs(yaw_accel_deg_s2))), 3)
    m["YAmean"] = round(float(np.mean(np.abs(yaw_accel_deg_s2))), 3)
    m["YASD"] = round(float(np.std(yaw_accel_deg_s2)), 3)

    # 30-32. Longitudinal acceleration (measured CARLA acceleration)
    m["LoAmax"] = round(float(np.max(np.abs(acc_fwd))), 3)
    m["LoAmean"] = round(float(np.mean(np.abs(acc_fwd))), 3)
    m["LoASD"] = round(float(np.std(acc_fwd)), 3)

    # ── Same-lane gate for the lead-vehicle safety metrics ──
    # MRLD/TTC/DTC are only meaningful while the obstacle is in the ego's lane
    # AND ahead. Once the driver changes lane to pass it, the longitudinal gap
    # crosses zero; without this gate that reads as a phantom near-miss
    # (MRLD≈0, TTC≈0) on a perfectly clean overtake.
    #
    # Primary test: the obstacle is in the ego's own lane/road. Lane identity
    # is curvature-proof, unlike the body-frame lateral offset (a same-lane car
    # a few hundred metres ahead around a bend reads as tens of metres "to the
    # side"). Caveat: CARLA's project_to_road() flips between overlapping road
    # segments on Town06, so the ego's projected lane_id is not perfectly
    # stable — it is still far better than a fixed lateral tolerance, which
    # leaves the curved preset undefined entirely.
    lead_lane_ids = _optional_array(post_tor, "lead_lane_id")
    lead_road_ids = _optional_array(post_tor, "lead_road_id")
    ego_road_ids = _optional_array(post_tor, "road_id")
    lead_lat = _optional_array(post_tor, "lead_lat_m")
    lane_w_arr = _optional_array(post_tor, "lane_width_m")

    # A lane pair is "known" when neither id is the -1 lookup-failure sentinel.
    lane_known = None
    lane_match = None
    if lead_lane_ids is not None and lane_ids is not None:
        lane_known = (lead_lane_ids != -1) & (lane_ids != -1)
        lane_match = lead_lane_ids == lane_ids
        if lead_road_ids is not None and ego_road_ids is not None:
            lane_known = lane_known & (lead_road_ids != -1) & (ego_road_ids != -1)
            lane_match = lane_match & (lead_road_ids == ego_road_ids)

    same_lane = None
    if (
        lead_long is not None
        and lane_known is not None
        and bool(np.any(lane_known))
    ):
        same_lane = lane_match & lane_known & (lead_long > 0)
    elif lead_long is not None and lead_lat is not None:
        # Fallback: no lane identity available (legacy CSV, or every lookup
        # failed) -> use the body-frame lateral offset.
        if lane_w_arr is not None:
            half_lane = np.where(
                np.abs(lane_w_arr) < 900.0,
                np.abs(lane_w_arr) * 0.5,
                LANE_HALF_WIDTH_M,
            )
        else:
            half_lane = np.full(n, LANE_HALF_WIDTH_M)
        same_lane = (np.abs(lead_lat) <= half_lane) & (lead_long > 0)

    # 33. Minimum relative longitudinal distance to the lead vehicle
    if lead_long is not None:
        if same_lane is None:
            # Legacy CSV without lateral info: fall back to the raw minimum.
            m["MRLD"] = round(float(np.min(np.abs(lead_long))), 3)
        elif np.any(same_lane):
            m["MRLD"] = round(float(np.min(lead_long[same_lane])), 3)
        else:
            m["MRLD"] = 999.0  # no same-lane lead ahead after the TOR
    else:
        m["MRLD"] = round(float(np.min(dist_m)), 3)

    # 34. HFCS — steering power in the 0.3-0.6 Hz band / total steering power
    if n >= 8:
        sample_dt = float(np.mean(dt))
        if sample_dt > 0:
            centred = steer_norm - float(np.mean(steer_norm))
            freqs = np.fft.rfftfreq(n, d=sample_dt)
            power = np.abs(np.fft.rfft(centred)) ** 2
            band = (freqs >= HFCS_BAND_HZ[0]) & (freqs <= HFCS_BAND_HZ[1])
            total_power = float(power[1:].sum())  # exclude DC
            if total_power > 0:
                m["HFCS"] = round(float(power[band].sum()) / total_power, 4)

    # 35. TTC (min after TOR, same-lane lead ahead only)
    valid_mask = ttc_vals < 998
    if same_lane is not None:
        valid_mask = valid_mask & same_lane
    valid_ttc = ttc_vals[valid_mask]
    if len(valid_ttc) > 0:
        m["TTC"] = round(float(np.min(valid_ttc)), 3)
        # 36. DTC — distance to the lead at the minimum-TTC sample
        idx = int(np.argmin(np.where(valid_mask, ttc_vals, np.inf)))
        if lead_long is not None:
            m["DTC"] = round(float(lead_long[idx]), 3)
        else:
            m["DTC"] = round(float(dist_m[idx]), 3)
    else:
        m["TTC"] = 999.0
        m["DTC"] = 999.0

    # 37. TLC — min time to lane crossing (dynamic, post-TOR)
    tlc_vals = []
    for i in range(n):
        if lane_widths[i] > 0 and abs(vel_lat[i]) > 0.001:
            dist_to_edge = (lane_widths[i] / 2) - lane_offsets[i]
            if dist_to_edge > 0:
                tlc_vals.append(dist_to_edge / abs(vel_lat[i]))
    m["TLC"] = round(float(min(tlc_vals)), 3) if tlc_vals else 999.0

    # 38-40. Lane change → TCLC and the post-lane-change ECL window
    lc = _detect_lane_change(lane_ids, lane_offsets_arr, n)
    if lc is not None:
        start_i, done_i = lc
        m["TCLC"] = round(float(timestamps[done_i] - timestamps[start_i]), 3)
        ecl_window = lane_offsets_arr[done_i:]
    else:
        # No lane change detected: TCLC is undefined (0) and ECL falls back to
        # the full post-TOR window. Documented in the metric audit.
        m["TCLC"] = 0.0
        ecl_window = lane_offsets_arr
    m["ECLmax"] = round(float(np.max(ecl_window)), 3) if len(ecl_window) else 0.0
    m["ECLmean"] = round(float(np.mean(ecl_window)), 3) if len(ecl_window) else 0.0

    # 41. SDLP — SD of the signed lateral position (relative to lane centre)
    m["SDLP"] = round(float(np.std(lane_offsets_signed)), 3)

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

    # A metric that is undefined for this run (999 sentinel, e.g. TTC with no
    # in-lane lead) must not contribute. Z-scoring the sentinel produces
    # astronomically large scores (z ≈ 10³–10⁴) that swamp every other term.
    undefined = {
        name
        for name, value in raw_metrics.items()
        if value is None or float(value) >= UNDEFINED_METRIC_MIN
    }
    if undefined:
        logger.warning(
            "Undefined metrics excluded from PC scores: %s", sorted(undefined)
        )

    pcs = {}
    for i, weights in enumerate(PC_WEIGHTS, 1):
        total = 0.0
        for name, weight in weights.items():
            if name in undefined:
                continue
            total += weight * metrics.get(name, 0.0)
        pcs[f"pc{i}"] = round(total, 6)

    # Log accuracy warnings for partial PCs
    logger.warning("PC3: partial (~48% accuracy, TCLC=0)")

    return pcs
