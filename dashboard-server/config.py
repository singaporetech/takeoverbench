"""
config.py
Cross-platform configuration for TakeoverBench.
Reads from .env file (python-dotenv) with sensible defaults for Windows-native.
"""

import os
import socket
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent / ".env")

CARLA_HOST = os.getenv("CARLA_HOST", "127.0.0.1")
CARLA_PORT = int(os.getenv("CARLA_PORT", "2000"))

FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))

MQTT_HOST = os.getenv("MQTT_HOST", CARLA_HOST)
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# Port kill behaviour: ask | kill | skip
MQTT_PORT_KILL_MODE = os.getenv("MQTT_PORT_KILL_MODE", "ask")

# URL encoded in the QR code printed on session reports. Leave empty to
# auto-use this server's /results page on the LAN.
REPORT_QR_URL = os.getenv("REPORT_QR_URL", "")


# Runtime override for the QR target (set from the dashboard; not persisted).
_qr_url_override = ""


def lan_ip() -> str:
    """Best-effort LAN IP of this machine (falls back to loopback)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def _normalise_results_url(url: str) -> str:
    """If given just a base URL, point it at /results."""
    if not url:
        return ""
    from urllib.parse import urlparse, urlunparse

    p = urlparse(url)
    if p.scheme and p.netloc and p.path in ("", "/"):
        return urlunparse((p.scheme, p.netloc, "/results", "", "", ""))
    return url


def set_qr_url(url: str) -> str:
    """Set the runtime QR URL (empty clears it). Returns the active URL."""
    global _qr_url_override
    _qr_url_override = _normalise_results_url((url or "").strip())
    return results_url()


def results_url() -> str:
    """URL participants should reach for their results (QR target).

    Priority: runtime override (dashboard field) > REPORT_QR_URL (.env) >
    this machine's LAN address.
    """
    if _qr_url_override:
        return _qr_url_override
    if REPORT_QR_URL:
        return _normalise_results_url(REPORT_QR_URL)
    host = FLASK_HOST if FLASK_HOST not in ("", "0.0.0.0", "::") else lan_ip()
    return f"http://{host}:{FLASK_PORT}/results"

# Output directory for telemetry CSVs
RUNS_DIR = Path(__file__).resolve().parent / "runs"
RUNS_DIR.mkdir(exist_ok=True)


def get_session_dir(participant_id: str = "unknown") -> Path:
    """Create and return ``runs/{date}_{participant_id}/`` for the current session.

    The folder is created once per session (on first run start) and reused
    for all subsequent runs in that session.
    """
    date_str = datetime.now().strftime("%Y%m%d")
    folder_name = f"{date_str}_{participant_id}" if participant_id else date_str
    session_dir = RUNS_DIR / folder_name
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir
