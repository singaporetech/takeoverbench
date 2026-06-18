"""
install_carla_api.py
Reads CARLA_PYTHON_EGG from .env and installs the CARLA Python API.
Called by start_server.bat — no batch-level .env parsing needed.
"""

import logging
import os
import re
import subprocess
import sys

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main():
    try:
        with open(".env") as f:
            content = f.read()
    except FileNotFoundError:
        logger.error(".env file not found in current directory")
        return 1

    m = re.search(r"^CARLA_PYTHON_EGG=(.+)", content, re.M)
    if not m:
        logger.error("CARLA_PYTHON_EGG not set in .env")
        logger.error("Add a line like: CARLA_PYTHON_EGG=C:\\path\\to\\carla-0.9.16-cp312-cp312-win_amd64.whl")
        return 1

    path = m.group(1).strip().strip("\"'")
    logger.info("Found in .env: %s", path)

    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", path],
            stdout=subprocess.DEVNULL,
        )
        logger.info("Installation complete.")
        return 0
    except subprocess.CalledProcessError:
        logger.error("Failed to install: %s", path)
        logger.error("Check that the path is correct and your Python version matches the wheel.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
