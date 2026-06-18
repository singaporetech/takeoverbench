"""
sim/fidelity.py — Wynne et al. (2019) Table 4 fidelity scoring.

This module computes per-category fidelity scores (Visual / Motion / Physical)
and generates hardware-configuration warnings tied directly to HCMTP PC validity.
"""

from typing import Any

# Wynne et al. (2019) Table 4 scoring
VISUAL_SCORES: dict[str, int] = {
    "single_screen": 1,
    "large_single": 2,
    "multi_screen_180": 3,
    "multi_screen_270": 4,
    "projector_270": 5,
}

MOTION_SCORES: dict[str, int] = {
    "none": 1,
    "partial": 3,
    "full_6dof": 5,
}

PHYSICAL_SCORES: dict[str, int] = {
    "keyboard": 1,
    "wheel_only": 2,
    "wheel_pedals_seat": 3,
    "partial_cab": 4,
    "full_cab": 5,
}

# Severity-to-marker mapping for PC unreliability annotations in PDF reports.
# Error  → †  metric invalid or heavily skewed
# Warning → ‡  metric may be degraded
PC_MARKERS: dict[str, str] = {
    "error": "†",
    "warning": "‡",
}

# Data-driven warning rules linking hardware to specific PC inaccuracies
WARNING_RULES: list[dict[str, Any]] = [
    {
        "key": "physical",
        "values": ["keyboard", "wheel_only"],
        "level": "error",
        "aspect": "Missing Pedals",
        "message": "No analog pedals detected. PC2 (Longitudinal Brake) and PC4 (Longitudinal Throttle) metrics will be completely invalid or heavily skewed.",
        "message_short": "No pedals detected, PC2/PC4 invalid",
        "affected_pcs": ["pc2", "pc4"],
    },
    {
        "key": "physical",
        "values": ["keyboard"],
        "level": "error",
        "aspect": "Binary Steering",
        "message": "Keyboard steering is binary (0% or 100%). This destroys natural variance, invalidating PC1 (Lateral Control), PC6 (Lateral Fine), and PC7 (Lateral Composite).",
        "message_short": "Binary steering, PC1/PC6/PC7 invalid",
        "affected_pcs": ["pc1", "pc6", "pc7"],
    },
    {
        "key": "motion",
        "values": ["none"],
        "level": "warning",
        "aspect": "Kinesthetic Feedback",
        "message": "No motion platform. Drivers cannot feel G-forces, typically resulting in exaggerated physical inputs. Expect higher variances in PC1 (Lateral), PC2 (Brake), and PC4 (Throttle) compared to real-world data.",
        "message_short": "No motion base, PC1/PC2/PC4 degraded",
        "affected_pcs": ["pc1", "pc2", "pc4"],
    },
    {
        "key": "visual",
        "values": ["single_screen"],
        "level": "warning",
        "aspect": "Peripheral Vision",
        "message": "Single screen restricts field-of-view (FOV). Reduced speed perception and spatial awareness may artificially degrade PC3 (Distance Security) and PC8 (Lane Keeping).",
        "message_short": "Single screen, PC3/PC8 degraded",
        "affected_pcs": ["pc3", "pc8"],
    },
    {
        "key": "motion",
        "values": ["none"],
        "level": "info",
        "aspect": "Hard Limit",
        "message": "No Motion Rule: maximum total score = 11 (medium-fidelity). High-fidelity requires a motion base.",
    },
    {
        "key": "visual",
        "values": ["single_screen"],
        "level": "info",
        "aspect": "Hard Limit",
        "message": "Single Screen Rule: maximum total score = 11 (medium-fidelity). High-fidelity requires multiple screens or a projector.",
    },
]


def get_warnings(config: dict) -> list[dict]:
    """Evaluate WARNING_RULES against a hardware config dict."""
    result: list[dict] = []
    for rule in WARNING_RULES:
        if config.get(rule["key"]) in rule["values"]:
            entry: dict[str, Any] = {
                "level": rule["level"],
                "key": rule["key"],
                "aspect": rule["aspect"],
                "message": rule["message"],
            }
            if "message_short" in rule:
                entry["message_short"] = rule["message_short"]
            if "affected_pcs" in rule:
                entry["affected_pcs"] = rule["affected_pcs"]
            result.append(entry)
    return result


def get_unavailable_pcs(warnings: list[dict]) -> dict[str, str]:
    """From triggered warnings, return {pc_key: marker} for unreliable PC columns.

    When a PC is flagged by multiple rules the most severe marker wins
    (error/†  beats warning/‡).
    """
    pc_map: dict[str, str] = {}
    # Process errors first so they take priority
    severity_rank = {"error": 0, "warning": 1}
    for w in sorted(warnings, key=lambda x: severity_rank.get(x.get("level", ""), 99)):
        marker = PC_MARKERS.get(w.get("level", ""), "")
        if not marker:
            continue
        for pc in w.get("affected_pcs", []):
            # First occurrence wins (errors come first after sort)
            if pc not in pc_map:
                pc_map[pc] = marker
    return pc_map


def classify_fidelity(visual: int, motion: int, physical: int) -> tuple[str, int]:
    """Return (level, total) based on Wynne et al. (2019) Table 4 total.

    Ranges: 3–7 → Low, 8–11 → Medium, 12–15 → High.
    Scores 3 and 11 are edge cases that Wynne et al. did not explicitly name
    but are logically the lowest Low and highest Medium respectively.
    """
    total = visual + motion + physical
    if total <= 7:
        return "Low", total      # 3–7 (3 = lowest Low)
    if total <= 11:
        return "Medium", total   # 8–11 (11 = top-tier Medium)
    return "High", total         # 12–15


def calculate_fidelity(config: dict) -> dict[str, Any]:
    """Full fidelity calculation: scores + warnings + classification."""
    visual = VISUAL_SCORES.get(config.get("visual", "single_screen"), 1)
    motion = MOTION_SCORES.get(config.get("motion", "none"), 1)
    physical = PHYSICAL_SCORES.get(config.get("physical", "keyboard"), 1)
    warnings = get_warnings(config)
    level, total = classify_fidelity(visual, motion, physical)

    return {
        "visual_score": visual,
        "motion_score": motion,
        "physical_score": physical,
        "visual_raw": config.get("visual", "single_screen"),
        "motion_raw": config.get("motion", "none"),
        "physical_raw": config.get("physical", "keyboard"),
        "fidelity_level": level,
        "fidelity_total": total,
        "warnings": warnings,
        "standard": "SAE J3016-2021",
        "reference": "Wynne et al. (2019)",
    }