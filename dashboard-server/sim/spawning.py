"""
sim/spawning.py — Ego and lead-vehicle spawning utilities for TakeoverBench.

Contains the Smart Tracer algorithm for placing the lead vehicle ahead of
the ego, weather presets, and spawn-point filtering logic.
"""

import logging
import math
import time
from typing import Any
import carla
from sim.constants import SPAWN_RETRY_COUNT
from .state import state, state_lock, ctx

logger = logging.getLogger(__name__)

# Weather preset mapping (used by setup_weather)
WEATHER_MAP: dict[str, Any] = {
    "ClearNoon": carla.WeatherParameters.ClearNoon,
    "CloudyNoon": carla.WeatherParameters.CloudyNoon,
    "WetNoon": carla.WeatherParameters.WetNoon,
    "HardRainNoon": carla.WeatherParameters.HardRainNoon,
    "ClearSunset": carla.WeatherParameters.ClearSunset,
}


def setup_weather(weather_name: str) -> None:
    """Apply a named weather preset to the current CARLA world."""
    weather = WEATHER_MAP.get(weather_name, carla.WeatherParameters.ClearNoon)
    ctx["world"].set_weather(weather)
    logger.info("Weather set: %s", weather_name)


def spawn_ego_vehicle(cfg: dict) -> tuple[Any, Any] | tuple[None, None]:
    """Spawn the ego vehicle at a valid highway spawn point.

    Filters the map's spawn points to find on-road, non-junction positions,
    then attempts to spawn at consecutive points until one succeeds.

    Returns ``(vehicle, spawn_point)`` or ``(None, None)`` on failure.
    """
    bp_lib = ctx["world"].get_blueprint_library()
    carla_map = ctx["world"].get_map()
    spawn_points = carla_map.get_spawn_points()

    ego_bp = bp_lib.find(cfg["vehicle_id"])
    if ego_bp is None:
        logger.warning("%s not found, using Tesla", cfg["vehicle_id"])
        ego_bp = bp_lib.find("vehicle.tesla.model3")
    if ego_bp.has_attribute("color"):
        ego_bp.set_attribute("color", "255,255,255")

    # Filter valid on-road, non-junction spawn points
    valid_spawn_points = []
    for sp in spawn_points:
        wp = carla_map.get_waypoint(sp.location)
        if wp is None:
            continue
        dist_to_road = sp.location.distance(wp.transform.location)
        if dist_to_road >= 5.0:
            continue
        if wp.lane_type != carla.LaneType.Driving:
            continue
        if wp.is_junction:
            continue
        valid_spawn_points.append(sp)

    logger.info("Found %d/%d on-road spawn points", len(valid_spawn_points), len(spawn_points))

    if not valid_spawn_points:
        logger.error("Could not find any valid highway spawn points.")
        return None, None

    # Route diversity offset
    start_idx = cfg.get("spawn_index", 0)
    if start_idx >= len(valid_spawn_points):
        start_idx = 0

    ego_spawn_point = None
    for i, sp in enumerate(valid_spawn_points[start_idx : start_idx + SPAWN_RETRY_COUNT]):
        vehicle = ctx["world"].try_spawn_actor(ego_bp, sp)
        if vehicle is not None:
            ctx["vehicle"] = vehicle
            ego_spawn_point = sp
            logger.info("Ego vehicle spawned cleanly at point index %d", start_idx + i)
            break

    if ctx["vehicle"] is None or ego_spawn_point is None:
        logger.error("Could not spawn ego vehicle (points blocked).")
        return None, None

    return ctx["vehicle"], ego_spawn_point


