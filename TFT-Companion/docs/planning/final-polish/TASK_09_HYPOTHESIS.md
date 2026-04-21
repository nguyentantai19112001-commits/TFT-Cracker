# TASK_09_HYPOTHESIS.md — Property-based tests for econ invariants

> Add Hypothesis for property-based testing of econ and pool math. Catches
> edge cases that unit tests miss. Auto-shrinks to minimal reproducers on
> failure.

---

## Prereq checks

```bash
pytest -q                          # current count green
python -c "import hypothesis" 2>/dev/null || echo "need to install"
```

## Files you may edit

- `tests/test_econ_properties.py` (new)
- `tests/test_pool_properties.py` (new)
- `requirements-dev.txt` or test-deps section (add `hypothesis`)
- `STATE.md`

**Do NOT edit** `econ.py` or `pool.py` — this task only adds tests. If
Hypothesis finds a real bug, stop and report via DATA_GAPS.md. Do NOT
fix bugs as part of this task.

## Dependencies

```bash
pip install hypothesis
```

## The tests

### Econ properties

```python
# tests/test_econ_properties.py
"""Property-based tests for econ math invariants.

These complement the fixed-value tests in test_econ.py by exercising the
math across the full input space to catch edge cases. If Hypothesis finds
a failing example, it auto-shrinks to the minimal input that fails.

IMPORTANT: If a property test fails, that's a signal — not noise. Do NOT
tighten the property to make it pass. Report the failure to the user;
it's likely a real bug or an incorrect assumption in the property.
"""
from __future__ import annotations

import pytest
from hypothesis import given, assume, strategies as st
from hypothesis import settings, HealthCheck

from econ import analyze_roll, interest_projection
from schemas import PoolState
from knowledge import load_set, load_core

SET17 = load_set("17")
CORE = load_core()


# --- Strategy helpers ---

levels = st.integers(min_value=1, max_value=11)
golds = st.integers(min_value=0, max_value=300)
streaks = st.integers(min_value=-10, max_value=10)


def pool_states():
    """Generate valid PoolState objects."""
    return st.builds(
        PoolState,
        copies_of_target_remaining=st.integers(min_value=0, max_value=30),
        same_cost_copies_remaining=st.integers(min_value=1, max_value=300),
        distinct_same_cost=st.integers(min_value=1, max_value=15),
    ).filter(
        lambda p: p.copies_of_target_remaining <= p.same_cost_copies_remaining
    )


# --- Probability bounds ---

@given(level=levels, gold=golds, pool=pool_states())
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_probabilities_in_unit_interval(level, gold, pool):
    """All P(hit) outputs must be in [0, 1]."""
    r = analyze_roll("X", level=level, gold=gold, pool=pool, set_=SET17)
    assert 0.0 <= r.p_hit_at_least_1 <= 1.0
    assert 0.0 <= r.p_hit_at_least_2 <= 1.0
    assert 0.0 <= r.p_hit_at_least_3 <= 1.0


@given(level=levels, gold=golds, pool=pool_states())
@settings(max_examples=100)
def test_hit_cdf_ordering(level, gold, pool):
    """P(≥1) >= P(≥2) >= P(≥3). Always."""
    r = analyze_roll("X", level=level, gold=gold, pool=pool, set_=SET17)
    assert r.p_hit_at_least_1 >= r.p_hit_at_least_2 >= r.p_hit_at_least_3


# --- Monotonicity: more gold never decreases P(hit) ---

@given(level=levels, pool=pool_states(),
       gold_a=golds, gold_b=golds)
@settings(max_examples=100)
def test_more_gold_monotone_nondecreasing(level, pool, gold_a, gold_b):
    """P(hit | N gold) <= P(hit | M gold) whenever N <= M."""
    assume(gold_a <= gold_b)
    r_a = analyze_roll("X", level, gold_a, pool, SET17)
    r_b = analyze_roll("X", level, gold_b, pool, SET17)
    # Allow 1e-9 float slop
    assert r_a.p_hit_at_least_1 <= r_b.p_hit_at_least_1 + 1e-9
    assert r_a.p_hit_at_least_2 <= r_b.p_hit_at_least_2 + 1e-9


# --- Zero copies means zero probability ---

@given(level=levels, gold=golds, R_T=st.integers(min_value=1, max_value=300),
       D=st.integers(min_value=1, max_value=15))
@settings(max_examples=50)
def test_zero_target_copies_zero_probability(level, gold, R_T, D):
    """If target pool is empty, P(hit) == 0 regardless of gold."""
    pool = PoolState(copies_of_target_remaining=0,
                     same_cost_copies_remaining=R_T,
                     distinct_same_cost=D)
    r = analyze_roll("X", level, gold, pool, SET17)
    assert r.p_hit_at_least_1 == 0.0
    assert r.p_hit_at_least_2 == 0.0
    assert r.p_hit_at_least_3 == 0.0


# --- Expected copies non-negative ---

@given(level=levels, gold=golds, pool=pool_states())
@settings(max_examples=100)
def test_expected_copies_non_negative(level, gold, pool):
    r = analyze_roll("X", level, gold, pool, SET17)
    assert r.expected_copies_seen >= 0.0


# --- Variance non-negative ---

@given(level=levels, gold=golds, pool=pool_states())
@settings(max_examples=100)
def test_variance_non_negative(level, gold, pool):
    r = analyze_roll("X", level, gold, pool, SET17)
    assert r.variance_copies >= 0.0


# --- Zero gold = zero probability ---

@given(level=levels, pool=pool_states())
def test_zero_gold_zero_hit(level, pool):
    r = analyze_roll("X", level, 0, pool, SET17)
    assert r.p_hit_at_least_1 == 0.0


# --- Interest projection invariants ---

@given(starting_gold=st.integers(min_value=0, max_value=100),
       rounds=st.integers(min_value=1, max_value=10),
       streak=streaks)
@settings(max_examples=100)
def test_interest_projection_non_decreasing(starting_gold, rounds, streak):
    """With no spending, gold never decreases across rounds."""
    proj = interest_projection(starting_gold, rounds, streak, CORE)
    assert len(proj) == rounds
    # Each round's gold >= previous round (or starting gold on round 0)
    prev = starting_gold
    for gold_at_round in proj:
        assert gold_at_round >= prev
        prev = gold_at_round


@given(starting_gold=st.integers(min_value=60, max_value=200),
       rounds=st.integers(min_value=1, max_value=5))
@settings(max_examples=50)
def test_interest_cap_respected(starting_gold, rounds):
    """At ≥50g, interest is capped — growth per round is bounded."""
    proj = interest_projection(starting_gold, rounds, streak=0, core=CORE)
    # Interest cap is 5g; base income is 5g; so max growth without streak is 10g/round
    max_per_round = 5 + CORE.interest_cap   # base income + max interest
    assert proj[0] <= starting_gold + max_per_round + 1  # +1 slop for edge cases
```

