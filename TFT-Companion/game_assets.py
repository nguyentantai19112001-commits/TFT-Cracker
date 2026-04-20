"""Current-set champion, item, and trait data.

Populated at runtime from data/set_data.json (fetched via
data/fetch_community_dragon.py). Do NOT hardcode champion lists here —
TFT rotates sets every ~3 months and stale data breaks fuzzy matching.
"""

from __future__ import annotations

import json
from pathlib import Path

_DATA_PATH = Path(__file__).parent / "data" / "set_data.json"


def _load() -> dict:
    if not _DATA_PATH.exists():
        return {"champions": {}, "items": {}, "traits": {}, "set": None, "patch": None}
    with _DATA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


_DATA: dict = _load()

CHAMPIONS: dict[str, dict] = _DATA.get("champions", {})
ITEMS: dict[str, dict] = _DATA.get("items", {})
TRAITS: dict[str, dict] = _DATA.get("traits", {})
SET_ID: str | None = _DATA.get("set")
PATCH: str | None = _DATA.get("patch")

CHAMPION_NAMES: set[str] = set(CHAMPIONS.keys())
ITEM_NAMES: set[str] = set(ITEMS.keys())
TRAIT_NAMES: set[str] = set(TRAITS.keys())


def reload() -> None:
    """Re-read set_data.json (useful after running fetch_community_dragon.py)."""
    global _DATA, CHAMPIONS, ITEMS, TRAITS, SET_ID, PATCH
    global CHAMPION_NAMES, ITEM_NAMES, TRAIT_NAMES
    _DATA = _load()
    CHAMPIONS = _DATA.get("champions", {})
    ITEMS = _DATA.get("items", {})
    TRAITS = _DATA.get("traits", {})
    SET_ID = _DATA.get("set")
    PATCH = _DATA.get("patch")
    CHAMPION_NAMES = set(CHAMPIONS.keys())
    ITEM_NAMES = set(ITEMS.keys())
    TRAIT_NAMES = set(TRAITS.keys())