def spawn_lead_vehicle(cfg: dict, ego_spawn_point: Any) -> bool:
    """Spawn the lead vehicle ahead of the ego using the Smart Tracer algorithm.

    Walks waypoints along the road from the ego's spawn position by the
    configured *obstacle_distance*, preferring to stay on the same road
    and lane when the road splits.  Falls back 5 m forward if the primary
    position is blocked.

    Returns True if the lead vehicle was spawned successfully.
    """
    bp_lib = ctx["world"].get_blueprint_library()
    carla_map = ctx["world"].get_map()

    lead_bp = bp_lib.find("vehicle.audi.a2")
    if lead_bp and lead_bp.has_attribute("color"):
        lead_bp.set_attribute("color", "255,0,0")

    try:
        ego_loc = ego_spawn_point.location
        dist = float(cfg["obstacle_distance"])

        ego_wp = carla_map.get_waypoint(
            ego_loc, project_to_road=True, lane_type=carla.LaneType.Driving
        )

        # --- THE SMART TRACER ---
        current_wp = ego_wp
        walked = 0.0

        while walked < dist:
            next_wps = current_wp.next(2.0)
            if not next_wps:
                break

            # If the road splits (like an off-ramp), force it to stay in the same lane
            chosen_wp = next_wps[0]
            for wp in next_wps:
                if wp.road_id == current_wp.road_id and wp.lane_id == current_wp.lane_id:
                    chosen_wp = wp
                    break

            current_wp = chosen_wp
            walked += 2.0

        lead_wp = current_wp
        # ------------------------

        if lead_wp is None:
            raise RuntimeError("No waypoint for lead spawn")

        road_match = "SAME ROAD" if lead_wp.road_id == ego_wp.road_id else "DIFF ROAD"
        lane_match = "SAME LANE" if lead_wp.lane_id == ego_wp.lane_id else "DIFF LANE"
        logger.info("Lead spawn: Smart Tracer walked %.0fm along the curve.", walked)
        logger.info("Lead spawn: road=%s, lane=%s (%s, %s)",
                    lead_wp.road_id, lead_wp.lane_id, road_match, lane_match)

        # --- Spawn at the chosen waypoint ---
        lead_transform = lead_wp.transform
        lead_transform.location.z += 1.5
        logger.info("Lead spawn: trying at (%.1f, %.1f, %.2f)",
                    lead_transform.location.x, lead_transform.location.y, lead_transform.location.z)

        ctx["lead_vehicle"] = ctx["world"].try_spawn_actor(lead_bp, lead_transform)
        if ctx["lead_vehicle"]:
            ctx["lead_vehicle"].set_autopilot(False)
            ctx["lead_vehicle"].apply_control(carla.VehicleControl(hand_brake=True))
            time.sleep(0.1)
            _print_lead_debug(carla_map, walked)
        else:
            logger.warning("Lead vehicle spawn blocked — trying fallback 5m")
            fallback_wps = lead_wp.next(5.0)
            if fallback_wps:
                fb_wp = fallback_wps[0]
                t2 = fb_wp.transform
                t2.location.z += 1.5
                logger.info("Lead spawn: fallback at (%.1f, %.1f)", t2.location.x, t2.location.y)
                ctx["lead_vehicle"] = ctx["world"].try_spawn_actor(lead_bp, t2)
                if ctx["lead_vehicle"]:
                    ctx["lead_vehicle"].set_autopilot(False)
                    ctx["lead_vehicle"].apply_control(carla.VehicleControl(hand_brake=True))
                    time.sleep(0.1)
                    _print_lead_debug(carla_map, walked, fallback=True)

        return ctx["lead_vehicle"] is not None

    except Exception as e:
        logger.error("Lead vehicle spawn error: %s", e)
        return False


def _print_lead_debug(carla_map, walked, fallback: bool = False) -> None:
    """Log debug info about the lead vehicle's spawn position (internal)."""
    tag = "fallback" if fallback else "primary"
    if ctx["vehicle"] is None or ctx["lead_vehicle"] is None:
        logger.info("Lead debug (%s): cannot check — missing actor", tag)
        return
    try:
        lead_loc = ctx["lead_vehicle"].get_location()
        ego_loc = ctx["vehicle"].get_location()
        actual_dist = ego_loc.distance(lead_loc)
        lead_wp = carla_map.get_waypoint(
            lead_loc, project_to_road=True, lane_type=carla.LaneType.Driving
        )
        lead_road = lead_wp.road_id if lead_wp else "?"
        lead_lane = lead_wp.lane_id if lead_wp else "?"
        ego_wp = carla_map.get_waypoint(
            ego_loc, project_to_road=True, lane_type=carla.LaneType.Driving
        )
        ego_road = ego_wp.road_id if ego_wp else "?"
        ego_lane = ego_wp.lane_id if ego_wp else "?"
        same_road = "SAME ROAD" if lead_road == ego_road else "DIFF ROAD"
        same_lane = "SAME LANE" if lead_lane == ego_lane else "DIFF LANE"
        logger.info(
            "Lead (%s): pos=(%.1f, %.1f, %.2f), dist=%.0fm, road=%s, lane=%s (%s, %s vs ego road=%s, lane=%s)",
            tag, lead_loc.x, lead_loc.y, lead_loc.z, actual_dist,
            lead_road, lead_lane, same_road, same_lane, ego_road, ego_lane,
        )
    except Exception as e:
        logger.warning("Lead debug (%s) error: %s", tag, e)
