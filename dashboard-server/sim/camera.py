"""Camera attachment, frame processing, and spectator view following."""
import logging
import math
import numpy as np
import carla
from sim.constants import CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FOV, CAMERA_JPEG_QUALITY
from sim.constants import CAMERA_POV_X, CAMERA_POV_Y, CAMERA_POV_Z
from sim.constants import CAMERA_CHASE_X, CAMERA_CHASE_Y, CAMERA_CHASE_Z, CAMERA_CHASE_PITCH
from sim.constants import CAMERA_SPECTATOR_INITIAL_Z, CAMERA_SPECTATOR_INITIAL_PITCH
from .state import state, state_lock, ctx

logger = logging.getLogger(__name__)

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("OpenCV (cv2) not available — video feed will show black frames only")


def _attach_camera(mode: str = "chase") -> None:
    """Attach RGB camera to the ego vehicle."""
    if ctx["camera"] is not None:
        try:
            ctx["camera"].stop()
            ctx["camera"].destroy()
        except Exception:
            logger.debug("Error destroying previous camera", exc_info=True)
        ctx["camera"] = None

    try:
        cam_bp = ctx["world"].get_blueprint_library().find("sensor.camera.rgb")
        cam_bp.set_attribute("image_size_x", str(CAMERA_WIDTH))
        cam_bp.set_attribute("image_size_y", str(CAMERA_HEIGHT))
        cam_bp.set_attribute("fov", str(CAMERA_FOV))

        if mode == "pov":
            cam_transform = carla.Transform(
                carla.Location(x=CAMERA_POV_X, y=CAMERA_POV_Y, z=CAMERA_POV_Z),
                carla.Rotation(pitch=0)
            )
        else:
            cam_transform = carla.Transform(
                carla.Location(x=CAMERA_CHASE_X, y=CAMERA_CHASE_Y, z=CAMERA_CHASE_Z),
                carla.Rotation(pitch=CAMERA_CHASE_PITCH)
            )

        ctx["camera"] = ctx["world"].spawn_actor(
            cam_bp, cam_transform,
            attach_to=ctx["vehicle"],
            attachment_type=carla.AttachmentType.SpringArmGhost
            if mode == "chase" else carla.AttachmentType.Rigid
        )
        ctx["camera"].listen(_on_camera_frame)
        logger.info("Camera attached — mode: %s", mode)

    except Exception as e:
        logger.error("Camera attach error: %s", e)


def _on_camera_frame(image: carla.Image) -> None:
    """Camera callback — convert to JPEG and store in shared state."""
    if not CV2_AVAILABLE:
        return
    try:
        array = np.frombuffer(image.raw_data, dtype=np.uint8)
        array = array.reshape((image.height, image.width, 4))
        bgr = array[:, :, :3]
        _, jpeg = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, CAMERA_JPEG_QUALITY])
        with state_lock:
            state["frame_bytes"] = jpeg.tobytes()
    except Exception:
        logger.debug("Camera frame processing error", exc_info=True)


def _start_spectator_follow(mode: str = "chase") -> None:
    """Move CARLA's spectator view to follow the ego vehicle.

    Stores the update function in ``ctx["spectator_update"]`` so the
    telemetry loop calls it once per ``world.tick()`` — no thread, no race.
    """
    ctx["spectator_mode"] = mode
    spectator = ctx["world"].get_spectator()

    # Initial position
    try:
        t = ctx["vehicle"].get_transform()
        if mode == "pov":
            yaw_rad = math.radians(t.rotation.yaw)
            spectator.set_transform(carla.Transform(
                carla.Location(
                    x=t.location.x + 0.5 * math.cos(yaw_rad),
                    y=t.location.y + 0.5 * math.sin(yaw_rad),
                    z=t.location.z + 1.6
                ),
                carla.Rotation(pitch=0, yaw=t.rotation.yaw, roll=0)
            ))
        else:
            spectator.set_transform(carla.Transform(
                t.location + carla.Location(z=CAMERA_SPECTATOR_INITIAL_Z),
                carla.Rotation(pitch=CAMERA_SPECTATOR_INITIAL_PITCH, yaw=t.rotation.yaw)
            ))
    except Exception:
        logger.debug("Spectator initial position error", exc_info=True)

    def _update():
        """Read vehicle transform and reposition spectator.
        Called from telemetry_loop after each world.tick()."""
        if ctx["vehicle"] is None or not state.get("scenario_running"):
            return
        try:
            if not ctx["vehicle"].is_alive:
                return
            t = ctx["vehicle"].get_transform()
            spectator = ctx["world"].get_spectator()
            if mode == "pov":
                yaw_rad = math.radians(t.rotation.yaw)
                spectator.set_transform(carla.Transform(
                    carla.Location(
                        x=t.location.x + 0.5 * math.cos(yaw_rad),
                        y=t.location.y + 0.5 * math.sin(yaw_rad),
                        z=t.location.z + 1.6
                    ),
                    carla.Rotation(pitch=0, yaw=t.rotation.yaw, roll=0)
                ))
            else:
                yaw_rad = math.radians(t.rotation.yaw)
                spectator.set_transform(carla.Transform(
                    carla.Location(
                        x=t.location.x + CAMERA_CHASE_X * math.cos(yaw_rad),
                        y=t.location.y + CAMERA_CHASE_X * math.sin(yaw_rad),
                        z=t.location.z + CAMERA_CHASE_Z
                    ),
                    carla.Rotation(pitch=CAMERA_CHASE_PITCH, yaw=t.rotation.yaw)
                ))
        except Exception:
            pass

    ctx["spectator_update"] = _update
