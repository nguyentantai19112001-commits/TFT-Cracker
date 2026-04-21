# SKILL: recommender — scored top-K actions (Phase 5)

> Enumerate candidate actions of each of the 7 types, compute 5-dimension scores for
> each, return top-3 with reasoning tags.

**Prerequisites:** Phases 0, 1, 2, 3, 4 complete.

## Purpose

This is the decision layer. It replaces "LLM decides what to do" with "deterministic
scoring picks the top 3; LLM narrates which one". Everything numeric happens here.

## Files you may edit

- `recommender.py` (new)
- `tests/test_recommender.py` (new)
- `tests/fixtures/recommender_scenarios.yaml` (new)

## Public API

```python
# recommender.py
from __future__ import annotations
from schemas import (
    GameState, ActionCandidate, ActionType, ActionScores,
    CompCandidate, Fire, SetKnowledge, CoreKnowledge, ScoringWeights,
)
from pool import PoolTracker

def top_k(
    state: GameState,
    fires: list[Fire],
    comps: list[CompCandidate],
    pool: PoolTracker,
    set_: SetKnowledge,
    core: CoreKnowledge,
    k: int = 3,
) -> list[ActionCandidate]:
    """Full pipeline: enumerate -> score -> rank -> top k."""

def enumerate_candidates(
    state: GameState,
    comps: list[CompCandidate],
    pool: PoolTracker,
    set_: SetKnowledge,
) -> list[ActionCandidate]:
    """Generate ~15-25 reasonable candidates. Candidates are pruned by obvious filters
    (can't BUY what's not in shop, can't LEVEL at 10+, etc.)."""

def score_candidate(
    candidate: ActionCandidate,
    state: GameState,
    fires: list[Fire],
    comps: list[CompCandidate],
    pool: PoolTracker,
    set_: SetKnowledge,
    core: CoreKnowledge,
) -> ActionCandidate:
    """Compute the 5 scores + total_score + reasoning_tags. Returns candidate with
    scores filled in."""
```

## Candidate enumeration

### What to enumerate

For each action type, generate the reasonable variants:

**BUY** — one per relevant shop unit:
- For every unit in shop where `unit.champion ∈ top_comp.core_units ∪ optional_units`
  for any top-3 CompCandidate, OR where we already have 2 copies of it
- Skip if bench is full and no space for another copy
- Params: `{"champion": name, "shop_slot": idx}`

**SELL** — one per dispensable unit:
- For every unit on bench or 1-cost on board with no items and not in top-3 comps
- Params: `{"unit_index": idx, "location": "bench" | "board"}`

**ROLL_TO** — one per target gold floor:
- 3 variants: roll to 0 (full roll), roll to 20 (keep interest tier), roll to 30
- Params: `{"gold_floor": n}`

**LEVEL_UP** — at most one:
- If level < 10 and xp_for_next_level affordable with ≥20% gold left after
- Params: `{}`

**HOLD_ECON** — exactly one:
- Always a candidate
- Params: `{}`

**SLAM_ITEM** — one per completable recipe:
- For every pair of components on bench that combine
- Prefer completions that land on a unit in top comp
- Params: `{"components": [c1, c2], "carrier": unit_name}`

**PIVOT_COMP** — one per secondary comp:
- If top_comp.total_score - second_comp.total_score < 0.2, pivot is a real option
- Params: `{"archetype_id": id, "swap_units": [...]}`

Total: typically 10-20 candidates per F9 press.

## The 5 scores

Each score is a float in `[-3, +3]`. Computed independently; then combined via
`core.scoring_weights` into `total_score`.

### `tempo`

"Does this progress board power *this round*?"

```python
def _score_tempo(cand, state, comps):
    if cand.action_type == ActionType.BUY:
        # Buying a 2-star completion is huge tempo
        if _completes_2_star(cand.params["champion"], state):
            return +3
        # Buying a unit we already field is +1
        if cand.params["champion"] in [u.champion for u in state.board]:
            return +1
        return 0
    if cand.action_type == ActionType.ROLL_TO:
        g = state.gold - cand.params["gold_floor"]
        return min(+3, g / 10)  # rolling more gold = more tempo
    if cand.action_type == ActionType.LEVEL_UP:
        return +1 if state.stage_num() >= 4 else 0
    if cand.action_type == ActionType.HOLD_ECON:
        return -1  # holding is by definition not tempo
    if cand.action_type == ActionType.SLAM_ITEM:
        return +2 if cand.params.get("carrier") in _top_comp_carriers(comps) else +1
    if cand.action_type == ActionType.SELL:
        return -1 if cand.params.get("location") == "board" else 0
    if cand.action_type == ActionType.PIVOT_COMP:
        return -2  # pivots cost tempo by definition
    return 0
```

