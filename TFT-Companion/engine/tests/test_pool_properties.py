"""Property-based tests for PoolTracker invariants (Task 9 — Hypothesis).

IMPORTANT: If any property fails, do NOT auto-fix. Report the minimal
counterexample Hypothesis produces — it's likely a real bug.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if sys.path[0] != str(_ROOT):
    sys.path.insert(0, str(_ROOT))

from hypothesis import given, settings
from hypothesis import strategies as st

from knowledge import load_set
from pool import PoolTracker
from schemas import BoardUnit

SET17 = load_set("17")

# Jinx is a 2-cost in Set 17: copies_per_champ=20
_JINX_MAX_COPIES = 20


@given(star=st.sampled_from([1, 2, 3]))
@settings(max_examples=20)
def test_belief_bounds_always_valid(star):
    """After any observation, k_estimate stays in [0, copies_per_champ]."""
    t = PoolTracker(SET17)
    t.observe_own_board([BoardUnit(champion="Jinx", star=star)], [])
    belief = t.belief_for("Jinx")
    assert 0 <= belief.k_estimate <= _JINX_MAX_COPIES, (
        f"k_estimate={belief.k_estimate} out of [0, {_JINX_MAX_COPIES}]"
    )


@given(buys=st.integers(min_value=0, max_value=10))
@settings(max_examples=20)
def test_repeated_same_observation_idempotent(buys):
    """Observing the same board state twice must not double-count.

    observe_own_board() computes deltas from the previous snapshot, so
    calling it with the same board twice is a no-op on the second call.
    """
    t = PoolTracker(SET17)
    board = [BoardUnit(champion="Jinx", star=1) for _ in range(buys)]
    t.observe_own_board(board, [])
    first = t.belief_for("Jinx").k_estimate
    t.observe_own_board(board, [])  # identical board — delta should be zero
    second = t.belief_for("Jinx").k_estimate
    assert first == second, (
        f"k_estimate changed from {first} to {second} on repeated observation"
    )


def test_reset_returns_to_initial():
    """reset() must restore all beliefs to the full-pool value."""
    t = PoolTracker(SET17)
    t.observe_own_board([BoardUnit(champion="Jinx", star=2)], [])
    assert t.belief_for("Jinx").k_estimate < _JINX_MAX_COPIES  # sanity
    t.reset()
    belief = t.belief_for("Jinx")
    assert belief.k_estimate == _JINX_MAX_COPIES, (
        f"k_estimate after reset: {belief.k_estimate}, expected {_JINX_MAX_COPIES}"
    )
