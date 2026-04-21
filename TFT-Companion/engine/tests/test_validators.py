"""Tests for validators.py — state validation before scorer.

validators.py lives at the TFT-Companion root (not inside engine/),
so we add the root to sys.path before importing.
"""
from __future__ import annotations

import sys
from pathlib import Path

# engine/ is at parents[1]; TFT-Companion root is at parents[2].
_ENGINE = Path(__file__).resolve().parents[1]
_ROOT   = _ENGINE.parent
if sys.path[0] != str(_ENGINE):
    sys.path.insert(0, str(_ENGINE))
if str(_ROOT) not in sys.path:
    sys.path.insert(1, str(_ROOT))

import pytest
from validators import validate, ValidationResult
from schemas import GameState, BoardUnit, ShopSlot


# ── Helpers ────────────────────────────────────────────────────────────────────

def _valid_state(**overrides) -> GameState:
    base = dict(
        stage="3-2", gold=30, hp=70, level=6,
        xp_current=5, xp_needed=36, streak=0, set_id="17",
    )
    base.update(overrides)
    return GameState(**base)


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_valid_state_passes():
    assert validate(_valid_state()).ok


def test_negative_gold_fails():
    state      = _valid_state()
    state.gold = -5
    result     = validate(state)
    assert not result.ok
    assert any(f.check_name == "gold_bounds" for f in result.failures)


def test_gold_999_passes():
    state      = _valid_state()
    state.gold = 999
    assert validate(state).ok


def test_hp_over_100_fails():
    state    = _valid_state()
    state.hp = 150
    assert not validate(state).ok


def test_hp_slightly_negative_passes():
    """HP between -20 and 0 is tolerated (end-of-game display edge case)."""
    state    = _valid_state()
    state.hp = -5
    assert validate(state).ok


def test_hp_very_negative_fails():
    state    = _valid_state()
    state.hp = -50
    assert not validate(state).ok


def test_level_12_fails():
    state       = _valid_state()
    state.level = 12
    assert not validate(state).ok


def test_level_1_passes():
    state       = _valid_state()
    state.level = 1
    assert validate(state).ok


def test_board_larger_than_level_fails():
    state       = _valid_state(level=3)
    state.board = [BoardUnit(champion="Jinx", star=1) for _ in range(5)]
    result      = validate(state)
    assert not result.ok
    assert any(f.check_name == "board_size" for f in result.failures)


def test_board_equal_to_level_passes():
    state       = _valid_state(level=3)
    state.board = [BoardUnit(champion="Jinx", star=1) for _ in range(3)]
    assert validate(state).ok


def test_xp_current_exceeds_needed_fails():
    state = _valid_state(xp_current=100, xp_needed=36)
    assert not validate(state).ok


def test_xp_both_zero_passes():
    """xp 0/0 is valid (e.g. level 10 max, no XP needed)."""
    state = _valid_state(xp_current=0, xp_needed=0)
    assert validate(state).ok


def test_shop_with_3_slots_fails():
    state      = _valid_state()
    state.shop = [ShopSlot(champion="Jinx", cost=2) for _ in range(3)]
    assert not validate(state).ok


def test_empty_shop_passes():
    """Carousel and god rounds have no shop — that's valid state."""
    state      = _valid_state()
    state.shop = []
    assert validate(state).ok


def test_four_items_on_unit_fails():
    state       = _valid_state()
    state.board = [BoardUnit(
        champion="Jinx", star=2,
        items=["BF Sword", "Recurve Bow", "Tear of the Goddess", "Chain Vest"],
    )]
    assert not validate(state).ok


def test_three_items_on_unit_passes():
    state       = _valid_state()
    state.board = [BoardUnit(
        champion="Jinx", star=2,
        items=["BF Sword", "Recurve Bow", "Tear of the Goddess"],
    )]
    assert validate(state).ok


def test_four_augments_passes():
    """Augment count > 3 is now warn-only (Vision partial parse is legitimate)."""
    state           = _valid_state()
    state.augments  = ["A", "B", "C", "D"]
    assert validate(state).ok


def test_three_augments_passes():
    state           = _valid_state()
    state.augments  = ["A", "B", "C"]
    assert validate(state).ok


def test_malformed_stage_fails():
    state = _valid_state(stage="three-two")
    assert not validate(state).ok


def test_stage_out_of_range_fails():
    state = _valid_state(stage="9-9")
    assert not validate(state).ok


def test_multiple_failures_all_reported():
    """All three violations must appear in the same ValidationResult."""
    state       = _valid_state(gold=-5, hp=150, level=12)
    state.gold  = -5
    state.hp    = 150
    state.level = 12
    result      = validate(state)
    assert not result.ok
    assert len(result.failures) >= 3
