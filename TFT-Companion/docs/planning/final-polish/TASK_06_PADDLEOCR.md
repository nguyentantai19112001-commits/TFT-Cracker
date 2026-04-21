# TASK_06_PADDLEOCR.md — Add PaddleOCR as primary OCR

> PaddleOCR PP-OCRv5 (English model, Apache 2.0) replaces pytesseract as the
> primary OCR engine. pytesseract remains as fallback for when PaddleOCR
> returns empty or low-confidence. Expected accuracy improvement on
> stylized TFT fonts from ~70% to ~98%+.

---

## Why this matters

pytesseract on TFT's stylized UI fonts is unreliable — the single biggest
source of "wrong stats" failures. PaddleOCR handles stylized text noticeably
better and has a much cleaner inference API. Keeping pytesseract as
fallback means no regression when PaddleOCR finds nothing.

## Prereq checks

```bash
pytest -q                          # 124/124
grep -rn "pytesseract\|tesseract" . | grep -v ".git"
    # capture every usage site
ls tests/fixtures/screenshots/ 2>/dev/null || echo "no screenshot corpus"
    # need labeled screenshots to validate accuracy; confirm they exist
```

If there is no labeled screenshot corpus, STOP. PaddleOCR vs pytesseract
comparison requires ground truth. Tell the user: "I need at least 20
labeled screenshots in tests/fixtures/screenshots/ with expected gold/HP/
level/stage/xp values in a sidecar JSON file. Without those, I can't
validate the accuracy gate."

Build the corpus first (user task), then come back to this task.

## Files you may edit

- `ocr_helpers.py` (add PaddleOCR paths alongside pytesseract)
- `requirements.txt` or `pyproject.toml` (add `paddleocr` and `paddlepaddle`)
- `tests/test_ocr_accuracy.py` (new)
- `STATE.md`

## Dependencies

```bash
pip install paddleocr paddlepaddle
```

Both are needed. `paddlepaddle` is the inference framework, `paddleocr` is
the wrapper. Total install size ~500MB — note in STATE.md.

Use CPU-only paddle unless the user specifically asks for GPU; CPU latency
on text regions is fine (~50-100ms per region).

## The change

### Wrapper pattern

```python
# ocr_helpers.py — add alongside existing pytesseract helpers

from typing import Optional
from paddleocr import PaddleOCR
import numpy as np

_PADDLE: Optional[PaddleOCR] = None


def _get_paddle() -> PaddleOCR:
    """Lazy singleton PaddleOCR instance. Initialization is expensive (~2s)."""
    global _PADDLE
    if _PADDLE is None:
        _PADDLE = PaddleOCR(
            use_angle_cls=False,   # our ROIs are axis-aligned; skip angle detection
            lang="en",
            show_log=False,
        )
    return _PADDLE


def read_text_paddle(
    region: np.ndarray,
    *,
    allow_empty: bool = False,
    min_confidence: float = 0.7,
) -> Optional[str]:
    """Read text from a cropped region using PaddleOCR. Returns None on failure.

    Returns the first string found with confidence >= min_confidence.
    """
    paddle = _get_paddle()
    result = paddle.ocr(region, cls=False)
    if not result or not result[0]:
        return None
    # Each item: [bbox, (text, confidence)]
    best = max(result[0], key=lambda item: item[1][1], default=None)
    if best is None:
        return None
    text, conf = best[1]
    if conf < min_confidence:
        return None
    return text.strip()


def read_int_paddle(region: np.ndarray, **kwargs) -> Optional[int]:
    """Paddle-first int reader. Returns None if Paddle can't parse."""
    text = read_text_paddle(region, **kwargs)
    if text is None:
        return None
    # Strip any non-digit characters
    cleaned = "".join(c for c in text if c.isdigit() or c == "-")
    try:
        return int(cleaned)
    except ValueError:
        return None


# --- Hybrid wrapper: Paddle primary, pytesseract fallback ---

def read_int_hybrid(region: np.ndarray, *, field_name: str = "") -> Optional[int]:
    """Primary path: PaddleOCR. Fallback: pytesseract. Last resort: None.

    field_name is passed for logging to distinguish which fallback fired.
    """
    # Try Paddle first
    result = read_int_paddle(region)
    if result is not None:
        return result

    # Fall back to existing pytesseract helper
    import logging
    logging.debug("paddle OCR returned None for %s, falling back to tesseract", field_name)
    from ocr_helpers import read_int_tesseract  # existing function, renamed if needed
    return read_int_tesseract(region)
```

