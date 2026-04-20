"""OCR pipeline: screen region → preprocessed image → Tesseract → string.

Pipeline adapted from jfd02/TFT-OCR-BOT (GPLv3). Rewritten to use pytesseract
instead of tesserocr to simplify Windows setup. See THIRD_PARTY_NOTICES.md.
"""

from __future__ import annotations

import os
from typing import Optional

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageGrab

_TESSERACT_CMD = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
if os.path.exists(_TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = _TESSERACT_CMD

ALPHABET_WHITELIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
ROUND_WHITELIST = "0123456789-"
DIGIT_WHITELIST = "0123456789"


def _preprocess(image: Image.Image, scale: int = 3) -> np.ndarray:
    resized = image.resize((image.width * scale, image.height * scale))
    arr = np.array(resized)[..., :3]
    gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    _, thresholded = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return thresholded


def _tesseract(img: np.ndarray, psm: int, whitelist: str) -> str:
    cfg = f"--psm {psm}"
    if whitelist:
        cfg += f" -c tessedit_char_whitelist={whitelist}"
    return pytesseract.image_to_string(img, config=cfg).strip()


def get_text(bbox: tuple[int, int, int, int], scale: int = 3, psm: int = 7,
             whitelist: str = "") -> str:
    """Screenshot a region and OCR it."""
    screenshot = ImageGrab.grab(bbox=bbox)
    return _tesseract(_preprocess(screenshot, scale), psm, whitelist)


def get_text_from_image(image: Image.Image, whitelist: str = "", psm: int = 7,
                        scale: int = 3) -> str:
    """OCR an already-captured PIL image."""
    return _tesseract(_preprocess(image, scale), psm, whitelist)


def check_tesseract() -> Optional[str]:
    """Returns None if Tesseract is reachable, else an error message."""
    try:
        version = pytesseract.get_tesseract_version()
        return None if version else "pytesseract returned no version"
    except Exception as e:
        return f"{type(e).__name__}: {e}"
