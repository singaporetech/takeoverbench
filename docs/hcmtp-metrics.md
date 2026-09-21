# HCMTP Metric Mapping — TakeoverBench

This document describes how TakeoverBench implements the **Human-Centred Comprehensive Measure of Take-Over Performance** (HCMTP) framework to evaluate driver takeover performance in conditionally automated driving scenarios. The system records 41 objective telemetry metrics during each takeover event and reduces them to 9 principal performance components via sparse PCA. This document serves as the reference for how every metric is defined, computed, standardised, and mapped to the final component scores — ensuring consistent, reproducible evaluation of takeover performance across all experimental runs.

---

## 41 Objective Metrics

The 41 metrics, their paper definitions (Table II), how TakeoverBench calculates each one, the assumptions we make, and the current implementation status are all maintained in one generated place:

- **[`hcmtp-metric-calculations.md`](./hcmtp-metric-calculations.md)** — readable per-metric table (generated).
- **[`hcmtp-metric-audit.csv`](./hcmtp-metric-audit.csv)** — the machine-readable source of truth.

The CSV is canonical: to change a metric's definition, assumption, formula, or status, edit the CSV and run:

```bash
python dashboard-server/scripts/generate_hcmtp_doc.py
```

**Current status (from the CSV):** OK 21 · OK-ASSUMED 6 · APPROX 5 · BUG 6 · DEFERRED 2 · DECIDE 1.

### Approximation Notes

- **Steering (SAmax, SAmean, SASD)**: CARLA outputs normalized steer (-1 to +1). Converted via x450° assuming 900° steering wheel lock-to-lock (±450° from center). This matches the HCMTP paper's definition of steering wheel angle (not tire angle). Paper's simulator max angle unknown — 450° is our hardware setting.
- **Brake (Bmax, Bmean, BSD)**: CARLA outputs normalized brake (0 to 1). Converted via x5 MPa assuming 5 MPa max brake pressure. Paper's simulator brake spec unknown.
- **Lane-based (TTBT, TLC, SDLP, ECLmax, ECLmean)**: Computed from CARLA waypoint lane_width and lateral offset from lane center. Offset computed as \|vehicle_pos - waypoint_center\|. Waypoints give the road centerline; real lane center may differ slightly on curved segments.

### Deferred Metrics

- **HFCS (metric 34)**: Requires rolling FFT buffer of steering samples. Implementation deferred.
- **TCLC (metric 38)**: Requires lane change start/end detection (lane_id transitions). Implementation deferred.

**Impact**: PC3 (Distance Security) has reduced accuracy because TCLC is not yet implemented. Once lane-change detection is added, PC3 will be complete. ECLmax/ECLmean/SDLP are now computed via waypoints.

**Note:** Table III lists every metric as its **own row**. It does **not** use "(incl.)" grouping — adjacent metrics such as `Ymax`/`Ymean`, `YAmax`/`YAmean`, `SAmean`/`SASD`, `YRmean`/`YRSD`, and `LaVmean`/`LaVmax` carry **different** loadings on **different** PCs. Never duplicate a loading across a pair.

## PCA Loading Weights

Reference: Li, Q., Wang, Z., Wang, W., Zeng, C., Wu, C., Li, G., Heh, J.-S., & Cheng, B. (2023). A Human-Centered Comprehensive Measure of Take-Over Performance Based on Multiple Objective Metrics. *IEEE Transactions on Intelligent Transportation Systems*, 24(4), 4235–4240.
DOI: 10.1109/TITS.2022.3233623

The 41 objective metrics are reduced to 9 principal components via Sparse Principal Component Analysis (SPCA). The loading weights from Table III (p. 4243) are transcribed below. All 9 components together explain 76.93% of total variance.

> **Implementation status is tracked separately.** The per-metric code-vs-paper audit (definition, unit, source signal, current formula, status, fix) lives in [`hcmtp-metric-audit.csv`](./hcmtp-metric-audit.csv). Many metrics are currently **not** computed per the paper — always check that file before interpreting scores.

