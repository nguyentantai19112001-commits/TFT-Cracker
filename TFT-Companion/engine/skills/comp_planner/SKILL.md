# SKILL: comp_planner — reachable archetypes (Phase 4)

> Hand-author the 12 dominant Set 17 comps as YAML. Build a planner that ranks them
> from the current state by P(reach) × expected_power × trait_fit.

**Prerequisites:** Phases 0, 1, 2 complete.

## Purpose

"What am I playing?" is the hardest question for the LLM to answer well. Without this
module the advisor gives shop-level advice with no endgame context. With it, every
recommendation lands on a named archetype with numeric reach probability and a concrete
list of next buys.

## Files you may edit

- `comp_planner.py` (new)
- `knowledge/archetypes/*.yaml` (new — 12 files, one per comp)
- `tests/test_comp_planner.py` (new)
- `tests/fixtures/comp_scenarios.yaml` (new)

## Public API

```python
# comp_planner.py
from __future__ import annotations
from pathlib import Path
from schemas import GameState, Archetype, CompCandidate, SetKnowledge
from pool import PoolTracker

def load_archetypes(dir_: Path | None = None) -> list[Archetype]:
    """Load all knowledge/archetypes/*.yaml into Archetype objects. Cached."""

def top_k_comps(
    state: GameState,
    pool: PoolTracker,
    archetypes: list[Archetype],
    set_: SetKnowledge,
    k: int = 3,
) -> list[CompCandidate]:
    """Rank archetypes by total_score desc, return top k."""

def score_archetype(
    archetype: Archetype,
    state: GameState,
    pool: PoolTracker,
    set_: SetKnowledge,
) -> CompCandidate:
    """Compute p_reach, expected_power, trait_fit, total_score for one archetype."""
```

## Archetype YAML format

`knowledge/archetypes/dark_star.yaml`:
```yaml
archetype_id: dark_star
display_name: "Dark Star"
target_level: 9
playstyle: standard

core_units:
  - Jhin         # primary carry, 5-cost Dark Star
  - Karma        # AP carry / caster, 4-cost Dark Star
  - Kai'Sa       # secondary carry, 3-cost Dark Star
  - Mordekaiser  # frontline, 2-cost Dark Star
  - Cho'Gath     # tank, 1-cost Dark Star
  - Lissandra    # utility / CC, 1-cost Dark Star

optional_units:
  - Vex          # 5-cost flex Dark Star
  - Morgana      # 5-cost flex AP carrier

required_traits:
  - [Dark Star, 6]

ideal_items:
  Jhin:
    - Giant Slayer
    - Infinity Edge
    - Last Whisper
  Karma:
    - Archangel's Staff
    - Jeweled Gauntlet
    - Hextech Gunblade
  Kai'Sa:
    - Guinsoo's Rageblade
    - Runaan's Hurricane
    - Bloodthirster

tier: "A"  # S / A / B / C — from current meta reports
```

Author 12 archetypes covering at minimum:
- 2-3 reroll comps (1-cost, 2-cost, 3-cost)
- 3-4 standard fast-8 comps
- 2-3 trait-vertical comps
- 1-2 flex comps with multiple carry options

Source meta reports from tactics.tools / mobalytics / TFTacademy for Set 17. Use your
own judgment on what's dominant; you'll revise per patch anyway.

## Scoring formulas

### `p_reach`

Probability we can assemble the core_units from here.

```python
def compute_p_reach(archetype, state, pool, set_):
    need = [u for u in archetype.core_units if not _we_have_it_starred(u, state)]
    if not need:
        return 1.0

    # Assume we'll reach target_level and have ~40g to spend there
    remaining_at_target = 40  # rough budget
    p_all = 1.0
    for champ in need:
        pool_state = pool.to_pool_state(champ)
        analysis = econ.analyze_roll(
            target=champ,
            level=archetype.target_level,
            gold=remaining_at_target // len(need),  # naive split
            pool=pool_state,
            set_=set_,
        )
        p_all *= analysis.p_hit_at_least_1
    return p_all
```

First-cut formula. Improve later by actually projecting gold trajectory from
`econ.interest_projection`.

### `expected_power`

Heuristic score 0..1. Use the archetype's tier + how many units we already have:

```python
TIER_BASE = {"S": 0.9, "A": 0.75, "B": 0.6, "C": 0.45}

def compute_expected_power(archetype, state):
    base = TIER_BASE[archetype.tier]
    have = sum(1 for u in archetype.core_units if _we_have_it(u, state))
    progress = have / len(archetype.core_units)
    return base * (0.5 + 0.5 * progress)   # 50-100% of tier depending on progress
```

### `trait_fit`

How well our current augments and items align with this archetype.

