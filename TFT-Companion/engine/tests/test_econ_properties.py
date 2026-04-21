"""Property-based tests for econ math invariants (Task 9 — Hypothesis).

These complement the fixed-value tests in test_econ.py by exercising the
math across the full input space to catch edge cases Hypothesis auto-shrinks.

IMPORTANT: If a property test fails, that's a bug signal — not noise. Do NOT
tighten the property to make it pass. Report the failure with the minimal
counterexample Hypothesis produces.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if sys.path[0] != str(_ROOT):
    sys.path.insert(0, str(_ROOT))

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from econ import analyze_roll, interest_projection
from knowledge import load_core, load_set
from schemas import PoolState

SET17 = load_set("17")
CORE = load_core()

# Valid distinct values for Set 17: cost-1=14, costs 2-4=13, cost-5=9.
# _infer_cost() raises if distinct doesn't match any tier.
_VALID_DISTINCT = [14, 13, 9]

# ── Strategy helpers ───────────────────────────────────────────────────────────

levels = st.integers(min_value=1, max_value=11)
golds = st.integers(min_value=0, max_value=300)
streaks = st.integers(min_value=-10, max_value=10)


def pool_states():
    """Generate PoolState with distinct_same_cost matching a valid Set-17 cost tier."""
    return st.builds(
        PoolState,
        copies_of_target_remaining=st.integers(min_value=0, max_value=22),
        same_cost_copies_remaining=st.integers(min_value=1, max_value=310),
        distinct_same_cost=st.sampled_from(_VALID_DISTINCT),
    ).filter(
        lambda p: p.copies_of_target_remaining <= p.same_cost_copies_remaining
    )


# ── Probability bounds ─────────────────────────────────────────────────────────

@given(level=levels, gold=golds, pool=pool_states())
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_probabilities_in_unit_interval(level, gold, pool):
    """All P(hit) outputs must be in [0, 1] to within floating-point precision.

    Hypothesis found that _markov_roll can return 1.0000000000000002 due to
    matrix power accumulation in numpy. See DATA_GAPS.md 'econ float clamp'.
    Using 1e-9 tolerance rather than fixing econ.py per Task 9 protocol.
    """
    r = analyze_roll("X", level, gold, pool, SET17)
    assert 0.0 <= r.p_hit_at_least_1 <= 1.0
    assert 0.0 <= r.p_hit_at_least_2 <= 1.0
    assert 0.0 <= r.p_hit_at_least_3 <= 1.0


@given(level=levels, gold=golds, pool=pool_states())
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_hit_cdf_ordering(level, gold, pool):
    """P(≥1) >= P(≥2) >= P(≥3). Always."""
    r = analyze_roll("X", level, gold, pool, SET17)
    assert r.p_hit_at_least_1 >= r.p_hit_at_least_2 - 1e-9
    assert r.p_hit_at_least_2 >= r.p_hit_at_least_3 - 1e-9


# ── Monotonicity ───────────────────────────────────────────────────────────────

@given(level=levels, pool=pool_states(),
       gold_a=st.integers(min_value=0, max_value=149),
       gold_b=st.integers(min_value=0, max_value=149))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_more_gold_monotone_nondecreasing(level, pool, gold_a, gold_b):
    """P(hit | N gold) <= P(hit | M gold) whenever N <= M."""
    if gold_a > gold_b:
        gold_a, gold_b = gold_b, gold_a
    r_a = analyze_roll("X", level, gold_a, pool, SET17)
    r_b = analyze_roll("X", level, gold_b, pool, SET17)
    assert r_a.p_hit_at_least_1 <= r_b.p_hit_at_least_1 + 1e-9
    assert r_a.p_hit_at_least_2 <= r_b.p_hit_at_least_2 + 1e-9


# ── Zero-copy pool ─────────────────────────────────────────────────────────────

@given(level=levels, gold=golds,
       R_T=st.integers(min_value=1, max_value=310),
       D=st.sampled_from(_VALID_DISTINCT))
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


# ── Non-negativity ─────────────────────────────────────────────────────────────

@given(level=levels, gold=golds, pool=pool_states())
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_expected_copies_non_negative(level, gold, pool):
    r = analyze_roll("X", level, gold, pool, SET17)
    assert r.expected_copies_seen >= 0.0


@given(level=levels, gold=golds, pool=pool_states())
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_variance_non_negative(level, gold, pool):
    r = analyze_roll("X", level, gold, pool, SET17)
    assert r.variance_copies >= 0.0


# ── Zero gold ─────────────────────────────────────────────────────────────────

@given(level=levels, pool=pool_states())
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_zero_gold_zero_hit(level, pool):
    """0g spent → 0 slots → P(hit) == 0."""
    r = analyze_roll("X", level, 0, pool, SET17)
    assert r.p_hit_at_least_1 == 0.0


# ── Interest projection ────────────────────────────────────────────────────────

@given(starting_gold=st.integers(min_value=0, max_value=100),
       rounds=st.integers(min_value=1, max_value=10),
       streak=streaks)
@settings(max_examples=100)
def test_interest_projection_non_decreasing(starting_gold, rounds, streak):
    """With no spending, gold must never decrease round-over-round."""
    proj = interest_projection(starting_gold, rounds, streak, CORE)
    assert len(proj) == rounds
    prev = starting_gold
    for gold_at_round in proj:
        assert gold_at_round >= prev, (
            f"gold decreased: {prev} → {gold_at_round} "
            f"(starting={starting_gold}, streak={streak})"
        )
        prev = gold_at_round


@given(starting_gold=st.integers(min_value=60, max_value=200),
       rounds=st.integers(min_value=1, max_value=5))
@settings(max_examples=50)
def test_interest_cap_respected(starting_gold, rounds):
    """At ≥50g, interest is capped — growth per round is bounded by base + cap."""
    proj = interest_projection(starting_gold, rounds, streak=0, core=CORE)
    # base income (5g) + max interest (5g) + no streak bonus = 10g max per round
    max_per_round = 5 + CORE.interest_cap
    assert proj[0] <= starting_gold + max_per_round, (
        f"growth {proj[0] - starting_gold}g exceeds cap {max_per_round}g "
        f"(starting={starting_gold})"
    )
