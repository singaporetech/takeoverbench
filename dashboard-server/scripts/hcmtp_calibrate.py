#!/usr/bin/env python3
"""hcmtp_calibrate.py — Compute the HCMTP population baseline per preset.

Reads telemetry CSV files from ``runs/``, groups them by ``preset_id``, takes
the pre-computed 41 objective metrics from each run, and writes per-preset
population mean (µ) and standard deviation (σ) to ``calibration.json``.

Curation is explicit: pass ``--exclude <substring>`` (repeatable) to drop test
sessions, and ``--min-rows`` to drop truncated runs. The output records
provenance (sample count, source sessions, git commit, timestamp).
"""

import argparse
import csv
import json
import math
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Hardcoded to decouple the offline calibration script from CARLA imports
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
    "ECLmax", "ECLmean", "SDLP",
]

MIN_SIGMA = 0.1


def _parse_preset_id(value) -> int | None:
    """Parse a preset_id cell; returns None when missing/blank/non-numeric."""
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _git_commit(project_root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=project_root, text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# Columns that are identifiers, not numbers — leave them as strings.
_STR_COLUMNS = {"preset_id", "run_id", "session_id", "hardware", "mode", "scenario"}

_recompute_fn = None


def _parse_rows(rows: list[dict]) -> list[dict]:
    """Convert CSV string values to floats so sim.hcmtp can consume them."""
    out = []
    for r in rows:
        out.append({
            k: (v if k in _STR_COLUMNS else _to_float(v))
            for k, v in r.items()
        })
    return out


def _get_recompute_fn(project_root: Path):
    """Import sim.hcmtp.compute_raw_metrics with a stubbed carla module.

    Recomputing from the raw telemetry keeps the baseline consistent with the
    *current* metric definitions, regardless of which code version recorded
    the run. Requires numpy (already a server dependency).
    """
    global _recompute_fn
    if _recompute_fn is None:
        import sys as _sys
        from unittest.mock import MagicMock

        _sys.modules.setdefault("carla", MagicMock(name="carla"))
        if str(project_root) not in _sys.path:
            _sys.path.insert(0, str(project_root))
        from sim.hcmtp import compute_raw_metrics  # noqa: PLC0415
        _recompute_fn = compute_raw_metrics
    return _recompute_fn


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute HCMTP population µ/σ per preset")
    parser.add_argument("--runs-dir", default="runs", help="Directory of telemetry CSVs (default: runs/)")
    parser.add_argument(
        "--exclude", action="append", default=[],
        help="Skip CSVs whose path contains this substring (repeatable)",
    )
    parser.add_argument("--min-rows", type=int, default=0, help="Skip runs shorter than this many rows")
    parser.add_argument(
        "--keep-collisions", action="store_true",
        help="Include runs flagged as collisions (default: exclude them)",
    )
    parser.add_argument(
        "--recompute", action="store_true",
        help="Recompute the 41 metrics from the raw telemetry with the current "
             "code instead of reading the stored columns. Use this whenever the "
             "metric definitions have changed since the runs were recorded.",
    )
    parser.add_argument("--output", default=None, help="Output path (default: <project>/calibration.json)")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent

    runs_dir = Path(args.runs_dir)
    if not runs_dir.is_absolute():
        runs_dir = project_root / runs_dir
    if not runs_dir.is_dir():
        print(f"Error: directory not found: {runs_dir}", file=sys.stderr)
        sys.exit(1)

    csv_files = sorted(runs_dir.rglob("*_telemetry.csv"))
    kept = [f for f in csv_files if not any(x in str(f) for x in args.exclude)]
    skipped = len(csv_files) - len(kept)
    print(f"Found {len(csv_files)} CSVs; {len(kept)} after --exclude ({skipped} excluded)")

    by_preset: dict[int, list[dict[str, float]]] = defaultdict(list)
    sources: dict[int, set[str]] = defaultdict(set)

    for path in kept:
        with path.open(newline="") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            print(f"  Skipping {path.name}: empty")
            continue
        if len(rows) < args.min_rows:
            print(f"  Skipping {path.name}: {len(rows)} rows < min-rows {args.min_rows}")
            continue

        collisions = sum(1 for r in rows if str(r.get("collision", "")).strip() in ("1", "1.0"))
        if collisions and not args.keep_collisions:
            print(f"  Skipping {path.name}: collision detected ({collisions} samples)")
            continue

        preset_id = _parse_preset_id(rows[0].get("preset_id"))
        if preset_id is None:
            print(f"  Skipping {path.name}: no valid preset_id")
            continue

        if args.recompute:
            parsed = _parse_rows(rows)
            tor_ts = next(
                (r.get("timestamp") for r in parsed if r.get("post_tor")), None
            )
            try:
                metrics = _get_recompute_fn(project_root)(parsed, tor_ts)
            except Exception as e:
                print(f"  Skipping {path.name}: recompute failed ({e})")
                continue
        else:
            last = rows[-1]
            metrics = {}
            for k in ALL_METRICS:
                v = _to_float(last.get(k))
                if v is not None:
                    metrics[k] = v
            if not metrics:
                print(f"  Skipping {path.name}: no HCMTP metric columns")
                continue

        by_preset[preset_id].append(metrics)
        sources[preset_id].add(path.parent.name)
        print(f"  {path.name}: preset={preset_id} loaded")

    if not by_preset:
        print("Error: no valid take-overs found", file=sys.stderr)
        sys.exit(1)

    output: dict[str, dict] = {}
    for preset_id, metrics_list in sorted(by_preset.items()):
        means: dict[str, float] = {}
        stds: dict[str, float] = {}
        for key in ALL_METRICS:
            # Drop 999.0 fallbacks so they don't corrupt the baseline.
            values = [m[key] for m in metrics_list if key in m and m[key] < 900.0]
            if not values:
                continue
            mu = sum(values) / len(values)
            variance = sum((v - mu) ** 2 for v in values) / len(values)
            sigma = math.sqrt(variance) if variance > 0 else MIN_SIGMA
            means[key] = round(mu, 6)
            stds[key] = round(max(sigma, MIN_SIGMA), 6)

        output[str(preset_id)] = {
            "name": f"Preset {preset_id}",
            "n": len(metrics_list),
            "sources": sorted(sources[preset_id]),
            "means": means,
            "stds": stds,
        }
        print(f"\nPreset {preset_id}: {len(metrics_list)} take-overs from {len(sources[preset_id])} session(s)")

    output["_provenance"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commit": _git_commit(project_root),
        "runs_dir": str(runs_dir),
        "excluded_substrings": args.exclude,
        "min_rows": args.min_rows,
        "keep_collisions": args.keep_collisions,
        "recomputed": args.recompute,
        "csv_files_used": len(kept),
        "sigma_floor": MIN_SIGMA,
    }

    out_path = Path(args.output) if args.output else (project_root / "calibration.json")
    with out_path.open("w") as f:
        json.dump(output, f, indent=2)

    total_runs = sum(len(v) for v in by_preset.values())
    print(f"\nDone — {len(by_preset)} preset(s), {total_runs} take-over(s) → {out_path}")


if __name__ == "__main__":
    main()