### `econ`

"Does this preserve interest / streak gold?"

```python
def _score_econ(cand, state, core):
    interest_now = min(core.interest_cap, state.gold // 10)

    if cand.action_type == ActionType.HOLD_ECON:
        return +2 if interest_now >= 4 else +1
    if cand.action_type == ActionType.ROLL_TO:
        gold_after = cand.params["gold_floor"]
        interest_after = min(core.interest_cap, gold_after // 10)
        lost = interest_now - interest_after
        return -min(3, lost)  # more interest lost = worse
    if cand.action_type == ActionType.LEVEL_UP:
        # leveling costs gold → reduces interest
        xp_needed = _xp_needed(state, core)
        gold_needed = ceil(xp_needed / core.xp_per_buy) * core.xp_cost_per_buy
        return -1 if gold_needed >= 10 else 0
    if cand.action_type == ActionType.BUY:
        cost = _shop_cost(cand.params["champion"], state)
        return -1 if cost >= 3 and state.gold - cost < (interest_now * 10) else 0
    return 0
```

### `hp_risk`

"Does this reduce HP loss projection?"

```python
def _score_hp_risk(cand, state):
    if state.hp >= 60:
        # HP fine; HP considerations don't dominate
        multiplier = 0.3
    elif state.hp >= 40:
        multiplier = 1.0
    elif state.hp >= 25:
        multiplier = 2.0
    else:
        multiplier = 3.0

    raw = 0
    if cand.action_type == ActionType.ROLL_TO:
        # rolling for stabilization when HP low
        g = state.gold - cand.params["gold_floor"]
        raw = min(+3, g / 10) if state.hp < 40 else 0
    elif cand.action_type == ActionType.HOLD_ECON and state.hp < 35:
        raw = -2
    elif cand.action_type == ActionType.BUY and state.hp < 40:
        raw = +1 if _is_board_upgrade(cand, state) else 0
    elif cand.action_type == ActionType.LEVEL_UP and state.hp < 30:
        raw = -1  # leveling without rolling at low HP is risky
    elif cand.action_type == ActionType.SLAM_ITEM and state.hp < 45:
        raw = +2  # slam everything at low HP

    return raw * multiplier / 3  # normalize to ~[-3, +3]
```

### `board_strength`

"Does this improve expected fight outcome?"

Use existing `scoring.compute_board_strength` as the baseline. Compute the projected
board strength AFTER the action and return the delta, normalized.

```python
def _score_board_strength(cand, state, projected_board_delta: float):
    # projected_board_delta is the expected change in board_strength 0-100
    return max(-3, min(+3, projected_board_delta / 10))
```

Projecting delta requires applying the action to the state; v1 can use heuristic deltas:
- BUY of upgrade: +8
- BUY of 2-star completion: +20
- ROLL_TO with econ.analyze_roll giving p_hit_at_least_2 > 0.5: +12 * p_hit
- LEVEL_UP: +5 (new unit slot) + 5 if new cost-tier unlocks
- SELL: -5
- SLAM_ITEM on carry: +15
- HOLD_ECON: 0
- PIVOT: varies; use `_pivot_power_delta`

### `pivot_value`

"Does this align with a reachable strong comp?"

```python
def _score_pivot_value(cand, comps):
    if not comps:
        return 0
    top_comp = comps[0]
    if cand.action_type == ActionType.BUY:
        if cand.params["champion"] in top_comp.archetype.core_units:
            return +2
        if cand.params["champion"] in top_comp.archetype.optional_units:
            return +1
        # not in top comp at all
        return -1
    if cand.action_type == ActionType.PIVOT_COMP:
        target = next((c for c in comps if c.archetype.archetype_id == cand.params["archetype_id"]), None)
        return +2 if target and target.total_score > 0.7 else 0
    if cand.action_type == ActionType.SELL:
        # selling a unit we were going to use is bad
        unit = _resolve_unit(cand, state)
        if unit and unit.champion in top_comp.archetype.core_units:
            return -2
    return 0
```

## Combining into `total_score`

```python
def _combine(scores: ActionScores, weights: ScoringWeights) -> float:
    return (
        weights.tempo * scores.tempo
        + weights.econ * scores.econ
        + weights.hp_risk * scores.hp_risk
        + weights.board_strength * scores.board_strength
        + weights.pivot_value * scores.pivot_value
    )
```

## Reasoning tags

Attach human-readable tags per candidate. These get passed to the advisor so it can
reference them in the narration. Examples:

