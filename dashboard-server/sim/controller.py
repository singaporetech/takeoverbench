"""
Waypoint-following PID controller for highway driving.

The public entry point is ``run_controller()``, which is started as a daemon
thread in ``setup_scenario()``.  It delegates to three helpers:

* ``_calculate_steering()`` — pure math, no side effects
* ``_get_lead_distance()`` — distance to lead vehicle (``None`` if absent)
* ``_autopilot_control()`` — full PI speed control with integral, overspeed
  brake, and collision brake

**Before TOR** (``autopilot_engaged == True``): full PID control — steering,
speed, integral, overspeed brake, collision brake.

**After TOR** (``autopilot_engaged == False``): the controller does **nothing**.
No ``apply_control()`` is called, so the human's physical steering wheel
and pedal inputs pass through directly to CARLA.
"""

import logging
import math
import time
import carla
from sim.constants import (
    PID_KP_STEER,
    PID_KP_SPEED,
    PID_KI_SPEED,
    PID_THROTTLE_FF_FACTOR,
    PID_LOOK_AHEAD_M,
    PID_OVERSPEED_BRAKE_THRESHOLD,
    PID_SAFETY_BRAKE_DIST_M,
    PID_SAFETY_BRAKE_MIN_SPEED,
    CONTROLLER_INTERVAL_S,
)
from .state import state, state_lock, ctx

logger = logging.getLogger(__name__)

# PID state (reset on each new scenario via globals in run_controller)
_integral: float = 0.0
_tick_count: int = 0


# ── Helpers ──────────────────────────────────────────────────────────

def _calculate_steering(current_loc, target_loc, current_yaw) -> float:
    """Compute steer value [-1, 1] from current position toward target waypoint."""
    dx = target_loc.x - current_loc.x
    dy = target_loc.y - current_loc.y
    target_yaw = math.degrees(math.atan2(dy, dx))
    yaw_error = target_yaw - current_yaw

    while yaw_error > 180:
        yaw_error -= 360
    while yaw_error < -180:
        yaw_error += 360

    return max(-1.0, min(1.0, yaw_error / 90.0 * PID_KP_STEER))


def _get_lead_distance(ego_loc) -> float | None:
    """Distance to lead vehicle, or ``None`` if no lead vehicle or error."""
    if ctx["lead_vehicle"] is None:
        return None
    try:
        return ego_loc.distance(ctx["lead_vehicle"].get_location())
    except Exception:
        logger.debug("Lead distance check error", exc_info=True)
        return None


def _autopilot_control(current_speed: float, target_speed_ms: float,
                       lead_distance: float | None) -> tuple[float, float]:
    """Autopilot speed control with PI, anti-windup, overspeed brake, and collision brake.

    Returns ``(throttle, brake)``, both in [0, 1].
    """
    global _integral

    speed_error = target_speed_ms - current_speed

    if speed_error > 0:
        # ── Below target: accumulate integral, apply throttle ──
        _integral += speed_error * 0.05
        _integral = min(1.0, _integral)
        throttle = min(1.0, target_speed_ms * PID_THROTTLE_FF_FACTOR
                       + speed_error * PID_KP_SPEED
                       + _integral * PID_KI_SPEED)
        brake = 0.0

    else:
        # ── At or above target: decay integral ──
        _integral = max(0.0, _integral - 0.2)

        if speed_error < PID_OVERSPEED_BRAKE_THRESHOLD:
            brake = min(0.4, abs(speed_error) * 0.1)
            throttle = 0.0
            logger.warning("OVERSPEED brake -- spd=%.1f (%.0f km/h)",
                           current_speed, current_speed * 3.6)
        else:
            throttle = max(0.0, min(1.0, target_speed_ms * PID_THROTTLE_FF_FACTOR
                                    + speed_error * PID_KP_SPEED))
            brake = 0.0

    # ── Safety collision brake ──
    if (lead_distance is not None
            and lead_distance < PID_SAFETY_BRAKE_DIST_M
            and current_speed > PID_SAFETY_BRAKE_MIN_SPEED):
        logger.warning("SAFETY BRAKE -- lead_dist=%.1fm spd=%.1f", lead_distance, current_speed)
        brake = 1.0
        throttle = 0.0
        _integral = 0.0

    return throttle, brake


# ── Public entry point ──────────────────────────────────────────────

def run_controller(target_speed_kmh: float) -> None:
    """PID waypoint-follower.  Runs in a daemon thread from ``setup_scenario()``.

    * **Before TOR** (``autopilot_engaged == True``): full PID steering,
      speed, integral, overspeed brake, and collision brake.
    * **After TOR** (``autopilot_engaged == False``): does nothing — lets
      human physical inputs pass through directly to CARLA.

    The loop exits when the ego vehicle is destroyed or the scenario ends.
    """
    global _integral, _tick_count
    _integral = 0.0
    _tick_count = 0

    # Initialise wheel in this thread (init + pump must be same thread)
    from . import wheel
    wheel.init()

    target_speed_ms = target_speed_kmh / 3.6
    carla_map = ctx["world"].get_map()

    while ctx["vehicle"] is not None and state.get("scenario_running"):
        try:
            if not ctx["vehicle"].is_alive:
                break

            _tick_count += 1
            transform = ctx["vehicle"].get_transform()
            v = ctx["vehicle"].get_velocity()
            current_speed = math.sqrt(v.x**2 + v.y**2 + v.z**2)

            # ── Read autopilot flag ──
            with state_lock:
                autopilot = state["autopilot_engaged"]

            # ── Autopilot branch ──
            if autopilot:
                current_wp = carla_map.get_waypoint(
                    transform.location,
                    project_to_road=True,
                    lane_type=carla.LaneType.Driving,
                )
                next_wps = current_wp.next(PID_LOOK_AHEAD_M) if current_wp else []

                if not next_wps:
                    logger.warning("EMPTY WAYPOINTS -- stopping at (%.1f, %.1f)",
                                   transform.location.x, transform.location.y)
                    ctx["vehicle"].apply_control(
                        carla.VehicleControl(throttle=0.0, brake=1.0, reverse=False))
                    time.sleep(0.1)
                    continue

                steer = _calculate_steering(
                    transform.location,
                    next_wps[0].transform.location,
                    transform.rotation.yaw,
                )
                lead_dist = _get_lead_distance(transform.location)
                throttle, brake = _autopilot_control(current_speed, target_speed_ms, lead_dist)

                ctx["vehicle"].apply_control(carla.VehicleControl(
                    throttle=throttle,
                    steer=steer,
                    brake=brake,
                    reverse=False,
                    manual_gear_shift=False,
                ))

                if _tick_count % 20 == 1:
                    logger.debug("tick spd=%.1f/%.0f th=%.2f br=%.2f st=%.3f",
                                 current_speed, target_speed_kmh, throttle, brake, steer)

            # ── Human branch (post-TOR): read steering wheel ──
            else:
                from . import wheel
                ctrl = wheel.read()
                if ctrl is not None:
                    ctx["vehicle"].apply_control(ctrl)
                if _tick_count % 20 == 1:
                    logger.debug("Human %s", "wheel connected" if ctrl else "no wheel -- coasting")

        except Exception as e:
            logger.error("Controller exception: %s", e, exc_info=True)

        time.sleep(CONTROLLER_INTERVAL_S)
