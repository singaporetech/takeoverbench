"""
Scenario lifecycle: setup, end, cleanup, and spawn point helpers.
Both setup_scenario() and training scenarios delegate to _start_experiment().
"""
import logging
import threading
import carla
from .state import state, state_lock, ctx

logger = logging.getLogger(__name__)


def setup_scenario() -> bool:
    """Spawn ego vehicle + lead vehicle + camera. Map must already be loaded."""
    return _start_experiment(
        has_lead=True,
        autopilot_engaged=True,
    )


def _start_experiment(
    *,
    has_lead: bool,
    autopilot_engaged: bool,
    weather_override: str | None = None,
    config_defaults: dict | None = None,
) -> bool:
    """Shared scenario startup used by both calibration and full scenarios."""
    _cleanup_actors()

    try:
        cfg = dict(config_defaults or {})
        with state_lock:
            cfg.update(state.get("scenario_config", {}))

        # Map change
        current_map = ctx["world"].get_map().name.split("/")[-1]
        target_map = cfg["map"]
        if current_map != target_map:
            logger.info("Map change requested. Loading %s...", target_map)
            from .connection import load_map
            load_map(target_map)

        # Weather
        weather_name = weather_override or cfg["weather"]
        from .spawning import setup_weather
        setup_weather(weather_name)

        # Spawn ego vehicle
        from .spawning import spawn_ego_vehicle, spawn_lead_vehicle
        vehicle, spawn_point = spawn_ego_vehicle(cfg)
        if vehicle is None:
            return False

        # Spawn lead vehicle (optional)
        if has_lead:
            spawn_lead_vehicle(cfg, spawn_point)

        # Set state
        with state_lock:
            state["scenario_running"] = True
            state["tor_triggered"] = False
            state["autopilot_engaged"] = autopilot_engaged
            state["recording"] = True  # enables telemetry row buffering

        # Prime the world with one tick so the freshly spawned vehicle's
        # physics are fully initialized before the controller applies control.
        ctx["world"].tick()

        # Start controller thread (PID in autopilot mode, wheel read in human mode)
        from .controller import run_controller
        ctx["control_thread"] = threading.Thread(
            target=run_controller,
            args=(float(cfg.get("speed_kmh", 60)),),
            daemon=True,
        )
        ctx["control_thread"].start()

        # Attach camera and spectator
        from .camera import _attach_camera, _start_spectator_follow
        _start_spectator_follow("pov")
        _attach_camera(cfg.get("camera_mode", "chase"))

        if autopilot_engaged:
            logger.info("Scenario started — %s km/h, SAE %s",
                        cfg.get("speed_kmh"), cfg.get("sae_level", "?"))
        else:
            logger.info("Calibration mode active — drive freely")

        return True

    except Exception as e:
        logger.error("Scenario start error: %s", e, exc_info=True)
        _cleanup_actors()
        return False


def _cleanup_actors():
    """Destroy all spawned actors safely."""
    ctx["control_thread"] = None

    actors_to_destroy = []

    if ctx["camera"] is not None:
        actors_to_destroy.append(("camera", ctx["camera"]))
        ctx["camera"] = None
    if ctx["vehicle"] is not None:
        actors_to_destroy.append(("vehicle", ctx["vehicle"]))
        ctx["vehicle"] = None
    if ctx["lead_vehicle"] is not None:
        actors_to_destroy.append(("lead_vehicle", ctx["lead_vehicle"]))
        ctx["lead_vehicle"] = None

    for name, actor in actors_to_destroy:
        try:
            if actor.is_alive:
                actor.destroy()
                logger.info("Destroyed %s", name)
        except Exception as e:
            logger.warning("Could not destroy %s: %s", name, e)

    with state_lock:
        state["scenario_running"] = False
        state["frame_bytes"] = None


def end_scenario() -> str | None:
    """Full stop: save CSV, destroy actors, reset state."""
    from .recording import stop_recording_and_save
    result = stop_recording_and_save()
    filepath = result[0] if isinstance(result, tuple) else result
    if filepath is None:
        logger.warning("stop_recording_and_save returned no data")
    _cleanup_actors()

    with state_lock:
        state["autopilot_engaged"] = True
        state["tor_phase"] = "idle"
        state["tor_countdown_s"] = 0

    logger.info("Scenario ended and reset.")
    return filepath
