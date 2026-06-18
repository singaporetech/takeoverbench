"""
sim/summary.py
Shared run summary builder — aggregates telemetry rows into a flat dict.
"""

def build_run_summary(
    rows: list[dict],
    *,
    run_id: str | None,
    run_number: int,
    participant_id: str,
    scenario_set: str,
    config: dict,
    hardware: dict,
    tor_triggered: bool,
    pc_scores: dict | None = None,
) -> dict:
    """Compute aggregate statistics and return a flat summary dict.

    Parameters
    ----------
    rows : list[dict]
        Telemetry rows. Each row must contain ``timestamp`` and may contain
        ``speed_kmh``, ``ttc``, ``steer``, ``brake``, ``distance_m``.
    run_id, run_number, participant_id, scenario_set :
        Run metadata.
    config, hardware :
        Scenario and hardware configuration dicts (stored as-is).
    tor_triggered :
        Whether a TOR event fired during this run.
    pc_scores :
        HCMTP PC scores dict (e.g. ``{"pc1": 0.123, ...}``).
    """
    speeds = [r["speed_kmh"] for r in rows if "speed_kmh" in r]
    ttcs = [r["ttc"] for r in rows if "ttc" in r and r["ttc"] < 999]
    steers = [abs(r["steer"]) for r in rows if "steer" in r]
    brakes = [r["brake"] for r in rows if "brake" in r]
    distances = [r["distance_m"] for r in rows if "distance_m" in r]

    summary: dict = {
        "run_id": run_id,
        "run_number": run_number,
        "participant_id": participant_id,
        "scenario_set": scenario_set,
        "num_rows": len(rows),
        "duration_s": (
            round(rows[-1]["timestamp"] - rows[0]["timestamp"], 1)
            if len(rows) >= 2
            else 0
        ),
        "speed_avg": round(sum(speeds) / len(speeds), 1) if speeds else 0,
        "speed_max": round(max(speeds), 1) if speeds else 0,
        "speed_min": round(min(speeds), 1) if speeds else 0,
        "ttc_min": round(min(ttcs), 2) if ttcs else 999.0,
        "steer_max": round(max(steers), 3) if steers else 0,
        "brake_max": round(max(brakes), 3) if brakes else 0,
        "dist_min": round(min(distances), 1) if distances else 999.0,
        "tor_triggered": tor_triggered,
        "scenario_config": config,
        "hardware_config": hardware,
    }

    if pc_scores:
        summary.update(pc_scores)

    return summary
