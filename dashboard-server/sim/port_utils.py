"""
sim/port_utils.py
Port management utilities for TakeoverBench.
Detects, inspects, and frees ports used by CARLA or the embedded MQTT broker.
"""

import logging
import re
import socket
import subprocess
import time

logger = logging.getLogger(__name__)


def _port_in_use(host: str, port: int) -> bool:
    """Check if a TCP port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def _get_port_process_info(port: int) -> list[tuple[int, str]]:
    """Return list of (pid, exe_name) for all processes on the given port.

    Windows only — uses ``netstat`` and ``tasklist``.
    Returns an empty list on non-Windows platforms.
    """
    results: list[tuple[int, str]] = []
    try:
        output = subprocess.check_output(
            f'netstat -ano | findstr ":{port} "',
            shell=True, text=True, stderr=subprocess.DEVNULL,
        )
        for line in output.strip().split("\n"):
            parts = re.split(r"\s+", line.strip())
            if len(parts) >= 5 and "LISTENING" in line:
                pid = int(parts[-1])
                try:
                    out2 = subprocess.check_output(
                        f'tasklist /FI "PID eq {pid}" /NH',
                        shell=True, text=True, stderr=subprocess.DEVNULL,
                    )
                    exe = out2.strip().split()[0] if out2.strip() else "?"
                except Exception:
                    exe = "?"
                results.append((pid, exe))
    except Exception:
        pass
    return results


def _kill_process(pid: int, label: str = "") -> bool:
    """Kill a process by PID using ``taskkill``. Returns True if successful."""
    for cmd in [f"taskkill /PID {pid} /F", f"taskkill /PID {pid} /F /T"]:
        try:
            subprocess.run(cmd, shell=True, check=True, capture_output=True, timeout=10)
            time.sleep(0.5)
            return True
        except subprocess.CalledProcessError:
            continue
    return False


def ensure_port_free(host: str, port: int, mode: str, label: str) -> bool:
    """Check and optionally free a port.

    Parameters
    ----------
    host, port :
        The address to check.
    mode :
        ``"skip"`` — leave it alone, ``"ask"`` — prompt the user,
        ``"kill"`` — kill the process automatically.
    label :
        Human-readable name for log messages (e.g. ``"MQTT"``).

    Returns True if the port is free (or was successfully freed).
    """
    if not _port_in_use(host, port):
        return True

    procs = _get_port_process_info(port)

    for pid, exe in procs:
        if mode == "skip":
            logger.info("%s %s:%s in use%s — skipping", label, host, port,
                        f" ({exe}, PID {pid})" if exe else f" (PID {pid})")
            continue
        if mode == "ask":
            logger.warning("%s %s:%s in use by PID %s — set MQTT_PORT_KILL_MODE=kill to auto-free",
                           label, host, port, pid)
            continue

        if _kill_process(pid, label):
            logger.info("Killed PID %s — %s %s:%s freed", pid, label, host, port)

    # Final recheck
    time.sleep(0.2)
    if not _port_in_use(host, port):
        logger.info("Port %s:%s free after cleanup", host, port)
        return True

    pids_left = [p[0] for p in _get_port_process_info(port)]
    logger.warning("Port %s:%s still in use by PID(s) %s — kill manually", host, port, pids_left)
    return False