```python
def compute_trait_fit(archetype, state):
    score = 0.0

    # Augment alignment: +0.3 per augment that names a trait in required_traits
    for aug in state.augments:
        for trait, _ in archetype.required_traits:
            if trait.lower() in aug.lower():
                score += 0.3
                break

    # Item alignment: do completed items match at least one unit's ideal items?
    for item in state.completed_items_on_bench:
        if any(item in items for items in archetype.ideal_items.values()):
            score += 0.2

    # Board alignment: fraction of current board units that belong to archetype
    archetype_units = set(archetype.core_units) | set(archetype.optional_units)
    board_match = sum(1 for u in state.board if u.champion in archetype_units)
    if state.board:
        score += 0.5 * (board_match / len(state.board))

    return min(1.0, score)
```

### `total_score`

```python
total_score = 0.5 * p_reach + 0.3 * expected_power + 0.2 * trait_fit
```

Weights hand-tuned. Revisable.

## `recommended_next_buys`

Given the archetype and current state, return the next 3 units to prioritize:

```python
def _next_buys(archetype, state):
    # Priority: units in core that we don't have at all
    missing_core = [u for u in archetype.core_units if not _we_have_it(u, state)]
    # Then: units we have at 1-star that need 2-star
    upgrade_core = [u.champion for u in state.board + state.bench
                    if u.champion in archetype.core_units and u.star == 1]
    return (missing_core + upgrade_core)[:3]
```

## Acceptance tests

```python
import pytest
from comp_planner import load_archetypes, top_k_comps, score_archetype
from schemas import GameState, BoardUnit
from pool import PoolTracker
from knowledge import load_set

SET17 = load_set("17")

def test_all_archetypes_load():
    archs = load_archetypes()
    assert len(archs) >= 12
    for a in archs:
        assert len(a.core_units) >= 3
        assert a.target_level in (7, 8, 9, 10)

def test_top_comp_when_augment_matches():
    state = GameState(
        stage="3-1", gold=30, hp=80, level=5, set_id="17",
        augments=["Dark Star Soul"],
    )
    pt = PoolTracker(SET17)
    top = top_k_comps(state, pt, load_archetypes(), SET17, k=3)
    assert top[0].archetype.archetype_id == "dark_star"
    assert top[0].trait_fit > 0.3

def test_low_pool_lowers_p_reach():
    """Own board already holds 6 Jhin copies (2-star) — pool depleted."""
    state = GameState(
        stage="4-2", gold=40, hp=70, level=8, set_id="17",
        board=[BoardUnit(champion="Jhin", star=2)],
    )
    pt = PoolTracker(SET17)
    pt.observe_own_board(state.board, state.bench)
    top = top_k_comps(state, pt, load_archetypes(), SET17, k=5)
    dark_star = next((c for c in top if c.archetype.archetype_id == "dark_star"), None)
    # Having own Jhin 2-star actually means we're in the comp — p_reach should be higher,
    # not lower. This test verifies the planner doesn't crash on low-pool state.
    assert dark_star is not None

def test_progress_raises_score():
    """Having 3/6 core units should score higher than 0/6."""
    empty = GameState(stage="4-1", gold=30, hp=70, level=7, set_id="17")
    with_board = GameState(
        stage="4-1", gold=30, hp=70, level=7, set_id="17",
        board=[BoardUnit(champion=c, star=1) for c in ["Jhin", "Karma", "Kai'Sa"]],
    )
    pt = PoolTracker(SET17)
    dark_star = next(a for a in load_archetypes() if a.archetype_id == "dark_star")
    empty_score = score_archetype(dark_star, empty, pt, SET17).total_score
    loaded_score = score_archetype(dark_star, with_board, pt, SET17).total_score
    assert loaded_score > empty_score

def test_recommended_buys_prioritizes_missing():
    state = GameState(
        stage="3-2", gold=20, hp=80, level=6, set_id="17",
        board=[BoardUnit(champion="Jhin", star=1)],
    )
    pt = PoolTracker(SET17)
    top = top_k_comps(state, pt, load_archetypes(), SET17, k=1)
    cand = top[0]
    # already have Jhin, so next buys should not start with Jhin
    if cand.recommended_next_buys:
        assert cand.recommended_next_buys[0] != "Jhin"

def test_top_k_respects_k():
    state = GameState(stage="3-1", gold=20, hp=80, level=5, set_id="17")
    pt = PoolTracker(SET17)
    archs = load_archetypes()
    assert len(top_k_comps(state, pt, archs, SET17, k=3)) == 3
    assert len(top_k_comps(state, pt, archs, SET17, k=5)) == 5
```

## STATE.md entry

```
## Phase 4 — DONE YYYY-MM-DD
- added: comp_planner.py, knowledge/archetypes/ (12 yaml files), tests
- tests: 6/6 test_comp_planner passing
- known limitation: p_reach uses naive gold split across missing units; revisit if
  recommendations feel off
```

## Anti-patterns to avoid

- Do not scrape live meta sites at runtime. Archetypes are hand-authored files.
- Do not add more than 15 archetypes per set. If you have more, you haven't actually
  decided which ones matter.
- Do not parameterize the scoring weights per-archetype. Global weights are fine.
- Do not call `econ.analyze_roll` more than once per archetype-unit pair. Cache within
  the `top_k_comps` call.
