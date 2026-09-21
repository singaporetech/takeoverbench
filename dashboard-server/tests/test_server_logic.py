"""Tests for small pure server helpers (no CARLA, no network).

Importing ``server`` pulls in Flask and the ``sim`` package; skipped when
Flask is not installed in the current environment.
"""
from __future__ import annotations

import pytest

pytest.importorskip("flask")


def _state(queue, idx, running):
    return {"preset_queue": list(queue), "active_preset_index": idx,
            "scenario_running": running}


def test_next_preset_while_running():
    from server import _get_next_preset

    # Running run index 0 -> next is index 1.
    p = _get_next_preset(_state([0, 2, 3], 0, True))
    assert p is not None and p["id"] == 2


def test_next_preset_when_idle_uses_current_index():
    from server import _get_next_preset

    # Telemetry advanced the index to 1 at auto-end -> next is index 1 (Moderate),
    # not index 2 (Hard).
    p = _get_next_preset(_state([0, 2, 3], 1, False))
    assert p is not None and p["id"] == 2


def test_next_preset_none_at_end_of_set():
    from server import _get_next_preset

    assert _get_next_preset(_state([0, 2, 3], 3, False)) is None


def test_next_preset_none_for_empty_queue():
    from server import _get_next_preset

    assert _get_next_preset(_state([], 0, False)) is None