- `spike_round` — if next round is in set_.spike_rounds
- `interest_kept` — if resulting gold keeps interest tier
- `interest_lost` — opposite
- `hp_danger` — if hp < 35
- `streak_preserve` — if streak magnitude ≥ 3 and action maintains it
- `streak_break` — opposite
- `pool_favored` — if analyze_roll gives p_hit > 0.6
- `pool_unfavored` — opposite
- `comp_reachable` — if top comp p_reach > 0.5
- `comp_low_pool` — if own holdings have already depleted a core unit's pool

## Acceptance tests

```python
import pytest
from recommender import top_k, enumerate_candidates
from schemas import GameState, BoardUnit
from pool import PoolTracker
from comp_planner import load_archetypes, top_k_comps
from rules import evaluate
import knowledge as km, econ

SET17 = km.load_set("17")
CORE = km.load_core()
ARCHS = load_archetypes()

def _scenario(**overrides) -> dict:
    """Helper: base state + overrides."""
    base = dict(stage="3-1", round="PvP", gold=20, hp=70, level=5,
                streak=0, set_id="17", board=[], bench=[], shop=[],
                active_traits=[], augments=[])
    base.update(overrides)
    state = GameState(**base)
    pt = PoolTracker(SET17)
    comps = top_k_comps(state, pt, ARCHS, SET17, k=3)
    fires = evaluate(state, econ, pt, km)
    return state, fires, comps, pt

def test_hp_urgent_favors_roll():
    state, fires, comps, pt = _scenario(hp=25, gold=40, level=7)
    top = top_k(state, fires, comps, pt, SET17, CORE, k=3)
    assert top[0].action_type == ActionType.ROLL_TO

def test_interest_cap_favors_spend():
    state, fires, comps, pt = _scenario(hp=70, gold=54, level=6, streak=0)
    top = top_k(state, fires, comps, pt, SET17, CORE, k=3)
    assert top[0].action_type != ActionType.HOLD_ECON

def test_win_streak_with_strong_board_favors_hold():
    state, fires, comps, pt = _scenario(hp=80, gold=48, level=6, streak=8,
                                          board=[BoardUnit(champion="Kobuko", star=2, items=[])])
    top = top_k(state, fires, comps, pt, SET17, CORE, k=3)
    assert top[0].action_type == ActionType.HOLD_ECON

def test_low_gold_low_level_pace_favors_level():
    state, fires, comps, pt = _scenario(stage="4-2", hp=70, gold=24, level=6, streak=0)
    top = top_k(state, fires, comps, pt, SET17, CORE, k=3)
    # With 24g at L6 at stage 4-2, level is common advice
    assert top[0].action_type in (ActionType.LEVEL_UP, ActionType.BUY, ActionType.ROLL_TO)

def test_components_on_bench_surfaces_slam():
    state, fires, comps, pt = _scenario(
        hp=50, gold=30, level=6,
        board=[BoardUnit(champion="Xayah", star=2, items=[])],
        item_components_on_bench=["BF Sword", "Recurve Bow", "Tear"],
    )
    top = top_k(state, fires, comps, pt, SET17, CORE, k=5)
    assert any(c.action_type == ActionType.SLAM_ITEM for c in top)

def test_top_k_respects_k():
    state, fires, comps, pt = _scenario()
    for k in (1, 3, 5):
        assert len(top_k(state, fires, comps, pt, SET17, CORE, k=k)) <= k

def test_reasoning_tags_present():
    state, fires, comps, pt = _scenario(hp=25, gold=40)
    top = top_k(state, fires, comps, pt, SET17, CORE, k=3)
    assert any("hp_danger" in c.reasoning_tags for c in top)

def test_scores_in_bounds():
    state, fires, comps, pt = _scenario()
    top = top_k(state, fires, comps, pt, SET17, CORE, k=5)
    for c in top:
        for score_val in [c.scores.tempo, c.scores.econ, c.scores.hp_risk,
                          c.scores.board_strength, c.scores.pivot_value]:
            assert -3 <= score_val <= 3, f"Score out of bounds: {score_val}"
```

## STATE.md entry

```
## Phase 5 — DONE YYYY-MM-DD
- added: recommender.py, tests/test_recommender.py, tests/fixtures/recommender_scenarios.yaml
- tests: 8/8 test_recommender passing
- measured: 15-20 candidates enumerated per scenario, <80ms per top_k call
```

## Anti-patterns to avoid

- Do not make `enumerate_candidates` exhaustive. 15-25 candidates. Quality over quantity.
- Do not use ML or training. This is all heuristic scoring.
- Do not hide the 5 scores. They must be visible in the ActionCandidate so the advisor
  (and future debugging) can see breakdowns.
- Do not call `econ.analyze_roll` per-candidate uncached. If you need P(hit) for a
  target in 5 candidates, call it once.