### PC1 — Lateral Control (29.92% variance)
| Metric | Loading |
|--------|---------|
| SAmax | -0.267 |
| SASD | -0.381 |
| LaAmax | -0.302 |
| LaASD | -0.351 |
| YRmax | -0.251 |
| YRSD | -0.337 |
| Ymax | -0.299 |
| YSD | -0.290 |
| LaVmax | -0.292 |
| LaVSD | -0.241 |
| YAmean | -0.094 |
| YASD | -0.112 |
| MRLD | 0.004 |
| HFCS | -0.264 |
| TLC | 0.056 |

### PC2 — Longitudinal Control (variance not explicitly given)
| Metric | Loading |
|--------|---------|
| Bmax | -0.428 |
| Bmean | -0.498 |
| BSD | -0.470 |
| RTB | 0.332 |
| RTA | 0.037 |
| RT | 0.012 |
| Ymean | 0.137 |
| YAmean | 0.019 |
| LoAmax | -0.235 |
| LoAmean | 0.016 |
| LoASD | -0.328 |
| MRLD | 0.119 |
| TLC | -0.037 |

### PC3 — Distance Security (variance not explicitly given)
| Metric | Loading |
|--------|---------|
| RTS | 0.214 |
| RTB | 0.115 |
| TTBT | 0.465 |
| Bmean | 0.108 |
| YAmean | -0.095 |
| MRLD | 0.103 |
| TTC | 0.517 |
| DTC | 0.497 |
| TCLC | 0.518 |

### PC4 — Longitudinal Control (variance not explicitly given)
| Metric | Loading |
|--------|---------|
| RTA | -0.336 |
| Thmax | 0.494 |
| Thmean | 0.497 |
| ThSD | 0.279 |
| Ymean | 0.096 |
| LoAmax | 0.028 |
| LoAmean | 0.377 |
| MRLD | 0.156 |

### PC5 — Reaction Time (variance not explicitly given)
| Metric | Loading |
|--------|---------|
| RTS | -0.585 |
| RTB | -0.118 |
| RTA | -0.088 |
| RT | -0.537 |
| Ymean | 0.121 |
| LoAmean | -0.064 |
| TLC | -0.574 |

### PC6 — Lateral Control (variance not explicitly given)
| Metric | Loading |
|--------|---------|
| SAmean | 0.442 |
| LaAmean | 0.604 |
| YRmean | 0.617 |
| YAmean | 0.243 |
| LoAmax | 0.066 |

### PC7 — Lane Keeping (variance not explicitly given)
| Metric | Loading |
|--------|---------|
| Ymean | 0.153 |
| MRLD | -0.022 |
| ECLmax | 0.550 |
| ECLmean | 0.657 |
| SDLP | 0.516 |

### PC8 — Yaw / Lateral (variance not explicitly given)
| Metric | Loading |
|--------|---------|
| YRmax | -0.103 |
| YAmax | -0.889 |
| YAmean | 0.149 |

### PC9 — Lateral Velocity (2.51% variance)
| Metric | Loading |
|--------|---------|
| Ymean | 0.241 |
| LaVmean | -0.871 |

## Conversion Factors

These constants convert CARLA's normalized telemetry values into the physical units used by HCMTP. All constants are documented here so they can be tuned per hardware setup.

> **Intended vs actual:** the Yaw Rate, Lateral Acceleration, Longitudinal Acceleration, and Lateral Velocity rows below describe the **intended** source signals (`get_angular_velocity()`, `get_acceleration()`, `get_velocity()` projections). The current code does **not** use them — it finite-differences yaw/speed and models lateral acceleration as `yaw_rate × speed`. See [`hcmtp-metric-audit.csv`](./hcmtp-metric-audit.csv).