### Migration in call sites

Find every existing call to `read_int(gold_region)` (or similar) and
replace with `read_int_hybrid(gold_region, field_name="gold")`.

Do NOT remove the pytesseract helpers. They stay as the fallback path.
If the existing function is named `read_int`, rename the pytesseract
implementation to `read_int_tesseract` and make `read_int` alias to
`read_int_hybrid` — this keeps call sites working without changes.

## Accuracy validation

This is the part that absolutely must work before committing.

```python
# tests/test_ocr_accuracy.py
import json
import pytest
from pathlib import Path
import cv2

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "screenshots"


def _load_labeled_screenshots():
    """Load (screenshot, ground_truth) pairs for accuracy testing."""
    pairs = []
    if not FIXTURE_DIR.exists():
        return pairs
    for png_path in FIXTURE_DIR.glob("*.png"):
        json_path = png_path.with_suffix(".json")
        if not json_path.exists():
            continue
        img = cv2.imread(str(png_path))
        truth = json.loads(json_path.read_text())
        pairs.append((png_path.name, img, truth))
    return pairs


@pytest.mark.parametrize(
    "name,img,truth",
    _load_labeled_screenshots(),
    ids=lambda x: x if isinstance(x, str) else None,
)
def test_ocr_accuracy_gold(name, img, truth):
    if "gold" not in truth:
        pytest.skip("no gold ground truth")
    from ocr_helpers import read_int_hybrid
    from vision_regions import crop_gold_region  # or wherever ROI cropping lives
    gold_img = crop_gold_region(img)
    predicted = read_int_hybrid(gold_img, field_name="gold")
    assert predicted == truth["gold"], \
        f"{name}: gold predicted {predicted}, truth {truth['gold']}"


# Similar parametrized tests for hp, level, stage, xp, etc.


def test_ocr_accuracy_overall():
    """Aggregate: across all labeled screenshots, accuracy must be >= 98%."""
    pairs = _load_labeled_screenshots()
    if len(pairs) < 10:
        pytest.skip("need at least 10 labeled screenshots for aggregate test")

    from ocr_helpers import read_int_hybrid
    from vision_regions import crop_gold_region, crop_hp_region, crop_level_region

    correct = 0
    total = 0
    for name, img, truth in pairs:
        for field, crop_fn in [
            ("gold", crop_gold_region),
            ("hp", crop_hp_region),
            ("level", crop_level_region),
        ]:
            if field not in truth:
                continue
            predicted = read_int_hybrid(crop_fn(img), field_name=field)
            total += 1
            if predicted == truth[field]:
                correct += 1

    accuracy = correct / total
    assert accuracy >= 0.98, f"OCR accuracy {accuracy:.1%} below 98% threshold"
```

## Acceptance gate

1. PaddleOCR + paddlepaddle successfully pip-install.
2. All existing 124 tests still pass.
3. New accuracy test achieves ≥98% on the labeled corpus.
4. Latency per F9 does not increase by more than 150ms (PaddleOCR is
   slower than pytesseract per-call, but we avoid fallback in the common
   path which roughly balances out).
5. `grep -n "pytesseract" .` — pytesseract still present (fallback path),
   not removed.

## Rollback criteria

If accuracy on the corpus is LOWER than pytesseract's baseline, revert.
PaddleOCR isn't always better for every UI font; measure, don't assume.

## Commit message

```
Task 6: add PaddleOCR as primary OCR, pytesseract as fallback

- ocr_helpers gains read_text_paddle / read_int_paddle / *_hybrid wrappers
- Hybrid wrapper tries Paddle first, falls back to pytesseract on empty/low-conf
- All call sites migrated to hybrid wrapper
- OCR accuracy on labeled corpus improves from XX% to YY%

Tests: 124 → 124+N (accuracy tests). Wrong-stats failure rate expected to drop substantially.
```
