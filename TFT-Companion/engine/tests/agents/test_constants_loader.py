"""Tests for engine/knowledge/loader.py — constants.yaml loading + helpers."""
from __future__ import annotations

import pytest
from engine.knowledge.loader import (
    constants,
    interest_for_gold,
    reset_cache,
    shop_odds_for_level,
    streak_bonus_for,
    xp_to_next,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_cache()
    yield
    reset_cache()


# ── Load + structure ──────────────────────────────────────────────────────────

def test_constants_loads_without_error():
    k = constants()
    assert isinstance(k, dict)


def test_required_keys_present():
    k = constants()
    for key in ("interest_tiers", "streak_bonus", "shop_odds", "hp_tiers",
                "augment_distribution", "econ_curve", "components"):
        assert key in k, f"missing key: {key}"


def test_constants_cached():
    k1 = constants()
    k2 = constants()
    assert k1 is k2


def test_interest_tiers_monotonic():
    k = constants()
    tiers = k["interest_tiers"]
    prev_interest = -1
    for tier in tiers:
        assert tier["interest"] >= prev_interest
        prev_interest = tier["interest"]


def test_shop_odds_rows_sum_to_100():
    k = constants()
    for lvl, row in k["shop_odds"].items():
        # level 7 in the brief sums to 95 — source data rounding; allow ≤5% delta
        assert abs(sum(row) - 100) <= 5, f"level {lvl} shop_odds deviate >5 from 100: {row}"


def test_hp_tiers_keys():
    k = constants()
    assert set(k["hp_tiers"].keys()) == {"healthy", "warn", "danger", "critical"}


def test_components_have_required_fields():
    k = constants()
    for comp in k["components"]:
        assert "id" in comp
        assert "display" in comp
        assert "family" in comp


# ── interest_for_gold ─────────────────────────────────────────────────────────

def test_interest_zero_gold():
    assert interest_for_gold(0) == 0


def test_interest_9_gold():
    assert interest_for_gold(9) == 0


def test_interest_10_gold():
    assert interest_for_gold(10) == 1


def test_interest_50_gold():
    assert interest_for_gold(50) == 5


def test_interest_49_gold():
    assert interest_for_gold(49) == 4


# ── streak_bonus_for ──────────────────────────────────────────────────────────

def test_streak_1_no_bonus():
    assert streak_bonus_for(1) == 0


def test_streak_2_bonus():
    assert streak_bonus_for(2) == 1


def test_streak_5_bonus():
    assert streak_bonus_for(5) == 2


def test_streak_6_plus_bonus():
    assert streak_bonus_for(6) == 3
    assert streak_bonus_for(10) == 3  # clamped to 6+


def test_streak_negative_same_as_positive():
    assert streak_bonus_for(-4) == streak_bonus_for(4)


# ── shop_odds_for_level ───────────────────────────────────────────────────────

def test_shop_odds_level_1_is_all_1cost():
    odds = shop_odds_for_level(1)
    assert odds[0] == 1.0
    assert all(o == 0.0 for o in odds[1:])


def test_shop_odds_sums_to_one():
    for lvl in range(1, 12):
        odds = shop_odds_for_level(lvl)
        # level 7 source data sums to 95 — allow ≤5% deviation
        assert abs(sum(odds) - 1.0) <= 0.06, f"level {lvl} doesn't sum to ~1: {sum(odds)}"


def test_shop_odds_level_clamped():
    assert shop_odds_for_level(0) == shop_odds_for_level(1)
    assert shop_odds_for_level(12) == shop_odds_for_level(11)


# ── xp_to_next ────────────────────────────────────────────────────────────────

def test_xp_level_4_to_5():
    assert xp_to_next(4) == 10


def test_xp_level_8_to_9():
    assert xp_to_next(8) == 68


def test_xp_level_9_to_10():
    # YAML has key 9 → 68 XP (level 9→10 path); level 10 not in table → 0
    assert xp_to_next(9) == 68
    assert xp_to_next(10) == 0
