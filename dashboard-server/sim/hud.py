"""sim/hud.py — participant-facing message drawn inside the CARLA window.

The CARLA window runs fullscreen on the participant's monitor, so end-of-run
messages belong there (not on the evaluator dashboard). Text is rendered with
the CARLA DebugHelper as world-space billboard text placed in front of the
spectator camera and redrawn every telemetry tick so it persists on screen.
"""

import logging
import math

import carla

logger = logging.getLogger(__name__)

_message: str | None = None

# Distance in front of the spectator camera, and height above it.
_HUD_DISTANCE_M = 12.0
_HUD_HEIGHT_M = 1.2
# Slightly longer than one tick so the text never flickers between redraws.
_HUD_LIFE_TIME_S = 0.2


def set_message(text: str) -> None:
    """Show *text* in the CARLA window until cleared."""
    global _message
    _message = text or None


def clear_message() -> None:
    """Remove the on-screen message."""
    global _message
    _message = None


def get_message() -> str | None:
    """Return the current message, or None."""
    return _message


def draw(world) -> None:
    """Redraw the current message in front of the spectator camera.

    Safe to call every tick; no-op when there is no message or no world.
    """
    if _message is None or world is None:
        return
    try:
        t = world.get_spectator().get_transform()
        yaw = math.radians(t.rotation.yaw)
        location = carla.Location(
            x=t.location.x + _HUD_DISTANCE_M * math.cos(yaw),
            y=t.location.y + _HUD_DISTANCE_M * math.sin(yaw),
            z=t.location.z + _HUD_HEIGHT_M,
        )
        world.debug.draw_string(
            location,
            _message,
            draw_shadow=True,
            color=carla.Color(255, 255, 255),
            life_time=_HUD_LIFE_TIME_S,
        )
    except Exception:
        logger.debug("HUD draw failed", exc_info=True)
