"""
sim/video_feed.py — MJPEG video feed generation for TakeoverBench.

Provides a black placeholder frame and an infinite generator that yields
MJPEG boundary bytes from the latest CARLA camera frame stored in shared state.
"""

import threading
from .state import state, state_lock

_black_frame_cache: bytes | None = None


def black_frame() -> bytes:
    """Return a black JPEG image (800×450) as cached bytes.

    On first call, generates the JPEG via OpenCV. Subsequent calls return
    the cached version. Returns empty bytes if OpenCV/numpy is unavailable.
    """
    global _black_frame_cache
    if _black_frame_cache is None:
        try:
            import numpy as np
            import cv2
            img = np.zeros((450, 800, 3), dtype=np.uint8)
            _, jpeg = cv2.imencode(".jpg", img)
            _black_frame_cache = jpeg.tobytes()
        except Exception:
            _black_frame_cache = b""
    return _black_frame_cache


def frame_generator():
    """Infinite generator yielding MJPEG boundary frames.

    Reads the latest ``frame_bytes`` from shared state (populated by the
    CARLA camera callback) at approximately 30 fps.  Falls back to a black
    frame when no camera data is available.
    """
    while True:
        with state_lock:
            frame = state.get("frame_bytes")
        yield (
            b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
            + (frame if frame else black_frame())
            + b"\r\n"
        )
        threading.Event().wait(0.033)