| Metric Group | CARLA Raw | Conversion | Physical Unit | Source |
|---|---|---|---|---|
| Steering (SAmax, SAmean, SASD) | steer (-1 to +1) | x 450° | degrees | Assumes 900° steering wheel lock-to-lock (±450°). SAmax measures steering wheel angle, not tire angle. |
| Brake (Bmax, Bmean, BSD) | brake (0 to 1) | x 5 | MPa | Assumes 5 MPa max brake pressure (typical passenger car) |
| Throttle (Thmax, Thmean, ThSD) | throttle (0 to 1) | x 100 | % | Direct percentage of pedal travel |
| Yaw Rate (YR) | get_angular_velocity().z | — | °/s | Direct from CARLA |
| Lateral Acceleration (LaA) | get_acceleration() projected onto lateral axis | — | m/s² | Vector projection using vehicle yaw |
| Longitudinal Acceleration (LoA) | get_acceleration() projected onto forward axis | — | m/s² | Vector projection using vehicle yaw |
| Lateral Velocity (LaV) | get_velocity() projected onto lateral axis | — | m/s | Vector projection using vehicle yaw |
| Lane Offset (ECLmax, ECLmean, SDLP) | waypoint.transform.location vs vehicle location | — | m | \|vehicle_pos - waypoint_center\|. Requires CARLA map with lane data. |
| Lane Width (TLC, TTBT) | waypoint.lane_width | — | m | Used to compute distance_to_edge = (lane_width/2) - offset. |
| Time to Lane Crossing (TLC) | distance_to_edge / lateral_velocity | — | s | Dynamic: tracked continuously post-TOR. TTBT is the snapshot at t=0. |

## Standardization (Z-Score)

Before the PCA loading weights are applied, each of the 41 raw metrics MUST be standardized using the formula:

$$Z = \frac{X - \mu}{\sigma}$$

Where:
- X = the raw metric value (in degrees, MPa, %, seconds, etc.)
- μ (mu) = the mean of that metric across the baseline dataset
- σ (sigma) = the standard deviation of that metric across the baseline dataset

**Calibration Phase:** The calibration relies on a static baseline dataset, NOT an autopilot pre-window. The research team must record a sample of valid human take-overs (e.g., repeating the scenario 20–30 times). The global mean ($\mu$) and standard deviation ($\sigma$) for each metric are calculated across this entire population dataset, establishing the baseline of an "average human take-over."

If a metric has σ near zero across the dataset, a σ floor of 0.1 or 1% of the metric's range is used to prevent division-by-zero explosions.

**Failure to standardize will result in PC scores in the hundreds — the values will be meaningless.**

## Reaction Time Thresholds

> **Status: BUG.** The paper defines absolute thresholds. The current `_check_reaction()` (`sim/tor.py:106-125`) instead measures the *delta from a 100 ms post-TOR baseline*, to avoid counting residual autopilot input. That is not the paper's definition. Planned fix: detect the paper's absolute thresholds (steer > 2°, brake > 10%, throttle > 5°) and handle the autopilot residual explicitly (e.g. zero the vehicle control at TOR).

| Metric | Paper definition | Current code | Notes |
|---|---|---|---|
| RTS | steer > 2° (absolute) | delta from baseline > 0.0044 | 2° / 450° = 0.0044; the ×450° conversion is assumed. |
| RTB | brake > 10% (absolute) | delta from baseline > 0.10 | |
| RTA | throttle > 5% (absolute) | delta from baseline > 0.05 | |
| RT | min(RTS, RTB, RTA) | first detected input | Missing inputs not handled. |

## Unified HCMTP Score (Future Work)

The final HCMTP 0–10 unified score requires:
1. **STOPA survey** (Scale of Take-Over Performance Assessment): a 2-step self-rating collected immediately after each take-over event. The 11-point scale has categories: Uncontrolled (0), Dangerous (1–3), Unsatisfying (4–6), Delightful (7–9), Flawless (10).
2. **GAM mapping functions** (Generalized Additive Models): trained via Bayesian stepwise regression (Equation 11 in Li et al. 2023) to map the 9 PC scores to the STOPA ratings for each individual driver.
3. **Relabeling algorithm**: cross-references all drivers' GAM models to produce a ground-truth unified score per take-over.

## Interpreting PC Scores

### The Direction of Each PC

