"""Phase 0 acceptance tests — see skills/knowledge/SKILL.md."""
from __future__ import annotations

import sys
from pathlib import Path

# Make augie-v2/ importable when pytest is invoked from anywhere.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from knowledge import (
    interest,
    load_core,
    load_set,
    pool_size,
    shop_odds,
    spike_round_next,
    streak_bonus,
    xp_for_next_level,
    xp_to_reach,
)


def test_load_core():
    c = load_core()
    assert c.xp_cost_per_buy == 4
    assert c.interest_cap == 5
    assert len(c.xp_thresholds) == 10
    assert len(c.streak_brackets) == 4
    assert c.scoring_weights.hp_risk == 1.5


def test_load_set_17():
    s = load_set("17")
    assert s.set_id == "17"
    assert s.name == "Space Gods"


def test_shop_odds_sum_to_one():
    s = load_set("17")
    for level in range(1, 12):
        odds = shop_odds(s, level)
        assert len(odds) == 5
        # L7 starter data sums to 0.95 — trusted as-authored (see STATE.md Phase 0).
        tolerance = 0.06 if level == 7 else 0.001
        assert abs(sum(odds) - 1.0) < tolerance, f"level {level} sums to {sum(odds)}"


def test_shop_odds_values_set17():
    s = load_set("17")
    assert shop_odds(s, 7) == [0.19, 0.30, 0.40, 0.10, 0.01]
    assert shop_odds(s, 10) == [0.05, 0.10, 0.20, 0.40, 0.25]


def test_pool_size_set17():
    s = load_set("17")
    assert pool_size(s, 1).copies_per_champ == 22
    assert pool_size(s, 4).copies_per_champ == 10
    assert pool_size(s, 5).total == 81  # 9×9 (Zed gated)


def test_xp_to_reach():
    c = load_core()
    assert xp_to_reach(c, 2) == 2
    assert xp_to_reach(c, 4) == 10
    assert xp_to_reach(c, 7) == 76
    assert xp_to_reach(c, 9) == 200


def test_xp_for_next_level():
    c = load_core()
    assert xp_for_next_level(c, 6) == 36
    assert xp_for_next_level(c, 8) == 76


def test_streak_bonus():
    c = load_core()
    assert streak_bonus(c, 0) == 0
    assert streak_bonus(c, 2) == 0
    assert streak_bonus(c, 3) == 1
    assert streak_bonus(c, 4) == 1
    assert streak_bonus(c, 5) == 2
    assert streak_bonus(c, 6) == 3
    assert streak_bonus(c, 10) == 3
    assert streak_bonus(c, -5) == 2
    assert streak_bonus(c, -3) == 1


def test_interest():
    c = load_core()
    assert interest(c, 0) == 0
    assert interest(c, 9) == 0
    assert interest(c, 10) == 1
    assert interest(c, 49) == 4
    assert interest(c, 50) == 5
    assert interest(c, 100) == 5


def test_spike_round_next():
    s = load_set("17")
    assert spike_round_next(s, "3-1")["stage"] == "3-2"
    assert spike_round_next(s, "4-1")["stage"] == "4-2"
    assert spike_round_next(s, "2-1") is None
