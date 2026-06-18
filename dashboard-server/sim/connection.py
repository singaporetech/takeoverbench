"""CARLA client connection, disconnection, and map loading."""
import logging
import time
import threading
import carla
import config
from sim.constants import (
    CARLA_CONNECT_RETRIES,
    CARLA_CLIENT_TIMEOUT_S,
    CARLA_RETRY_DELAY_S,
    CARLA_MAP_LOAD_WAIT_S,
)
from .state import state, state_lock, ctx

logger = logging.getLogger(__name__)


def _set_sync_mode(world: carla.World) -> None:
    """Configure world for synchronous mode at ~30 Hz."""
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 0.033  # ~30 Hz
    settings.no_rendering_mode = False
    world.apply_settings(settings)
    logger.debug("Synchronous mode set (%s Hz)", round(1 / 0.033))


def _get_available_vehicles(world: carla.World) -> list:
    """Return sorted list of vehicle blueprint IDs, excluding bikes/motorcycles."""
    bp_lib = world.get_blueprint_library()
    return sorted([
        bp.id for bp in bp_lib.filter("vehicle.*")
        if not any(x in bp.id for x in ["bike", "cycle", "motorcycle"])
    ])


def disconnect_carla() -> None:
    """Close CARLA client and clean up gRPC connections."""
    from .scenario import _cleanup_actors
    _cleanup_actors()

    if ctx["client"] is not None:
        try:
            ctx["client"] = None
        except Exception:
            logger.debug("Error cleaning up client reference", exc_info=True)

    ctx["world"] = None
    ctx["telemetry_thread"] = None

    with state_lock:
        state["connected"] = False

    logger.info("Disconnected and cleaned up")


def connect_to_carla(host: str | None = None, port: int = 2000) -> bool:
    """Connect to a CARLA server, load Town06, and start the telemetry loop.

    Only starts a new telemetry thread if none is already running.
    """
    host = host or config.CARLA_HOST
    port = port or config.CARLA_PORT

    disconnect_carla()

    for attempt in range(1, CARLA_CONNECT_RETRIES + 1):
        try:
            logger.info("Connection attempt %d/%d...", attempt, CARLA_CONNECT_RETRIES)

            ctx["client"] = carla.Client(host, port)
            ctx["client"].set_timeout(CARLA_CLIENT_TIMEOUT_S)
            ctx["client"].get_world()

            logger.info("Loading default map: Town06...")
            ctx["world"] = ctx["client"].load_world("Town06")
            time.sleep(CARLA_MAP_LOAD_WAIT_S)

            map_name = ctx["world"].get_map().name
            logger.info("Map loaded: %s", map_name)

            _set_sync_mode(ctx["world"])

            vehicles = _get_available_vehicles(ctx["world"])

            with state_lock:
                state["connected"] = True
                state["available_vehicles"] = vehicles

            # Only start one telemetry thread — skip if already running
            old_thread = ctx.get("telemetry_thread")
            if old_thread is None or not old_thread.is_alive():
                from .telemetry import telemetry_loop
                t = threading.Thread(target=telemetry_loop, daemon=True)
                t.start()
                ctx["telemetry_thread"] = t

            return True

        except Exception as e:
            logger.warning("Attempt %d failed: %s", attempt, e)
            if attempt < CARLA_CONNECT_RETRIES:
                time.sleep(CARLA_RETRY_DELAY_S)

    return False


def load_map(map_name: str) -> None:
    """Load a new CARLA map and refresh vehicle list.

    Does nothing if the client is not connected.
    """
    if ctx["client"] is None:
        logger.warning("load_map called before client is connected")
        return

    try:
        ctx["world"] = ctx["client"].load_world(map_name)
        time.sleep(CARLA_MAP_LOAD_WAIT_S)
        _set_sync_mode(ctx["world"])  # load_world resets settings — re-apply sync mode
        vehicles = _get_available_vehicles(ctx["world"])
        with state_lock:
            state["available_vehicles"] = vehicles
        logger.info("Map changed to: %s", map_name)
    except Exception as e:
        logger.error("Map load failed: %s", e)
