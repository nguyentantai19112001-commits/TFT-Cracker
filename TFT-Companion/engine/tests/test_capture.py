"""Tests for vision.py screen capture (Task 5 — DXcam).

DXcam-specific tests are skipped on non-Windows platforms. The mss fallback
import test runs on any platform.
"""
from __future__ import annotations

import platform
import sys
from pathlib import Path

_TFTROOT = Path(__file__).resolve().parents[2]
if str(_TFTROOT) not in sys.path:
    sys.path.insert(0, str(_TFTROOT))

import pytest
import numpy as np


@pytest.mark.skipif(
    platform.system() != "Windows",
    reason="DXcam is Windows-only (Desktop Duplication API)",
)
def test_capture_returns_ndarray():
    """capture_screen() returns valid PNG bytes on Windows."""
    from vision import capture_screen
    frame = capture_screen()
    assert isinstance(frame, bytes), "capture_screen must return bytes"
    assert frame[:4] == b"\x89PNG", "output must be PNG-formatted bytes"


@pytest.mark.skipif(
    platform.system() != "Windows",
    reason="DXcam is Windows-only",
)
def test_capture_is_reasonably_fast():
    """Warm capture should complete in under 500ms per call.

    500ms is deliberately generous for the test environment:
    - DXcam returns None when no full-screen game is running (screen not updating).
    - The mss fallback + PIL PNG encode on a 1080p desktop takes ~200-300ms.
    - On a live TFT session DXcam grabs at ~4ms; 500ms guards against broken setup.
    """
    import time
    from vision import capture_screen

    capture_screen()          # warm up camera + encoder
    t0 = time.perf_counter()
    for _ in range(3):
        capture_screen()
    elapsed_ms = (time.perf_counter() - t0) * 1000 / 3
    assert elapsed_ms < 500, f"capture too slow: {elapsed_ms:.1f}ms average"


def test_mss_fallback_importable():
    """_mss_fallback is importable and callable (not necessarily invokable in CI)."""
    from vision import _mss_fallback
    assert callable(_mss_fallback)


def test_release_camera_safe_to_call_twice():
    """release_camera() must be idempotent — calling it twice must not crash."""
    from vision import release_camera
    release_camera()
    release_camera()  # second call must be a no-op


def test_use_dxcam_flag_exists():
    """USE_DXCAM flag must exist so rollback is a one-line change."""
    import vision
    assert hasattr(vision, "USE_DXCAM"), "USE_DXCAM flag must exist in vision.py"
    assert isinstance(vision.USE_DXCAM, bool)
