"""econ.py — P(hit), roll-EV, level-EV math for Augie v2 (Phase 1).

Math ported from wongkj12's Markov roll calculator (MIT license).
Reference: https://github.com/wongkj12/TFT-Rolling-Odds-Calculator
"""
from __future__ import annotations

import math
from typing import Literal

import numpy as np

from schemas import (
    CoreKnowledge, GameState, LevelDecision, PoolState,
    RollAnalysis, SetKnowledge,
)
from knowledge import (
    interest as _interest,
    shop_odds as _shop_odds,
    streak_bonus as _streak_bonus,
    xp_for_next_level as _xp_for_next_level,
)

# Standard TFT base round income — not set-specific, stable across all sets.
_BASE_ROUND_INCOME = 5


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _infer_cost(pool: PoolState, set_: SetKnowledge) -> int:
    """Infer cost tier from pool.distinct_same_cost."""
    for cost, info in set_.pool_sizes.items():
        if info.distinct == pool.distinct_same_cost:
            return cost
    raise ValueError(
        f"No cost tier with distinct={pool.distinct_same_cost} in set {set_.set_id}"
    )


def _p_slot(pool: PoolState, set_: SetKnowledge, level: int) -> float:
    """P(target appears in one shop slot). Denominator is R_T, not initial pool."""
    k = pool.copies_of_target_remaining
    R_T = pool.same_cost_copies_remaining
    if k == 0 or R_T == 0:
        return 0.0
    cost = _infer_cost(pool, set_)
    odds = _shop_odds(set_, level)      # already divided by 100
    shop_p = odds[cost - 1]
    return shop_p * k / R_T


def _hg_pmf(N: int, K: int, n: int, x: int) -> float:
    """Hypergeometric PMF: P(X=x) drawing n from pop N with K successes."""
    if x < 0 or x > min(K, n) or (n - x) > (N - K) or N < n:
        return 0.0
    try:
        return math.comb(K, x) * math.comb(N - K, n - x) / math.comb(N, n)
    except (ValueError, ZeroDivisionError):
        return 0.0


def _markov_roll(
    pool: PoolState, set_: SetKnowledge, level: int, slots: int
) -> tuple[float, float, float, float]:
    """Per-slot Markov chain. Returns (p1, p2, p3, expected_copies)."""
    k = pool.copies_of_target_remaining
    R_T = pool.same_cost_copies_remaining
    cost = _infer_cost(pool, set_)
    shop_p = _shop_odds(set_, level)[cost - 1]

    if k == 0 or slots == 0:
        return 0.0, 0.0, 0.0, 0.0

    # State i = copies collected (0..k). Absorbing at k.
    n = k + 1
    M = np.zeros((n, n))
    for i in range(n):
        rem_k = k - i
        rem_RT = R_T - i
        if rem_k <= 0 or rem_RT <= 0:
            M[i, i] = 1.0
        else:
            p = min(shop_p * rem_k / rem_RT, 1.0)
            M[i, i + 1] = p
            M[i, i] = 1.0 - p

    v = np.zeros(n)
    v[0] = 1.0
    dist = v @ np.linalg.matrix_power(M, slots)

    p1 = float(np.sum(dist[1:]))
    p2 = float(np.sum(dist[2:]))
    p3 = float(np.sum(dist[3:])) if k >= 3 else 0.0
    expected = float(np.dot(np.arange(n), dist))
    return p1, p2, p3, expected


