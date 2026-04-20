"""Game-state helpers: LCU API reads, fuzzy-match OCR cleanup, shop reader.

Patterns adapted from jfd02/TFT-OCR-BOT (GPLv3), reimplemented for this project.
See THIRD_PARTY_NOTICES.md.
"""

from __future__ import annotations

import threading
import warnings
from difflib import SequenceMatcher
from typing import Optional

import requests
from PIL import ImageGrab

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
