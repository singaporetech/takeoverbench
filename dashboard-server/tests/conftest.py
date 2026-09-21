"""Shared pytest setup for TakeoverBench.

``sim`` imports the CARLA Python API, which is a Windows-only dependency for
this project. These tests exercise pure-Python metric logic, so we install a
stub ``carla`` module and put the server package on ``sys.path`` before any
``sim`` import happens.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Make ``import sim`` work when pytest is invoked from the repo root or tests/.
_SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVER_ROOT))

# Stub CARLA (module-level attribute access only; no real API needed).
if "carla" not in sys.modules:
    sys.modules["carla"] = MagicMock(name="carla")
