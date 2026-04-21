"""OCR accuracy validation (Task 6 — PaddleOCR).

Requires labeled screenshots in engine/tests/fixtures/screenshots/*.png
with matching sidecar JSON files containing ground-truth values.

All tests here skip gracefully when no corpus exists so CI never breaks.
Build the corpus (>=20 screenshots + JSON sidecars) before expecting results.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_TFTROOT = Path(__file__).resolve().parents[3]
if str(_TFTROOT) not in sys.path:
    sys.path.insert(0, str(_TFTROOT))

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "screenshots"

FIELDS_CHECKED = ("gold", "hp", "level")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_corpus() -> list[tuple[str, object, dict]]:
    """Return [(filename, img_ndarray, ground_truth_dict), ...]."""
    pairs: list[tuple[str, object, dict]] = []
    if not FIXTURE_DIR.exists():
        return pairs
    try:
        import cv2  # type: ignore[import]
    except ImportError:
        return pairs
    for png in sorted(FIXTURE_DIR.glob("*.png")):
        sidecar = png.with_suffix(".json")
        if not sidecar.exists():
            continue
        img = cv2.imread(str(png))
        if img is None:
            continue
        truth = json.loads(sidecar.read_text(encoding="utf-8"))
        pairs.append((png.name, img, truth))
    return pairs


def _skip_no_corpus(pairs) -> None:
    if not pairs:
        pytest.skip("no labeled screenshot corpus in engine/tests/fixtures/screenshots/")


# ── Wrappers availability ──────────────────────────────────────────────────────

def test_read_int_hybrid_importable():
    """read_int_hybrid must be importable — even if PaddleOCR is missing."""
    from ocr_helpers import read_int_hybrid  # noqa: F401  (import is the test)
    assert callable(read_int_hybrid)


def test_read_text_paddle_importable():
    from ocr_helpers import read_text_paddle  # noqa: F401
    assert callable(read_text_paddle)


def test_read_int_tesseract_importable():
    from ocr_helpers import read_int_tesseract  # noqa: F401
    assert callable(read_int_tesseract)


def test_paddle_returns_none_on_blank_image():
    """read_int_paddle must return None (not raise) on a blank ndarray."""
    import numpy as np
    from ocr_helpers import read_int_paddle
    blank = np.zeros((30, 80, 3), dtype=np.uint8)
    result = read_int_paddle(blank)
    assert result is None


def test_hybrid_returns_none_on_blank_image():
    """read_int_hybrid must return None (not raise) on a blank ndarray."""
    import numpy as np
    from ocr_helpers import read_int_hybrid
    blank = np.zeros((30, 80, 3), dtype=np.uint8)
    result = read_int_hybrid(blank, field_name="test_blank")
    assert result is None


# ── Corpus-dependent tests (skipped without fixtures) ─────────────────────────

def test_corpus_has_enough_screenshots():
    """Corpus sanity check — requires ≥10 labeled PNGs before accuracy tests run."""
    pairs = _load_corpus()
    if not pairs:
        pytest.skip("no corpus")
    if len(pairs) < 10:
        pytest.skip(f"corpus too small ({len(pairs)} < 10); add more labeled screenshots")
    # If we get here the corpus is present and large enough; just pass.
    assert len(pairs) >= 10


@pytest.mark.parametrize("field", FIELDS_CHECKED)
def test_paddle_field_accuracy_per_screenshot(field):
    """PaddleOCR must match ground truth for each labeled screenshot (per-field)."""
    pytest.importorskip("cv2")
    pairs = _load_corpus()
    _skip_no_corpus(pairs)

    from ocr_helpers import read_int_hybrid

    mismatches = []
    checked = 0
    for name, img, truth in pairs:
        if field not in truth:
            continue
        # Caller is responsible for cropping ROIs; here we use full image as
        # a stand-in until crop helpers exist. Accuracy tests only matter once
        # crop helpers (vision_regions.py) are added.
        result = read_int_hybrid(img, field_name=field)
        checked += 1
        if result != truth[field]:
            mismatches.append(f"{name}: predicted={result}, truth={truth[field]}")

    if checked == 0:
        pytest.skip(f"no ground-truth for '{field}' in corpus")
    assert not mismatches, "\n".join(mismatches)


def test_ocr_aggregate_accuracy():
    """Aggregate OCR accuracy across all fields must be ≥98%."""
    pytest.importorskip("cv2")
    pairs = _load_corpus()
    if len(pairs) < 10:
        pytest.skip("need ≥10 labeled screenshots")

    from ocr_helpers import read_int_hybrid

    correct = total = 0
    for _name, img, truth in pairs:
        for field in FIELDS_CHECKED:
            if field not in truth:
                continue
            total += 1
            result = read_int_hybrid(img, field_name=field)
            if result == truth[field]:
                correct += 1

    if total == 0:
        pytest.skip("no ground-truth fields found in corpus")

    accuracy = correct / total
    assert accuracy >= 0.98, f"Aggregate OCR accuracy {accuracy:.1%} below 98% threshold"
