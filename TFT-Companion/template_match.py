"""Template matching: given a screen region, find the best-matching asset
(champion portrait, item icon, augment icon) from Community Dragon.

Strategy:
    1. On import, load all assets into memory as normalized grayscale ndarrays
       at a fixed size (64×64 for champions, 32×32 for items/augments).
    2. For a query region, resize to the same fixed size, grayscale, normalize,
       then score every candidate with normalized correlation coefficient
       (cv2.TM_CCOEFF_NORMED).
    3. Return (winner_name, winner_score, runner_up_name, runner_up_score).

Scoring thresholds:
    - confidence_floor: below this we reject the match (return None)
    - ambiguity_margin: if winner - runner_up < this, flag as ambiguous

Tuning these is a calibration task — the logger captures everything so we
can replay old screenshots against new thresholds.
"""

from __future__ import annotations

import io
import json
import time
from functools import lru_cache
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image

import db

ROOT = Path(__file__).parent
ASSETS = ROOT / "assets"
MANIFEST = ASSETS / "manifest.json"

CHAMP_SIZE = 64
ITEM_SIZE = 32
AUG_SIZE = 48

CONFIDENCE_FLOOR = 0.55
AMBIGUITY_MARGIN = 0.05


def _load_gray(path: Path, size: int) -> Optional[np.ndarray]:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        return None
    img = cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)


@lru_cache(maxsize=1)
def _bank() -> dict:
    if not MANIFEST.exists():
        raise FileNotFoundError(
            f"{MANIFEST} missing — run `py assets/fetch_images.py` first"
        )
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    out: dict[str, dict[str, np.ndarray]] = {
        "champion": {}, "item": {}, "augment": {}, "trait": {},
    }
    sizes = {"champion": CHAMP_SIZE, "trait": CHAMP_SIZE,
             "item": ITEM_SIZE, "augment": AUG_SIZE}
    for cat, bucket_key in [("champion", "champions"), ("item", "items"),
                            ("augment", "augments"), ("trait", "traits")]:
        for name, meta in m.get(bucket_key, {}).items():
            rel = meta["file"]
            if rel.startswith("TFT-Companion/"):
                rel = rel[len("TFT-Companion/"):]
            full = ROOT / rel
            arr = _load_gray(full, sizes[cat])
            if arr is not None:
                out[cat][name] = arr
    return out


def _region_to_gray(region: np.ndarray | Image.Image, size: int) -> np.ndarray:
    if isinstance(region, Image.Image):
        arr = np.array(region.convert("RGB"))
        arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    else:
        arr = region
    arr = cv2.resize(arr, (size, size), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    return cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)


def match(region: np.ndarray | Image.Image, category: str) -> tuple[Optional[str], float, Optional[str], float]:
    """Return (winner_name, winner_score, runner_up_name, runner_up_score).

    Winner is None if best score < CONFIDENCE_FLOOR.
    """
    bank = _bank().get(category, {})
    if not bank:
        return None, 0.0, None, 0.0
    size = {"champion": CHAMP_SIZE, "trait": CHAMP_SIZE,
            "item": ITEM_SIZE, "augment": AUG_SIZE}[category]
    query = _region_to_gray(region, size)

    scored: list[tuple[str, float]] = []
    for name, ref in bank.items():
        res = cv2.matchTemplate(query, ref, cv2.TM_CCOEFF_NORMED)
        scored.append((name, float(res[0, 0])))
    scored.sort(key=lambda t: t[1], reverse=True)

    winner_name, winner_score = scored[0]
    runner_up_name, runner_up_score = (scored[1] if len(scored) > 1 else (None, 0.0))
    if winner_score < CONFIDENCE_FLOOR:
        return None, winner_score, runner_up_name, runner_up_score
    return winner_name, winner_score, runner_up_name, runner_up_score


def match_and_log(capture_id: int, region: Image.Image, category: str,
                  region_xywh: tuple[int, int, int, int],
                  dump_crop: bool = False) -> tuple[Optional[str], float]:
    """Run match() and log the attempt to the DB. Returns (winner, score)."""
    with db.Timer() as t:
        winner, wscore, runner, rscore = match(region, category)
    is_rejected = winner is None
    is_ambiguous = (not is_rejected) and (runner is not None) \
                   and (wscore - rscore) < AMBIGUITY_MARGIN

    crop_bytes = None
    if dump_crop or is_ambiguous or is_rejected:
        buf = io.BytesIO()
        region.save(buf, format="PNG")
        crop_bytes = buf.getvalue()

    db.log_template_match(
        capture_id=capture_id, category=category, region=region_xywh,
        winner=winner, winner_score=wscore,
        runner_up=runner, runner_up_score=rscore,
        is_ambiguous=is_ambiguous, is_rejected=is_rejected,
        elapsed_ms=t.ms, crop_png=crop_bytes,
    )
    return winner, wscore


def bank_stats() -> dict:
    b = _bank()
    return {cat: len(bank) for cat, bank in b.items()}
