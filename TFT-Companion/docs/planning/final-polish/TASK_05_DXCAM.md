# TASK_05_DXCAM.md — Swap `mss` for `DXcam`

> Faster screen capture. Benchmarks show ~239 FPS vs mss's ~76 FPS at 1080p.
> Latency per capture drops from ~13ms to ~4ms. Worth the switch.

---

## Prereq checks

```bash
pytest -q                          # 121/121
python -c "import platform; print(platform.system())"   # must be Windows
python -c "import mss; print('mss present')"            # current capture lib
```

If not Windows, STOP — DXcam is Windows-only (uses Desktop Duplication API).

## Files you may edit

- `vision.py` or wherever `mss` is currently imported for capture
- `requirements.txt` or `pyproject.toml` (swap `mss` → `dxcam`)
- `tests/test_capture.py` (new or extend existing)
- `STATE.md`

## The change

### Install

```bash
pip install dxcam
```

Keep `mss` in requirements as a fallback for now — safer to allow instant
rollback if DXcam has issues on the user's specific Windows version.

### Current code (typical mss pattern)

```python
import mss
import numpy as np

def capture_screen() -> np.ndarray:
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        screenshot = sct.grab(monitor)
        return np.array(screenshot)
```

### New code (DXcam pattern)

```python
import dxcam
import numpy as np
from typing import Optional

_CAMERA: Optional[dxcam.DXCamera] = None

def _get_camera() -> dxcam.DXCamera:
    """Lazy, singleton DXCamera. One instance reused across F9 presses.

    Creating a DXCamera is expensive (~100ms) but grabs are ~4ms. So we
    create once at startup/first-use and reuse forever.
    """
    global _CAMERA
    if _CAMERA is None:
        _CAMERA = dxcam.create(output_color="RGB")
    return _CAMERA


def capture_screen() -> np.ndarray:
    """Capture primary monitor. Returns HxWx3 RGB ndarray."""
    cam = _get_camera()
    frame = cam.grab()
    # DXcam returns None if the frame hasn't changed since last grab.
    # On F9 press, we want the latest frame regardless — force a fresh one.
    if frame is None:
        # Request a new frame by sleeping a few ms and trying again
        import time
        time.sleep(0.01)
        frame = cam.grab()
    if frame is None:
        # Fall back to mss on unexpected DXcam failure
        return _mss_fallback()
    return frame


def _mss_fallback() -> np.ndarray:
    """Fallback if DXcam returns None repeatedly — should be rare."""
    import mss
    import numpy as np
    with mss.mss() as sct:
        screenshot = sct.grab(sct.monitors[1])
        # mss returns BGRA; convert to RGB
        arr = np.array(screenshot)
        return arr[:, :, [2, 1, 0]]  # BGRA -> RGB by slicing
```

### Important caveats to note in code comments

1. DXcam's `grab()` can return `None` if the frame hasn't changed — the
   retry logic above handles it.
2. DXCamera creation is expensive; singleton pattern is mandatory.
3. If the user has multiple monitors, you may need `dxcam.create(device_idx=0, output_idx=N)` to pick the right one. For v1 assume primary; add UI for monitor selection in a future task if needed.
4. DXcam lives in user-space; it doesn't require elevation. If permission errors occur, check Windows Graphics Capture policy.

### Shutdown hook

DXcam cameras should be released cleanly when the app exits:

```python
def release_camera():
    global _CAMERA
    if _CAMERA is not None:
        _CAMERA.release()
        _CAMERA = None
```

Wire this into the existing overlay shutdown / QApplication aboutToQuit signal.

### Tests

```python
# tests/test_capture.py (add to existing, or create new)
import numpy as np
import pytest
import platform


@pytest.mark.skipif(
    platform.system() != "Windows",
    reason="DXcam is Windows-only"
)
def test_capture_returns_ndarray():
    from vision import capture_screen
    frame = capture_screen()
    assert isinstance(frame, np.ndarray)
    assert frame.ndim == 3  # H, W, 3
    assert frame.shape[2] == 3  # RGB channels


@pytest.mark.skipif(
    platform.system() != "Windows",
    reason="DXcam is Windows-only"
)
def test_capture_is_fast():
    """Capture latency should be under 20ms after warm-up."""
    from vision import capture_screen
    import time
    # Warm up
    capture_screen()
    # Measure
    t0 = time.perf_counter()
    for _ in range(5):
        capture_screen()
    elapsed_ms = (time.perf_counter() - t0) * 1000 / 5
    assert elapsed_ms < 20, f"Capture too slow: {elapsed_ms:.1f}ms per frame"


def test_mss_fallback_available():
    """Fallback is importable even if DXcam is primary."""
    from vision import _mss_fallback
    # Don't call it in CI (no display), just import-check
    assert callable(_mss_fallback)
```

## Acceptance gate

1. `pytest -q` shows 124/124 passing (121 + 3 new, assuming Windows).
2. Manual F9 test: measure latency before/after, capture step should
   drop from ~13ms to ~4-8ms.
3. App shutdown cleanly (no "camera not released" warnings).
4. `pip list | grep -E "mss|dxcam"` shows both installed.

## Rollback if needed

If DXcam fails on the user's Windows version:
```python
# In capture_screen():
USE_DXCAM = False  # set to False to force mss fallback
```

Add this flag explicitly so rollback is one-line.

## Commit message

```
Task 5: swap mss for DXcam screen capture

- Capture latency drops from ~13ms to ~4ms (Desktop Duplication API)
- Singleton camera pattern; init cost amortized
- mss remains installed as fallback for robustness
- 3 new tests (skipped on non-Windows CI)

Tests: 121 → 124. F9 feel slightly snappier.
```
