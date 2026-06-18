#!/usr/bin/env python3
"""
hcmtp_calibrate.py — Compute HCMTP population baseline per preset.

Reads all telemetry CSV files in ``runs/``, groups them by ``preset_id``,
extracts the pre-computed 41 objective metrics from the saved CSV rows,
and outputs per-preset population mean (µ) and standard deviation (σ) to
``calibration.json``.
"""

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

# Hardcoded to decouple the offline calibration script from the CARLA library dependencies
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
    "MRLD", "HFCS", "TTC", "DTC", "TLC", "TCLC",
    "ECLmax", "ECLmean", "SDLP"
]

def main():
    parser = argparse.ArgumentParser(
        description="Compute HCMTP population µ/σ per preset from runs"
    )
    parser.add_argument(
        "--runs-dir",
        default="runs",
        help="Directory containing telemetry CSV files (default: runs/)",
    )
    args = parser.parse_args()

    runs_dir = Path(args.runs_dir)
    if not runs_dir.is_dir():
        print(f"Error: directory not found: {runs_dir}", file=sys.stderr)
        sys.exit(1)

    csv_files = sorted(runs_dir.rglob("*_telemetry.csv"))
    if not csv_files:
        print(f"Error: no telemetry CSV files found in {runs_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(csv_files)} CSV files in {runs_dir}")

    project_root = Path(__file__).resolve().parent.parent

    # Group raw metrics by preset_id
    by_preset: dict[int, list[dict[str, float]]] = defaultdict(list)

    for path in csv_files:
        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            continue

        # Convert numeric fields
        for r in rows:
            for k in r:
                try:
                    r[k] = float(r[k])
                except (ValueError, TypeError):
                    pass

        # Read preset_id from first row
        preset_id = int(rows[0].get("preset_id", -1))
        if preset_id < 0:
            print(f"  Skipping {path.name}: no preset_id column")
            continue

        # Extract final calculated metrics from the last row
        last_row = rows[-1]
        filtered = {}
        for k in ALL_METRICS:
            if k in last_row:
                filtered[k] = float(last_row[k])
            else:
                print(f"  Warning: Metric '{k}' missing in {path.name}")
        
        by_preset[preset_id].append(filtered)
        print(f"  {path.name}: preset={preset_id} loaded pre-computed metrics")

    if not by_preset:
        print("Error: no valid take-overs found", file=sys.stderr)
        sys.exit(1)

    # Compute per-preset µ/σ
    MIN_SIGMA = 0.1
    output: dict[str, dict] = {}

    for preset_id, metrics_list in sorted(by_preset.items()):
        print(f"\nPreset {preset_id}: {len(metrics_list)} take-overs")
        means: dict[str, float] = {}
        stds: dict[str, float] = {}

        for key in ALL_METRICS:
            # Filter out 999.0 fallbacks so they don't corrupt the human baseline
            values = [m[key] for m in metrics_list if key in m and m[key] < 900.0]
            if not values:
                continue
            n = len(values)
            mu = sum(values) / n
            variance = sum((v - mu) ** 2 for v in values) / n
            sigma = math.sqrt(variance) if variance > 0 else MIN_SIGMA
            means[key] = round(mu, 6)
            stds[key] = round(max(sigma, MIN_SIGMA), 6)

        output[str(preset_id)] = {"name": f"Preset {preset_id}", "means": means, "stds": stds}

    out_path = project_root / "calibration.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    total_runs = sum(len(v) for v in by_preset.values())
    print(f"\nDone — {len(output)} presets, {total_runs} take-overs saved to {out_path}")

if __name__ == "__main__":
    main()