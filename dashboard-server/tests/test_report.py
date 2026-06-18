"""Quick test: generate a PDF report with synthetic data.

Uses real WARNING_RULES from fidelity.py so the PDF exercises hardware
markers († / ‡) and the REPORT LEGEND section. It uses a curated set of 
PC scores to test every edge case (Ideal, Elevated, Danger) of the report logic.
"""
import importlib.util
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent

# Load sim/fidelity.py (no carla dependency, safe to import standalone)
_fid_spec = importlib.util.spec_from_file_location(
    "fidelity", _project_root / "sim" / "fidelity.py"
)
_fidelity = importlib.util.module_from_spec(_fid_spec)
_fid_spec.loader.exec_module(_fidelity)
get_warnings = _fidelity.get_warnings

# Load sim/report.py directly (bypasses sim/__init__.py which needs carla)
_rep_spec = importlib.util.spec_from_file_location(
    "report", _project_root / "sim" / "report.py"
)
_report = importlib.util.module_from_spec(_rep_spec)
_rep_spec.loader.exec_module(_report)
generate_session_report = _report.generate_session_report

# ── Curated PC Scores to thoroughly test report logic ──
synthetic_pc_matrix = [
    # RUN 1: The "Textbook" Run (Perfectly within targets, near ideal baselines)
    {"pc1": -0.15, "pc2": -0.50, "pc3": -2.20, "pc4": 0.05, "pc5": 2.50, "pc6": 0.10, "pc7": -0.20, "pc8": 0.00, "pc9": -0.15},
    
    # RUN 2: The "Sloppy" Run (Amber warnings: elevated deviations, but no danger)
    {"pc1": 1.45,  "pc2": 0.85,  "pc3": -0.50, "pc4": -1.50, "pc5": 0.30, "pc6": -1.20, "pc7": 0.70,  "pc8": -1.30, "pc9": 0.80},
    
    # RUN 3: The "Panic" Run (Red Dangers on PC2 Braking and PC3 Distance)
    {"pc1": -4.20, "pc2": -6.50, "pc3": -8.80, "pc4": 1.50,  "pc5": 4.80, "pc6": 2.10,  "pc7": -1.20, "pc8": 1.40,  "pc9": -2.20},
    
    # RUN 4: The "Distracted" Run (Red Dangers on Reaction Time and Lateral Swerving)
    {"pc1": -5.80, "pc2": -2.50, "pc3": -5.50, "pc4": -0.20, "pc5": -1.20, "pc6": 3.40,  "pc7": 3.80,  "pc8": 3.50,  "pc9": -3.50},
    
    # RUN 5: The "Recovery" Run (Realistic mix: mostly Green, minor Amber wandering)
    {"pc1": -1.10, "pc2": -1.80, "pc3": -3.50, "pc4": 1.15,  "pc5": 1.80, "pc6": 0.80,  "pc7": 0.30,  "pc8": 1.60,  "pc9": -0.60},
]

# ── Generate 5 fake runs ──
runs = []
for i, scores in enumerate(synthetic_pc_matrix):
    run_data = {
        "run_id": f"test_{i:02x}",
        "run_number": i + 1,
        "participant_id": "P001",
        "scenario_set": "Core Protocol A",
        "num_rows": 100 + (i * 15),
        "duration_s": 30.0 + i * 2,
        "speed_avg": 60.0 + i * 5,
        "speed_max": 70.0 + i * 4,
        "ttc_min": 0.5 - i * 0.08,
        "steer_max": 0.2 + i * 0.05,
        "brake_max": 0.3 + i * 0.1,
        "dist_min": 12.0 - i * 1.5,
        "tor_triggered": True,
        "scenario_config": {
            "speed_kmh": 60, "tor_ttc": 3, "obstacle_distance": 50,
            "weather": "Clear", "vehicle_id": "vehicle.audi.tt", "map": "Town06",
        },
        "hardware_config": {},
    }
    # Merge the specific curated scores into the run data
    run_data.update(scores)
    runs.append(run_data)

# Realistic low-fidelity hardware that triggers several warning rules
hw_config = {
    "visual": "single_screen",
    "motion": "none",
    "physical": "keyboard",
}
warnings = get_warnings(hw_config)

hw = {
    "visual_score": 1,
    "motion_score": 1,
    "physical_score": 1,
    "visual_raw": "single_screen",
    "motion_raw": "none",
    "physical_raw": "keyboard",
    "fidelity_level": "Low",
    "fidelity_total": 3,
    "warnings": warnings,
}

path = generate_session_report(runs, hw, output_dir=".")
print(f"\nPDF generated: {path}")
print(f"  Triggered {len(warnings)} warnings:")
for w in warnings:
    print(f"    [{w['level']}] {w['aspect']}: {w['message'][:60]}...")