"""Board strength scoring.

Produces a 0–100 score + breakdown so Claude can reason about
"strong for this stage" vs "weak for this stage" without re-deriving it.

Formula (v1, deterministic, tune later):
    unit_value   = cost * (star ** 1.5)          # 2-star doubles, 3-star ~2.8x
    items_bonus  = total_items_on_board * 1.5    # each item = ~1.5 "cost points"
    trait_mult   = 1 + 0.08 * (# activated traits with count >= 2)
    raw          = (sum(unit_value) + items_bonus) * trait_mult
    score        = 100 * raw / expected_raw[stage]   # clipped to [0, 100]

Expected raw-by-stage curve derived from typical Challenger pace:
    2-x : 15    3-x : 35    4-x : 65    5-x : 100    6+ : 150

When champion IDs are "Unknown" (Vision failed to name them), fall back
to an assumed 2-cost unit. Score is lossy but better than nothing, and
the function returns the uncertainty so the advisor can say "board score
~50, but X units are unidentified — estimate confidence LOW."
"""

from __future__ import annotations

import re
from typing import Optional

import game_assets


EXPECTED_RAW = {1: 5, 2: 15, 3: 35, 4: 65, 5: 100, 6: 150, 7: 180}
UNKNOWN_UNIT_ASSUMED_COST = 2


def _parse_stage_num(stage: Optional[str]) -> int:
    if not stage:
        return 0
    m = re.match(r"^(\d)-\d$", stage.strip())
    return int(m.group(1)) if m else 0


def _unit_cost(name: str) -> Optional[int]:
    if not name or name == "Unknown":
        return None
    champ = game_assets.CHAMPIONS.get(name)
    return (champ or {}).get("cost")


def compute_board_strength(state: dict) -> dict:
    """Returns {score, raw, expected, trait_mult, unknown_count, confidence, breakdown}."""
    board = state.get("board") or []
    stage_num = _parse_stage_num(state.get("stage"))
    expected = EXPECTED_RAW.get(stage_num, 15)

    unit_value_sum = 0.0
    item_count = 0
    unknown_count = 0
    breakdown = []

    for unit in board:
        name = unit.get("champion", "Unknown")
        star = max(1, int(unit.get("star") or 1))
        items = unit.get("items") or []
        item_count += len(items)

        cost = _unit_cost(name)
        if cost is None:
            cost = UNKNOWN_UNIT_ASSUMED_COST
            unknown_count += 1

        value = cost * (star ** 1.5)
        unit_value_sum += value
        breakdown.append({
            "champion": name, "star": star, "items": len(items),
            "cost": cost, "value": round(value, 2),
        })

    items_bonus = item_count * 1.5

    traits = state.get("active_traits") or []
    active_real = sum(1 for t in traits if (t.get("count") or 0) >= 2)
    trait_mult = 1 + 0.08 * active_real

    raw = (unit_value_sum + items_bonus) * trait_mult
    score = max(0.0, min(100.0, 100.0 * raw / expected if expected else 0))

    total_units = len(board)
    confidence = "LOW" if (total_units and unknown_count / total_units > 0.5) \
                 else "MEDIUM" if unknown_count else "HIGH"

    return {
        "score": round(score, 1),
        "raw": round(raw, 2),
        "expected_raw": expected,
        "stage_num": stage_num,
        "unit_value_sum": round(unit_value_sum, 2),
        "item_count": item_count,
        "items_bonus": round(items_bonus, 2),
        "active_traits": active_real,
        "trait_mult": round(trait_mult, 3),
        "unknown_units": unknown_count,
        "total_units": total_units,
        "confidence": confidence,
        "breakdown": breakdown,
    }
