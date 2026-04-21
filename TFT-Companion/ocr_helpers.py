"""Game-state helpers: LCU API reads, fuzzy-match OCR cleanup, shop reader.

Patterns adapted from jfd02/TFT-OCR-BOT (GPLv3), reimplemented for this project.
See THIRD_PARTY_NOTICES.md.

OCR hierarchy (cheapest-first):
    PaddleOCR  — primary path (read_int_hybrid / read_text_paddle)
    pytesseract — fallback when Paddle returns None or low-confidence
    None        — last resort (callers handle gracefully)
"""

from __future__ import annotations

import logging
import threading
import warnings
from difflib import SequenceMatcher
from typing import Optional

import numpy as np
import requests
from PIL import Image, ImageGrab

import ocr
import screen_coords
from vec4 import Vec4

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

LCU_ENDPOINT = "https://127.0.0.1:2999/liveclientdata/allgamedata"
CHAMP_FUZZY_THRESHOLD = 0.70
ITEM_FUZZY_THRESHOLD = 0.85


def _lcu_get() -> Optional[dict]:
    try:
        response = requests.get(LCU_ENDPOINT, timeout=10, verify=False)
        return response.json()
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,
            ValueError, KeyError):
        return None


def get_level() -> Optional[int]:
    """Tactician level via Riot LCU live client API. None if unreachable."""
    data = _lcu_get()
    if not data:
        return None
    try:
        return int(data["activePlayer"]["level"])
    except (KeyError, TypeError, ValueError):
        return None


def get_health() -> Optional[int]:
    """Tactician HP via Riot LCU live client API. None if unreachable."""
    data = _lcu_get()
    if not data:
        return None
    try:
        return int(data["activePlayer"]["championStats"]["currentHealth"])
    except (KeyError, TypeError, ValueError):
        return None


def get_gold() -> int:
    """Gold via OCR of the gold box. 0 on parse failure."""
    raw = ocr.get_text(bbox=screen_coords.GOLD_POS.get_coords(), scale=3,
                       psm=7, whitelist=ocr.DIGIT_WHITELIST)
    try:
        return int(raw)
    except ValueError:
        return 0


def valid_champ(candidate: str, champions: set[str]) -> str:
    """Fuzzy-match a noisy OCR string to a canonical champion name. '' if no match."""
    if candidate in champions:
        return candidate
    return next(
        (c for c in champions
         if SequenceMatcher(a=c, b=candidate).ratio() >= CHAMP_FUZZY_THRESHOLD),
        "",
    )


def valid_item(candidate: str, items: set[str]) -> Optional[str]:
    """Fuzzy-match an OCR string to a canonical item name. None if no match."""
    return next(
        (item for item in items
         if item in candidate or SequenceMatcher(a=item, b=candidate).ratio() >= ITEM_FUZZY_THRESHOLD),
        None,
    )


def _read_shop_slot(screen: ImageGrab.Image, name_pos: Vec4, slot_index: int,
                    result: list, champions: set[str]) -> None:
    crop = screen.crop(name_pos.get_coords())
    raw = ocr.get_text_from_image(crop, whitelist=ocr.ALPHABET_WHITELIST)
    result.append((slot_index, valid_champ(raw, champions)))


def get_shop(champions: set[str]) -> list[tuple[int, str]]:
    """Read the 5 shop slots in parallel. Returns [(slot_index, champ_name), ...]."""
    screen = ImageGrab.grab(bbox=screen_coords.SHOP_POS.get_coords())
    result: list = []
    threads: list[threading.Thread] = []
    for i, name_pos in enumerate(screen_coords.CHAMP_NAME_POS):
        t = threading.Thread(
            target=_read_shop_slot,
            args=(screen, name_pos, i, result, champions),
        )
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    return sorted(result)


# ── PaddleOCR wrappers ─────────────────────────────────────────────────────────
# PaddleOCR is the primary OCR path; pytesseract is the fallback.
# Import is lazy — if paddleocr isn't installed, the helpers return None and
# callers fall through to tesseract automatically.

_PADDLE: Optional[object] = None


def _get_paddle():
    """Lazy singleton PaddleOCR. Cold start is ~2s; subsequent calls are fast."""
    global _PADDLE
    if _PADDLE is not None:
        return _PADDLE
    try:
        from paddleocr import PaddleOCR  # type: ignore[import]
        _PADDLE = PaddleOCR(use_textline_orientation=False, lang="en", show_log=False)
    except Exception:
        _PADDLE = None
    return _PADDLE


def read_text_paddle(
    region: np.ndarray,
    *,
    allow_empty: bool = False,
    min_confidence: float = 0.7,
) -> Optional[str]:
    """Read text from a cropped HxWx3 ndarray using PaddleOCR.

    Returns the highest-confidence string found, or None on failure.
    """
    paddle = _get_paddle()
    if paddle is None:
        return None
    try:
        result = paddle.ocr(region, cls=False)
    except Exception:
        return None
    if not result or not result[0]:
        return None
    best = max(result[0], key=lambda item: item[1][1], default=None)
    if best is None:
        return None
    text, conf = best[1]
    if conf < min_confidence:
        return None
    stripped = text.strip()
    return stripped if (stripped or allow_empty) else None


def read_int_paddle(region: np.ndarray, **kwargs) -> Optional[int]:
    """PaddleOCR integer reader. Returns None if Paddle can't parse a number."""
    text = read_text_paddle(region, **kwargs)
    if text is None:
        return None
    cleaned = "".join(c for c in text if c.isdigit() or c == "-")
    try:
        return int(cleaned)
    except ValueError:
        return None


def read_int_tesseract(region: np.ndarray) -> Optional[int]:
    """Read an integer from a cropped ndarray via pytesseract (fallback path).

    Kept as an explicit function so the hybrid wrapper can call it directly
    and so callers can opt into the tesseract path when Paddle is overkill.
    """
    try:
        import pytesseract  # type: ignore[import]
        img = Image.fromarray(region)
        raw = pytesseract.image_to_string(
            img, config="--psm 7 -c tessedit_char_whitelist=0123456789-"
        )
        cleaned = "".join(c for c in raw if c.isdigit() or c == "-")
        return int(cleaned)
    except Exception:
        return None


def read_int_hybrid(region: np.ndarray, *, field_name: str = "") -> Optional[int]:
    """Primary: PaddleOCR. Fallback: pytesseract. Last resort: None.

    field_name is used only for debug logging to identify which field failed.
    """
    result = read_int_paddle(region)
    if result is not None:
        return result
    logging.debug("paddle OCR returned None for %s, falling back to tesseract", field_name)
    return read_int_tesseract(region)
