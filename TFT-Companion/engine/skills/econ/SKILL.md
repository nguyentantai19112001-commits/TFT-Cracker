# SKILL: econ — P(hit), roll-EV, level-EV math (Phase 1)

> Port wongkj12's Markov roll calculator to Python. Add level-vs-roll decision logic and
> interest projection. This is the math layer rules and recommender both call.

**Prerequisites:** Phase 0 complete. You may rely on `schemas.py` and `knowledge/`.

## Purpose

Answer three questions, deterministically and fast:

1. "Rolling N gold at level L, what's P(≥1, ≥2, ≥3 copies of champion C)?"
2. "Should I level now, hold, or roll?"
3. "If I don't spend, how much gold will I have at the start of round N?"

## Files you may edit

- `econ.py` (new)
- `tests/test_econ.py` (new)

**Do not touch** any other file.

## Public API

```python
# econ.py
from __future__ import annotations
from typing import Literal
from schemas import (
    GameState, PoolState, RollAnalysis, LevelDecision,
    SetKnowledge, CoreKnowledge,
)

def analyze_roll(
    target: str,
    level: int,
    gold: int,
    pool: PoolState,
    set_: SetKnowledge,
    method: Literal["markov", "hypergeo", "iid"] = "markov",
) -> RollAnalysis:
    """Compute P(hit ≥ 1, ≥ 2, ≥ 3 copies) of `target` by spending all `gold` at `level`."""

def level_vs_roll(
    state: GameState,
    target: str | None,
    pool: PoolState | None,
    core: CoreKnowledge,
    set_: SetKnowledge,
) -> LevelDecision:
    """Given current state and (optional) target unit, recommend LEVEL / HOLD / ROLL.

    If target and pool are None, reason only from stage pace + gold + HP.
    Otherwise compare P(hit at L) vs P(hit at L+1)."""

def interest_projection(
    starting_gold: int,
    rounds_ahead: int,
    streak: int,
    core: CoreKnowledge,
) -> list[int]:
    """Return [gold at start of round +1, +2, ..., +rounds_ahead] assuming no spending.
    Accounts for interest cap and streak bonus."""

def expected_gold_to_first_hit(
    target: str, level: int, pool: PoolState, set_: SetKnowledge,
) -> float:
    """E[gold spent until first copy seen]. Inf if k == 0."""
```

## The math — implement these formulas

**Per-slot probability of seeing target `C` in one shop slot:**
```
p_slot(C) = shop_odds[L][T] · k / R_T
```
where `T` = cost of C, `k` = `pool.copies_of_target_remaining`,
`R_T` = `pool.same_cost_copies_remaining`.

**Important:** the denominator is `R_T` (total same-cost copies remaining across the
pool), NOT `d · pool_size[T]`. This is how every published calculator does it, and the
difference matters once the lobby has units out.

**Per-refresh (5 slots, i.i.d. approx, used by every tool):**
```
p_refresh(>= 1) = 1 - (1 - p_slot)^5
```

**Over N gold spent (reroll = 2g → N/2 refreshes → 5N/2 slots):**
```
# Binomial approximation (method="iid")
slots = 5 * (gold // 2)
p_at_least_m = 1 - binom.cdf(m-1, slots, p_slot)
expected_copies = slots * p_slot
variance_copies = slots * p_slot * (1 - p_slot)
```

**Markov chain (method="markov", MORE ACCURATE, PORT FROM WONGKJ12):**
Build a `(k+1) x (k+1)` transition matrix M where `M[i][j]` is the probability of going
from `i` copies of C in the pool to `j` copies after one shop slot. Then after S slots,
the distribution is `M^S` applied to the starting state vector `[0, ..., 0, 1]` (we
start knowing there are k copies).

Reference: https://github.com/wongkj12/TFT-Rolling-Odds-Calculator (MIT license — the
README has the full derivation; port the JS to Python).

**Hypergeometric (method="hypergeo", for cross-checking):**
Use `scipy.stats.hypergeom` for sampling-without-replacement within each refresh,
compound across refreshes.

**Level decision logic (`level_vs_roll`):**

```
Compute:
  xp_to_level = core.xp_for_next_level(state.level) - state.xp_current  # xp needed
  gold_to_level = ceil(xp_to_level / core.xp_per_buy) * core.xp_cost_per_buy
  interest_lost = min(core.interest_cap, (state.gold // 10)) - min(core.interest_cap, ((state.gold - gold_to_level) // 10))

  if target and pool:
    p_now = analyze_roll(target, state.level, 30, pool, set_).p_hit_at_least_2
    p_next = analyze_roll(target, state.level + 1, 30, pool, set_).p_hit_at_least_2
    p_hit_delta = p_next - p_now
  else:
    p_hit_delta = 0.0

Decision rules (in order):
  1. if state.hp < 25 and state.level >= expected_level(state.stage):
       return ROLL (stabilize now, don't spend on XP)
  2. if state.level < expected_level(state.stage) and gold_to_level <= state.gold * 0.3:
       return LEVEL (pace behind, cheap enough)
  3. if p_hit_delta > 0.15:   # leveling helps a lot
       return LEVEL
  4. if state.gold < 30 and state.hp > 50:
       return HOLD (save for spike)
  5. default: ROLL
```

The thresholds above are first-cut. Tunable later based on replay.

## Implementation notes

- Use `numpy` for the Markov matrix. Use `scipy.stats.hypergeom` if available; if not,
  implement hypergeo by hand (simple combinatorics).
- Short-circuit: if `pool.copies_of_target_remaining == 0`, return all zeros.
- Cache Markov matrices? Not necessary — k is small (≤30) and each call is <1ms.
- `expected_gold_to_first_hit(...)` uses the geometric series: `E[gold] = 2 / (1 - (1 - p_slot)^5)`.
- `interest_projection` must handle streak interaction (streak bonus adds to base round
  gold, which compounds via interest next round).