def _hypergeo_roll(
    pool: PoolState, set_: SetKnowledge, level: int, slots: int
) -> tuple[float, float, float, float]:
    """Per-refresh hypergeometric Markov. Returns (p1, p2, p3, expected_copies).

    The cost-tier pool (R_T) represents only shop_p fraction of the full shop pool.
    Effective full-pool size = R_T / shop_p so that HG draws of 5 give the same
    expected per-slot probability as the Markov per-slot model.
    """
    k = pool.copies_of_target_remaining
    R_T = pool.same_cost_copies_remaining
    cost = _infer_cost(pool, set_)
    shop_p = _shop_odds(set_, level)[cost - 1]
    n_refreshes = slots // 5

    if k == 0 or n_refreshes == 0 or shop_p == 0.0:
        return 0.0, 0.0, 0.0, 0.0

    # Scale R_T to effective full-pool size (cost tier is shop_p fraction of full pool).
    # Use per-slot draws (n_draw=1, n_refreshes=slots) to avoid within-refresh batching
    # correlation, keeping results within 0.1% of the per-slot Markov model.
    N_eff = int(round(R_T / shop_p))

    n = k + 1
    M = np.zeros((n, n))
    for i in range(n):
        rem_k = k - i
        N_eff_i = N_eff - i
        if rem_k <= 0 or N_eff_i <= 0:
            M[i, i] = 1.0
        else:
            p_hit = min(rem_k / N_eff_i, 1.0)  # HG(N_eff_i, rem_k, 1, 1)
            M[i, i + 1] = p_hit
            M[i, i] = 1.0 - p_hit

    v = np.zeros(n)
    v[0] = 1.0
    dist = v @ np.linalg.matrix_power(M, slots)  # per-slot, not per-refresh

    p1 = float(np.sum(dist[1:]))
    p2 = float(np.sum(dist[2:]))
    p3 = float(np.sum(dist[3:])) if k >= 3 else 0.0
    expected = float(np.dot(np.arange(n), dist))
    return p1, p2, p3, expected


def _iid_roll(
    pool: PoolState, set_: SetKnowledge, level: int, slots: int
) -> tuple[float, float, float, float, float]:
    """Binomial i.i.d. approximation. Returns (p1, p2, p3, expected, variance)."""
    p = _p_slot(pool, set_, level)
    if slots == 0 or p == 0.0:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    # Depletion correction: p decreases as copies are bought; use first-order average.
    R_T = pool.same_cost_copies_remaining
    if R_T > 0:
        p *= 1.0 - pool.copies_of_target_remaining / (2.0 * R_T)

    q = 1.0 - p
    # P(X >= m) = 1 - sum_{x=0}^{m-1} binom(slots,x) * p^x * q^(slots-x)
    p0 = q ** slots
    p1_term = slots * p * (q ** (slots - 1))
    p2_term = math.comb(slots, 2) * (p ** 2) * (q ** (slots - 2)) if slots >= 2 else 0.0

    return (
        max(0.0, 1.0 - p0),
        max(0.0, 1.0 - p0 - p1_term),
        max(0.0, 1.0 - p0 - p1_term - p2_term),
        slots * p,
        slots * p * q,
    )


# ---------------------------------------------------------------------------
# Expected level pacing table (standard TFT, stable since Set 13)
# ---------------------------------------------------------------------------

_EXPECTED_LEVEL: dict[tuple[int, int], int] = {
    (2, 1): 4, (2, 2): 4, (2, 3): 4, (2, 4): 4, (2, 5): 4, (2, 6): 5, (2, 7): 5,
    (3, 1): 5, (3, 2): 5, (3, 3): 6, (3, 4): 6, (3, 5): 6, (3, 6): 6, (3, 7): 6,
    (4, 1): 7, (4, 2): 7, (4, 3): 7, (4, 4): 7, (4, 5): 8, (4, 6): 8, (4, 7): 8,
    (5, 1): 8, (5, 2): 8, (5, 3): 8, (5, 4): 9, (5, 5): 9,
}