### Pool tracker properties

```python
# tests/test_pool_properties.py
"""Property-based tests for PoolTracker invariants."""
import pytest
from hypothesis import given, assume, strategies as st, settings

from pool import PoolTracker
from schemas import BoardUnit
from knowledge import load_set

SET17 = load_set("17")


@given(star=st.sampled_from([1, 2, 3]))
@settings(max_examples=20)
def test_belief_bounds_always_valid(star):
    """After any observation, k_estimate stays in [0, copies_per_champ]."""
    t = PoolTracker(SET17)
    t.observe_own_board([BoardUnit(champion="Jinx", star=star)], [])
    belief = t.belief_for("Jinx")
    assert 0 <= belief.k_estimate <= 20  # 2-cost copies_per_champ


@given(buys=st.integers(min_value=0, max_value=10))
@settings(max_examples=20)
def test_repeated_same_observation_idempotent(buys):
    """Observing the same board state twice doesn't double-count."""
    t = PoolTracker(SET17)
    board = [BoardUnit(champion="Jinx", star=1) for _ in range(buys)]
    t.observe_own_board(board, [])
    first = t.belief_for("Jinx").k_estimate
    t.observe_own_board(board, [])   # same observation again
    second = t.belief_for("Jinx").k_estimate
    assert first == second


def test_reset_returns_to_initial():
    """reset() brings all beliefs back to full pool."""
    t = PoolTracker(SET17)
    t.observe_own_board([BoardUnit(champion="Jinx", star=2)], [])
    t.reset()
    belief = t.belief_for("Jinx")
    assert belief.k_estimate == 20  # full 2-cost pool
```

## Acceptance gate

1. `pytest -q` shows old test count + ~15 new tests all passing.
2. `hypothesis` is a dev-only dependency (not a runtime dep).
3. If ANY property test fails: STOP, do not auto-fix. Report the failure
   to the user with the minimal counterexample Hypothesis produces.

## Rollback criteria

Same as acceptance failure: if Hypothesis finds a real bug, this task
isn't "done" — the bug finding is the deliverable. Report to user and
wait for guidance on whether to patch econ/pool or adjust the property.

## Commit message

```
Task 9: add Hypothesis property tests for econ and pool math

- test_econ_properties.py: 9 invariants (bounds, monotonicity, CDF ordering, etc.)
- test_pool_properties.py: 3 invariants (bounds, idempotence, reset)
- All properties hold across 100 generated examples each

Tests: +12. Edge cases covered far beyond what hand-written fixtures reach.
```
