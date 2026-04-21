"""Phase 2 acceptance tests — pool tracker. See skills/pool/SKILL.md.
Opponent scouting removed in Phase 3.5a — tests cover own-holdings only.
"""
from __future__ import annotations
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if sys.path[0] != str(_ROOT):
    sys.path.insert(0, str(_ROOT))

import pytest
from pool import PoolTracker
from schemas import BoardUnit
from knowledge import load_set

SET17 = load_set("17")

# Jinx is a 2-cost in Set 17: copies_per_champ=20, distinct=13, total=260
_JINX_COPIES = 20
_JINX_DISTINCT = 13
_JINX_TOTAL = 260


def test_fresh_tracker_full_pool():
    t = PoolTracker(SET17)
    b = t.belief_for("Jinx")
    assert b.k_estimate == _JINX_COPIES


def test_own_board_decrements():
    t = PoolTracker(SET17)
    t.observe_own_board(board=[BoardUnit(champion="Jinx", star=2)], bench=[])
    assert t.belief_for("Jinx").k_estimate == _JINX_COPIES - 3  # star-2 = 3 copies


def test_sell_increments_back():
    t = PoolTracker(SET17)
    t.observe_own_board([BoardUnit(champion="Jinx", star=2)], [])
    assert t.belief_for("Jinx").k_estimate == _JINX_COPIES - 3
    t.observe_own_board([], [])  # sold
    assert t.belief_for("Jinx").k_estimate == _JINX_COPIES


def test_r_t_estimate_drops():
    t = PoolTracker(SET17)
    r_t_fresh = t.belief_for("Jinx").r_t_estimate  # full 2-cost pool = 260
    t.observe_own_board([BoardUnit(champion="Jinx", star=2)], [])  # -3
    assert t.belief_for("Jinx").r_t_estimate == r_t_fresh - 3


def test_to_pool_state_round_trip():
    t = PoolTracker(SET17)
    t.observe_own_board([BoardUnit(champion="Jinx", star=1)], [])
    p = t.to_pool_state("Jinx")
    assert p.copies_of_target_remaining == _JINX_COPIES - 1
    assert p.distinct_same_cost == _JINX_DISTINCT


def test_reset():
    t = PoolTracker(SET17)
    t.observe_own_board([BoardUnit(champion="Jinx", star=2)], [])
    t.reset()
    assert t.belief_for("Jinx").k_estimate == _JINX_COPIES
