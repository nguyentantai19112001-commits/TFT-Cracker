"""Lazy loader for engine/knowledge/constants.yaml — augie v3 agent constants.

Usage:
    from engine.knowledge.loader import constants
    k = constants()
    k["interest_tiers"]  # list of tier dicts
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_CONSTANTS_PATH = Path(__file__).parent / "constants.yaml"
_cache: dict[str, Any] | None = None

_REQUIRED_KEYS = {
    "player_damage",
    "xp_to_next_level",
    "interest_tiers",
    "streak_bonus",
    "pool_size_per_champion",
    "shop_odds",
    "augment_distribution",
    "econ_curve",
    "hp_tiers",
    "level_targets",
    "components",
    "posture_weights",
    "frame_templates",
    "value_class_weights",
    "cost_weights",
}


def constants(path: Path | None = None) -> dict[str, Any]:
    """Return parsed constants dict. Cached after first call (unless path overridden)."""
    global _cache
    if _cache is not None and path is None:
        return _cache

    target = path or _CONSTANTS_PATH
    with target.open("r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    missing = _REQUIRED_KEYS - set(raw)
    if missing:
        raise ValueError(f"constants.yaml is missing required keys: {sorted(missing)}")

    if path is None:
        _cache = raw
    return raw


def reset_cache() -> None:
    """Clear cached constants — for testing only."""
    global _cache
    _cache = None


def interest_for_gold(gold: int, k: dict[str, Any] | None = None) -> int:
    """Return interest earned at start of round for a given gold amount."""
    k = k or constants()
    for tier in k["interest_tiers"]:
        if tier["min"] <= gold <= tier["max"]:
            return tier["interest"]
    return 0


def streak_bonus_for(streak: int, k: dict[str, Any] | None = None) -> int:
    """Return bonus gold for a given streak magnitude (win or loss, same table)."""
    k = k or constants()
    n = abs(streak)
    table: dict[int, int] = {int(s): int(v) for s, v in k["streak_bonus"].items()}
    # table caps at 6 with +3; clamp down
    effective = min(n, max(table))
    return table.get(effective, 0)


def shop_odds_for_level(level: int, k: dict[str, Any] | None = None) -> list[float]:
    """Return [p_1cost, p_2cost, p_3cost, p_4cost, p_5cost] as fractions summing to 1."""
    k = k or constants()
    clamped = max(1, min(11, level))
    percents: list[int] = k["shop_odds"][clamped]
    return [round(p / 100.0, 6) for p in percents]


def xp_to_next(level: int, k: dict[str, Any] | None = None) -> int:
    """XP required from `level` to level+1. Returns 0 if level >= 9."""
    k = k or constants()
    table: dict[int, int] = {int(lvl): int(v) for lvl, v in k["xp_to_next_level"].items()}
    return table.get(level, 0)
