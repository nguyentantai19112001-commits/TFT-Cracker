"""Round indicator OCR reader. Tries multiple candidate crop positions and
returns the first one that parses to a known-valid round format.

Pattern adapted from jfd02/TFT-OCR-BOT (GPLv3). See THIRD_PARTY_NOTICES.md.
"""

from __future__ import annotations

import re
from typing import Optional

from PIL import ImageGrab

import ocr
import screen_coords

ROUND_PATTERN = re.compile(r"^[1-7]-[1-7]$")


def _try_crop(screen, crop_coords) -> Optional[str]:
    cropped = screen.crop(crop_coords)
    raw = ocr.get_text_from_image(cropped, whitelist=ocr.ROUND_WHITELIST)
    return raw if ROUND_PATTERN.match(raw) else None


def get_round() -> Optional[str]:
    """Read current round like '3-2'. None if unreadable."""
    screen = ImageGrab.grab(bbox=screen_coords.ROUND_POS.get_coords())
    for pos in (screen_coords.ROUND_POS_THREE,
                screen_coords.ROUND_POS_TWO,
                screen_coords.ROUND_POS_ONE):
        result = _try_crop(screen, pos.get_coords())
        if result:
            return result
    return None
