"""
sim/presets.py
Scenario presets and scenario sets for TakeoverBench.

Presets define individual run configurations.
Scenario Sets are ordered lists of preset IDs used for standardised protocols.

All presets use SAE J3016-2021 Level 3 by default.
"""

from typing import Any

PRESETS: list[dict[str, Any]] = [
    {
        "id": 0,
        "name": "Training Familiarization",
        "map": "Town06",
        "vehicle_id": "vehicle.tesla.model3",
        "speed_kmh": 60,
        "tor_ttc": 3.0,
        "obstacle_distance": 400,
        "weather": "ClearNoon",
        "camera_mode": "chase",
        "sae_level": "L3",
        "spawn_index": 0,
        "post_tor_drive_s": 15,
        "is_training": True,
    },
    {
        "id": 1,
        "name": "Easy Highway",
        "map": "Town06",
        "vehicle_id": "vehicle.tesla.model3",
        "speed_kmh": 80,
        "tor_ttc": 3.0,
        "obstacle_distance": 450,
        "weather": "ClearNoon",
        "camera_mode": "chase",
        "sae_level": "L3",
        "spawn_index": 0,
        "post_tor_drive_s": 15,
        "is_training": False,
    },
    {
        "id": 2,
        "name": "Moderate Highway",
        "map": "Town06",
        "vehicle_id": "vehicle.tesla.model3",
        "speed_kmh": 90,
        "tor_ttc": 3.0,
        "obstacle_distance": 500,
        "weather": "ClearNoon",
        "camera_mode": "chase",
        "sae_level": "L3",
        "spawn_index": 80,
        "post_tor_drive_s": 15,
        "is_training": False,
    },
    {
        "id": 3,
        "name": "Hard Highway",
        "map": "Town06",
        "vehicle_id": "vehicle.tesla.model3",
        "speed_kmh": 100,
        "tor_ttc": 3.0,
        "obstacle_distance": 500,
        "weather": "ClearNoon",
        "camera_mode": "chase",
        "sae_level": "L3",
        "spawn_index": 160,
        "post_tor_drive_s": 15,
        "is_training": False,
    },
    {
        "id": 4,
        "name": "Adverse Rain",
        "map": "Town06",
        "vehicle_id": "vehicle.tesla.model3",
        "speed_kmh": 80,
        "tor_ttc": 3.0,
        "obstacle_distance": 450,
        "weather": "HardRainNoon",
        "camera_mode": "chase",
        "sae_level": "L3",
        "spawn_index": 0,
        "post_tor_drive_s": 10,
        "is_training": False,
    },
    {
        "id": 5,
        "name": "Adverse Sunset",
        "map": "Town06",
        "vehicle_id": "vehicle.tesla.model3",
        "speed_kmh": 80,
        "tor_ttc": 3.0,
        "obstacle_distance": 450,
        "weather": "ClearSunset",
        "camera_mode": "chase",
        "sae_level": "L3",
        "spawn_index": 80,
        "post_tor_drive_s": 10,
        "is_training": False,
    },
]

# ── Built-in scenario sets ──
BUILTIN_SETS = [
    {
        "id": "standard_full",
        "name": "Set A — Standard Protocol",
        "estimated_minutes": 5,
        "preset_ids": [0, 1, 2, 3, 4, 5],
    },
]


def get_preset(preset_id: int) -> dict[str, Any] | None:
    """Return a preset by ID, or None if not found."""
    for p in PRESETS:
        if p["id"] == preset_id:
            return dict(p)
    return None


def preset_to_scenario_config(preset: dict[str, Any]) -> dict[str, Any]:
    """Extract only the keys that scenario_config expects."""
    return {
        "map":               preset["map"],
        "vehicle_id":        preset["vehicle_id"],
        "speed_kmh":         preset["speed_kmh"],
        "tor_ttc":           preset["tor_ttc"],
        "obstacle_distance": preset["obstacle_distance"],
        "weather":           preset["weather"],
        "camera_mode":       preset["camera_mode"],
        "sae_level":         preset["sae_level"],
        "spawn_index":       preset.get("spawn_index", 0),
        "post_tor_drive_s":  preset.get("post_tor_drive_s", 10),
    }