## Acceptance tests

File: `tests/test_econ.py`

```python
import pytest
from econ import analyze_roll, level_vs_roll, interest_projection, expected_gold_to_first_hit
from schemas import PoolState, GameState
from knowledge import load_core, load_set

SET17 = load_set("17")
CORE = load_core()

# --- analyze_roll ---

def test_uncontested_4cost_50g_l8():
    """50g at L8 for uncontested Jinx — tftodds says ~80% for 2-star."""
    pool = PoolState(copies_of_target_remaining=10, same_cost_copies_remaining=120, distinct_same_cost=12)
    r = analyze_roll("Jinx", level=8, gold=50, pool=pool, set_=SET17)
    assert r.p_hit_at_least_2 > 0.75
    assert r.p_hit_at_least_2 < 0.90
    assert r.p_hit_at_least_1 > r.p_hit_at_least_2

def test_contested_drops_p_hit():
    """Same roll, but 3 opponents each hold 2 Jinx. k drops 10 → 4."""
    pool = PoolState(4, 114, 12)
    r = analyze_roll("Jinx", 8, 50, pool, SET17)
    assert r.p_hit_at_least_2 < 0.55

def test_zero_copies():
    pool = PoolState(0, 100, 12)
    r = analyze_roll("Jinx", 8, 50, pool, SET17)
    assert r.p_hit_at_least_1 == 0.0
    assert r.p_hit_at_least_2 == 0.0

def test_zero_gold():
    pool = PoolState(10, 120, 12)
    r = analyze_roll("Jinx", 8, 0, pool, SET17)
    assert r.p_hit_at_least_1 == 0.0

def test_methods_agree():
    """markov, hypergeo, iid must agree within 2% for k >= 3."""
    pool = PoolState(8, 100, 12)
    results = {m: analyze_roll("X", 8, 40, pool, SET17, method=m) for m in ["markov", "hypergeo", "iid"]}
    ps = [r.p_hit_at_least_2 for r in results.values()]
    assert max(ps) - min(ps) < 0.02

def test_expected_copies_consistency():
    """E[copies] should match the analytical expected value for iid."""
    pool = PoolState(10, 120, 12)
    r = analyze_roll("Jinx", 8, 50, pool, SET17, method="iid")
    # 5 * 25 slots * 0.22 * 10 / 120 = 2.29 expected copies
    assert 2.0 < r.expected_copies_seen < 2.6

def test_1cost_reroll_deep():
    """1-cost reroll at L5: 20g roll-down should give very high P(3-star)."""
    pool = PoolState(22, 286, 13)  # uncontested 1-cost
    r = analyze_roll("Kobuko", 5, 30, pool, SET17)
    assert r.p_hit_at_least_3 > 0.50

# --- level_vs_roll ---

def test_level_when_pace_behind():
    state = GameState(stage="4-2", round=None, gold=50, hp=70, level=6,
                      xp_current=0, xp_needed=36, streak=0, set_id="17")
    d = level_vs_roll(state, target=None, pool=None, core=CORE, set_=SET17)
    assert d.recommended == "LEVEL"

def test_roll_when_hp_critical():
    state = GameState(stage="4-2", round=None, gold=40, hp=20, level=7,
                      xp_current=0, xp_needed=48, streak=0, set_id="17")
    d = level_vs_roll(state, target=None, pool=None, core=CORE, set_=SET17)
    assert d.recommended == "ROLL"

def test_hold_when_low_gold_high_hp():
    state = GameState(stage="3-3", round=None, gold=24, hp=80, level=6,
                      xp_current=0, xp_needed=36, streak=0, set_id="17")
    d = level_vs_roll(state, target=None, pool=None, core=CORE, set_=SET17)
    assert d.recommended == "HOLD"

# --- interest_projection ---

def test_interest_projection_basic():
    proj = interest_projection(starting_gold=30, rounds_ahead=3, streak=0, core=CORE)
    # round 1: 30 + 5 base + 3 interest = 38 (minus any spend, which is 0)
    # round 2: 38 + 5 + 3 = 46
    # round 3: 46 + 5 + 4 = 55
    assert len(proj) == 3
    assert proj[0] == 38
    assert proj[2] >= 55

def test_interest_capped():
    proj = interest_projection(starting_gold=60, rounds_ahead=2, streak=0, core=CORE)
    # Interest always 5 max
    assert proj[0] == 60 + 5 + 5  # base + capped interest

def test_streak_bonus_applied():
    """5-streak adds +2 per round."""
    proj_streak = interest_projection(30, 2, streak=5, core=CORE)
    proj_no_streak = interest_projection(30, 2, streak=0, core=CORE)
    assert proj_streak[0] > proj_no_streak[0]  # +2 more gold
```

## Integration step (after tests pass)

Nothing yet. `econ.py` is pure library. Phase 3 wires it into `rules.py`. Phase 5 wires
it into `recommender.py`.

## STATE.md entry

```
## Phase 1 — DONE YYYY-MM-DD
- added: econ.py, tests/test_econ.py
- deps added: numpy (if not already present), scipy (optional — for hypergeom cross-check)
- tests: 14/14 test_econ passing
- cross-checked 3 scenarios against tftodds.com, all within 2%
```

## Anti-patterns to avoid

- Do not import `knowledge` at module top-level — import inside function, or take
  `set_` and `core` as parameters. Keeps testability clean.
- Do not cache `RollAnalysis` objects globally. Cheap enough to recompute.
- Do not round probabilities until the final output. Float math throughout.
- Do not implement a GameState-based wrapper like `roll_for_carry(state)`. Keep this
  layer numerically pure; the wrapper belongs in recommender.py.