Each PC score is a standardized value. The direction (positive vs negative) depends on whether the metrics loading onto that PC indicate good or bad driving.

| PC | Name | Positive (+) means... | Negative (-) means... |
|-----|------|----------------------|----------------------|
| PC1 | Lateral Control | Smooth, minimal corrections | Erratic steering, high yaw variance |
| PC2 | Longitudinal Brake | Light, controlled braking | Hard, heavy braking (panic) |
| PC3 | Distance Security | Safe, large TTC/DTC margins | Close to collision, small margins |
| PC4 | Longitudinal Throttle | Heavy or jerky throttle application | Smooth, light throttle |
| PC5 | Reaction Time | Fast reaction | Slow reaction |
| PC6 | Lateral Fine Control | Jerky yaw/lateral movements (high variance) | Smooth, stable |
| PC7 | Lateral Composite | Large steering amplitude | Small, smooth corrections |
| PC8 | Lane Keeping | Wandering, high lane center error | Centered in lane |
| PC9 | Lateral Velocity | Stable lateral position | Fast side-to-side movement (swerving) |

### What a "Good Takeover" Looks Like

PC scores are z-scores. After proper calibration, a well-executed takeover should produce scores within a certain range:

| PC | Target Range | Ideal Value | What a good driver does |
|-----|-------------|-------------|------------------------|
| PC1 | -2.0 to +1.0 | ~-0.5 | Steers smoothly, minimal over-correction |
| PC2 | -2.0 to +0.5 | ~-0.5 | Brakes progressively, doesn't slam pedal |
| PC3 | -5.0 to -1.0 | ~-2.0 | Maintains safe distance (negative means closer than autopilot, which is inevitable — keep it modest) |
| PC4 | -1.0 to +1.0 | ~0.0 | Throttle control similar to cruise — smooth transitions |
| PC5 | +0.5 to +5.0 | > +2.0 | Faster is better. A score of +3 means reaction time is 3σ faster than human baseline |
| PC6 | -1.0 to +1.0 | ~0.0 | No high-frequency jitter |
| PC7 | -1.0 to +0.5 | ~-0.3 | Smooth, small steering angle changes |
| PC8 | -1.0 to +1.0 | ~0.0 | Stays near lane center |
| PC9 | -1.0 to +0.5 | ~-0.3 | Stable lateral movement |

### Warning Signs (Bad Takeovers)

| PC | Danger Range | What it indicates |
|-----|-------------|-------------------|
| PC1 | < -5.0 | Extreme over-correction, nearly losing control |
| PC2 | < -5.0 | Brake slammed to floor — panic response |
| PC3 | < -8.0 | Near-collision or actual collision (TTC near 0) |
| PC5 | < -1.0 or > 6.0 | < -1: extremely slow reaction. > 6: may be noise or crash data |
| PC6 | > +3.0 | Highly unstable lateral control — veering |
| PC7 | > +3.0 | Very large steering corrections — driver fighting the car |
| PC8 | > +3.0 | Significant lane deviation |

### Important Limitations

1. **Scores are relative to the human baseline calibration, not the hardware.** The calibration relies on a pre-recorded dataset of human drivers completing the exact same preset scenario. A PC5 score of +2.0 means "reacted 2 standard deviations faster than the average human in our baseline." PC scores are comparable across different simulator setups AS LONG AS both use the same preset (e.g., both ran "Set A — Standard Full Protocol") and standardized against that specific preset's baseline. Comparing PC scores from different presets (e.g., Set A vs Set C) is not valid because the baseline $\mu$ and $\sigma$ will differ.
2. **Cross-study comparison** is valid if both studies use the same preset. The preset standardises the scenario; the PC standardises the metrics.
3. **PC3 will naturally be negative** in any takeover scenario — the car IS approaching an obstacle. A very negative PC3 (-8 or below) means a crash. A moderate PC3 (-2 to -4) means the driver braked in time.
4. **Scores outside ±8 are almost certainly math errors** — check the baseline dataset or $\sigma$ floor.