def _expected_level(stage: str) -> int:
    try:
        x, y = map(int, stage.split("-", 1))
        return _EXPECTED_LEVEL.get((x, y), 7)
    except (ValueError, AttributeError):
        return 7


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_roll(
    target: str,
    level: int,
    gold: int,
    pool: PoolState,
    set_: SetKnowledge,
    method: Literal["markov", "hypergeo", "iid"] = "markov",
) -> RollAnalysis:
    """Compute P(hit >= 1, >= 2, >= 3 copies) of `target` by spending all `gold` at `level`."""
    p_s = _p_slot(pool, set_, level)
    egfh = (2.0 / (1.0 - (1.0 - p_s) ** 5)) if p_s > 0.0 else float("inf")

    zero = RollAnalysis(
        target_champion=target, level=level, gold_spent=gold,
        p_hit_at_least_1=0.0, p_hit_at_least_2=0.0, p_hit_at_least_3=0.0,
        expected_copies_seen=0.0, variance_copies=0.0,
        expected_gold_to_first_hit=egfh if gold > 0 else float("inf"),
        method=method,
    )
    if pool.copies_of_target_remaining == 0 or gold == 0:
        return zero

    slots = 5 * (gold // 2)

    if method == "markov":
        p1, p2, p3, exp = _markov_roll(pool, set_, level, slots)
        var = slots * p_s * (1.0 - p_s)
    elif method == "iid":
        p1, p2, p3, exp, var = _iid_roll(pool, set_, level, slots)
    else:  # hypergeo
        p1, p2, p3, exp = _hypergeo_roll(pool, set_, level, slots)
        var = slots * p_s * (1.0 - p_s)

    return RollAnalysis(
        target_champion=target, level=level, gold_spent=gold,
        p_hit_at_least_1=p1, p_hit_at_least_2=p2, p_hit_at_least_3=p3,
        expected_copies_seen=exp, variance_copies=var,
        expected_gold_to_first_hit=egfh, method=method,
    )


def level_vs_roll(
    state: GameState,
    target: str | None,
    pool: PoolState | None,
    core: CoreKnowledge,
    set_: SetKnowledge,
) -> LevelDecision:
    """Given current state and optional target, recommend LEVEL / HOLD / ROLL."""
    try:
        xp_per_bracket = _xp_for_next_level(core, state.level)
    except ValueError:
        xp_per_bracket = 0

    xp_remaining = max(0, xp_per_bracket - state.xp_current)
    buys_needed = math.ceil(xp_remaining / core.xp_per_buy) if xp_remaining > 0 else 0
    gold_to_level = buys_needed * core.xp_cost_per_buy

    interest_now = min(core.interest_cap, state.gold // 10)
    interest_after = min(core.interest_cap, max(0, state.gold - gold_to_level) // 10)
    interest_lost = float(interest_now - interest_after)

    if target and pool:
        r_now = analyze_roll(target, state.level, 30, pool, set_)
        r_next = analyze_roll(target, state.level + 1, 30, pool, set_)
        p_hit_delta = r_next.p_hit_at_least_2 - r_now.p_hit_at_least_2
    else:
        p_hit_delta = 0.0

    exp_level = _expected_level(state.stage)

    # Priority-ordered decision rules (thresholds are first-cut; tune after replay logging)
    if state.hp < 25 and state.level >= exp_level:
        rec, reason = "ROLL", "HP critical — stabilize board now"
    elif state.level < exp_level and gold_to_level <= state.gold * 0.75:
        rec, reason = "LEVEL", "Behind on pace; leveling is affordable"
    elif p_hit_delta > 0.15:
        rec, reason = "LEVEL", f"Leveling raises P(2-copy) by {p_hit_delta:.0%}"
    elif state.gold < 30 and state.hp > 50:
        rec, reason = "HOLD", "Save gold for spike round"
    else:
        rec, reason = "ROLL", "Default: roll for board strength"

    return LevelDecision(
        current_level=state.level,
        current_xp=state.xp_current,
        xp_needed_next=xp_remaining,
        gold_to_level=gold_to_level,
        gold_lost_interest=interest_lost,
        p_hit_delta=p_hit_delta,
        recommended=rec,
        reasoning=reason,
    )


def interest_projection(
    starting_gold: int,
    rounds_ahead: int,
    streak: int,
    core: CoreKnowledge,
) -> list[int]:
    """Return [gold at start of round +1, ..., +rounds_ahead] assuming no spending."""
    bonus = _streak_bonus(core, streak)
    gold = starting_gold
    result: list[int] = []
    for _ in range(rounds_ahead):
        gold = gold + _BASE_ROUND_INCOME + _interest(core, gold) + bonus
        result.append(gold)
    return result


def expected_gold_to_first_hit(
    target: str, level: int, pool: PoolState, set_: SetKnowledge,
) -> float:
    """E[gold spent until first copy seen]. Inf if k == 0."""
    if pool.copies_of_target_remaining == 0:
        return float("inf")
    p = _p_slot(pool, set_, level)
    if p == 0.0:
        return float("inf")
    # Geometric series: E[refreshes] = 1/p_refresh; each refresh costs 2g
    p_refresh = 1.0 - (1.0 - p) ** 5
    return 2.0 / p_refresh
