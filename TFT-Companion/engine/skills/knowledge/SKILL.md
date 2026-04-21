# SKILL: knowledge loader (Phase 0)

> Build the loader module that reads `knowledge/*.yaml` and exposes typed Python APIs.
> This is the FIRST module any other module depends on.

## Purpose

Load `knowledge/core.yaml` → `CoreKnowledge` and `knowledge/set_<N>.yaml` →
`SetKnowledge`. Expose query helpers so callers never dig into the dict structure
themselves.

## Files you may edit

- `knowledge/__init__.py` (new)
- `schemas.py` (ONLY to add types — only with user approval if you find a gap)
- `tests/test_knowledge.py` (new)

**Do not touch** any other file.

## Public API (this is the contract — match it exactly)

```python
# knowledge/__init__.py
from __future__ import annotations
from pathlib import Path
from schemas import CoreKnowledge, SetKnowledge, PoolInfo

_CORE: CoreKnowledge | None = None
_SET_CACHE: dict[str, SetKnowledge] = {}

def load_core(path: Path | None = None) -> CoreKnowledge:
    """Load and cache knowledge/core.yaml. Singleton."""

def load_set(set_id: str, path: Path | None = None) -> SetKnowledge:
    """Load and cache knowledge/set_<set_id>.yaml."""

# Query helpers — callers use these, not raw dict access
def shop_odds(set_: SetKnowledge, level: int) -> list[float]:
    """Return [p_1cost, p_2cost, p_3cost, p_4cost, p_5cost] as fractions summing to 1.0.
    Level clamped to [1, 11]."""

def pool_size(set_: SetKnowledge, cost: int) -> PoolInfo:
    """Return PoolInfo for a given cost tier 1..5."""

def xp_to_reach(core: CoreKnowledge, level: int) -> int:
    """Cumulative XP needed from L1 to reach level L. Raises for L<2 or L>11."""

def xp_for_next_level(core: CoreKnowledge, current_level: int) -> int:
    """XP needed from current_level to current_level+1."""

def streak_bonus(core: CoreKnowledge, streak: int) -> int:
    """Return bonus gold for a streak length. Uses abs(streak) — win and loss same curve."""

def interest(core: CoreKnowledge, gold: int) -> int:
    """Return interest earned at start of round with `gold` gold. Capped at core.interest_cap."""

def spike_round_next(set_: SetKnowledge, current_stage: str) -> dict | None:
    """If the next round is a known spike, return {stage, archetype}. Else None."""
```

## Implementation notes

- Use `pyyaml` for YAML loading. Use `pydantic.parse_obj_as` or `Model.model_validate`.
- Shop odds come in as percents (0-100). Return fractions (0-1.0) from `shop_odds()`.
- Stage parsing: stages are strings like `"3-2"`. Never pass integers. `"X-Y"` → next
  round is `"X-(Y+1)"` up to Y=7, then `"(X+1)-1"`. Put this in a small helper.
- Cache aggressively — these files load once per process lifetime.

## Acceptance tests

File: `tests/test_knowledge.py`

```python
def test_load_core():
    c = load_core()
    assert c.xp_cost_per_buy == 4
    assert c.interest_cap == 5
    assert len(c.xp_thresholds) == 10
    assert len(c.streak_brackets) == 4
    assert c.scoring_weights.hp_risk == 1.5

def test_load_set_17():
    s = load_set("17")
    assert s.set_id == "17"
    assert s.name == "Space Gods"

def test_shop_odds_sum_to_one():
    s = load_set("17")
    for level in range(1, 12):
        odds = shop_odds(s, level)
        assert abs(sum(odds) - 1.0) < 0.001, f"level {level} sums to {sum(odds)}"
        assert len(odds) == 5

def test_shop_odds_values_set17():
    s = load_set("17")
    assert shop_odds(s, 7) == [0.19, 0.30, 0.35, 0.10, 0.01]
    assert shop_odds(s, 10) == [0.05, 0.10, 0.20, 0.40, 0.25]

def test_pool_size_set17():
    s = load_set("17")
    assert pool_size(s, 1).copies_per_champ == 22
    assert pool_size(s, 4).copies_per_champ == 10
    assert pool_size(s, 5).total == 72

def test_xp_to_reach():
    c = load_core()
    assert xp_to_reach(c, 2) == 2
    assert xp_to_reach(c, 4) == 10
    assert xp_to_reach(c, 7) == 76
    assert xp_to_reach(c, 9) == 200

def test_xp_for_next_level():
    c = load_core()
    assert xp_for_next_level(c, 6) == 36
    assert xp_for_next_level(c, 8) == 76

def test_streak_bonus():
    c = load_core()
    assert streak_bonus(c, 0) == 0
    assert streak_bonus(c, 2) == 0
    assert streak_bonus(c, 3) == 1
    assert streak_bonus(c, 4) == 1
    assert streak_bonus(c, 5) == 2
    assert streak_bonus(c, 6) == 3
    assert streak_bonus(c, 10) == 3
    # loss streaks use absolute value
    assert streak_bonus(c, -5) == 2
    assert streak_bonus(c, -3) == 1

def test_interest():
    c = load_core()
    assert interest(c, 0) == 0
    assert interest(c, 9) == 0
    assert interest(c, 10) == 1
    assert interest(c, 49) == 4
    assert interest(c, 50) == 5
    assert interest(c, 100) == 5  # capped

def test_spike_round_next():
    s = load_set("17")
    assert spike_round_next(s, "3-1")["stage"] == "3-2"
    assert spike_round_next(s, "4-1")["stage"] == "4-2"
    assert spike_round_next(s, "2-1") is None  # nothing spikes at 2-2
```

## Integration step (after tests pass)

1. In `state_builder.py`:
   - Change `from dataclasses import dataclass` to no-op (remove if no other dataclass).
   - Replace `@dataclass class GameState` with `from schemas import GameState`.
   - Update the `build_state()` return type and construction to use Pydantic.
   - Every caller of `state.to_dict()` still works because Pydantic `.model_dump()` is
     drop-in; but rename the method or add a shim if downstream code calls `.to_dict()`.
2. In `rules.py`:
   - Change `from_dataclass` imports to `from schemas import GameState, Fire`.
   - Rule functions that take `state_dict: dict` should now take `state: GameState`.
     Use `state.gold` not `state.get("gold")`. The 10 existing rules need mechanical
     edits only.
3. Run existing tests: `test_state_builder.py`, `test_rules.py`, `test_imports.py`.
   All must still pass.

## STATE.md entry on completion

```
## Phase 0 — DONE YYYY-MM-DD
- added: knowledge/__init__.py, knowledge/core.yaml, knowledge/set_17.yaml, schemas.py
- edited: state_builder.py (dataclass -> Pydantic), rules.py (import-only)
- deps added: pyyaml, pydantic>=2
- tests: 11/11 test_knowledge passing, existing tests still green
- notes: none
```

## Anti-patterns to avoid

- Do not add convenience methods to the Pydantic models in `schemas.py`. Helpers live
  here, not on the model.
- Do not read YAML files anywhere outside this module. Anyone who needs set data calls
  `load_set()`.
- Do not introduce a "Config" or "Settings" abstraction. YAML files + loader is the whole
  story.
