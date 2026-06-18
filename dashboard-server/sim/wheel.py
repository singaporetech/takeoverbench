"""
sim/wheel.py — Logitech G29 / Keyboard fallback via pygame.

Initialization (``init()``) **must** happen in the main thread.
If no steering wheel is detected, it automatically falls back to
keyboard control (WASD or Arrow Keys) via a small focus window.
"""

import logging
import carla

logger = logging.getLogger(__name__)

_wheel = None
_init_done: bool = False
_tick: int = 0
_use_keyboard: bool = False


def init() -> None:
    """Initialise pygame and connect to the wheel, or fallback to keyboard."""
    global _init_done, _wheel, _use_keyboard
    import pygame

    # --- THE FIX IS HERE ---
    if _init_done:
        print("[WHEEL] Pygame already initialised, keeping existing wheel connection.")
        return 
    # -----------------------

    pygame.init()
    _init_done = True
    print(f"[WHEEL] pygame {pygame.version.ver} initialised")

    if pygame.joystick.get_count() > 0:
        try:
            _wheel = pygame.joystick.Joystick(0)
            _wheel.init()
            _use_keyboard = False
            print(f"[WHEEL] Connected to: {_wheel.get_name()}")
        except Exception:
            _use_keyboard = True
            print("[WHEEL] Joystick detected but failed to init. Falling back to KEYBOARD (WASD).")
    else:
        _use_keyboard = True
        print("[WHEEL] No joystick found. Falling back to KEYBOARD (WASD).")

    if _use_keyboard:
        pygame.display.set_mode((350, 150))
        pygame.display.set_caption("CLICK HERE FOR WASD CONTROL")

def read() -> carla.VehicleControl | None:
    """Read current wheel / pedal positions, or keyboard state.

    Returns a ``VehicleControl`` with steer [-1, 1], throttle [0, 1],
    and brake [0, 1].
    """
    global _tick
    try:
        import pygame
        pygame.event.pump()

        # ── KEYBOARD FALLBACK ──
        if _use_keyboard:
            keys = pygame.key.get_pressed()
            steer = 0.0
            throttle = 0.0
            brake = 0.0

            if keys[pygame.K_w] or keys[pygame.K_UP]:
                throttle = 1.0
            if keys[pygame.K_s] or keys[pygame.K_DOWN]:
                brake = 1.0
            if keys[pygame.K_a] or keys[pygame.K_LEFT]:
                steer = -1.0
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                steer = 1.0

            return carla.VehicleControl(
                steer=steer,
                throttle=throttle,
                brake=brake,
                hand_brake=False,
                reverse=False,
                manual_gear_shift=False,
            )

        # ── PHYSICAL WHEEL ──
        elif _wheel is not None:
            steer_raw    = _wheel.get_axis(0)       # -1 left,  +1 right
            throttle_raw = _wheel.get_axis(1)       # -1 rest,  +1 pressed
            brake_raw    = _wheel.get_axis(2)       # -1 rest,  +1 pressed

            _tick += 1
            if _tick % 60 == 0:
                logger.info("WHEEL raw — steer=%.3f throttle=%.3f brake=%.3f",
                            steer_raw, throttle_raw, brake_raw)

            # Normalise pedals from [-1, 1] to [0, 1]
            throttle = (-throttle_raw + 1.0) / 2.0
            brake    = (-brake_raw + 1.0) / 2.0

            return carla.VehicleControl(
                steer=steer_raw,
                throttle=max(0.0, min(1.0, throttle)),
                brake=max(0.0, min(1.0, brake)),
                hand_brake=False,
                reverse=False,
                manual_gear_shift=False,
            )

        return None

    except Exception as e:
        logger.error("Wheel/Keyboard read error: %s", e)
        return None
