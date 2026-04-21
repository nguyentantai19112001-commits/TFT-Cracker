# SKILL: pool — pool tracker (Phase 2)

> Maintain point-estimate `k_effective` and `R_T_effective` for every champion based on
> own holdings. Opponent scouting is v2.5 scope — not in v2.

**Prerequisites:** Phase 0 + Phase 1 complete.

## Purpose

Before `pool.py`, the rules layer could only ask "is this unit uncontested?" heuristically.
After `pool.py`, any caller can ask "how many copies of this unit are likely remaining?" and
get a calibrated estimate with a confidence interval — based on our own buys and sells.

Scope: **point estimates only, own-holdings only**. No full Bayesian inference. No opponent
scouting (v2.5 scope). A champion's `k` decrements when we observe our own board/bench changes.

## Files you may edit

- `pool.py` (new)
- `tests/test_pool.py` (new)
- `state_builder.py` (minor — instantiate `PoolTracker` and hook observe-calls)

## Public API

```python
# pool.py
from __future__ import annotations
from schemas import BoardUnit, ShopSlot, GameState, PoolBelief, PoolState, SetKnowledge

class PoolTracker:
    """Per-game tracker. Own-holdings only — opponent data is v2.5 scope."""

    def __init__(self, set_: SetKnowledge):
        """Initialize beliefs to full pool for every champion in the set."""

    def observe_own_board(self, board: list[BoardUnit], bench: list[BoardUnit]) -> None:
        """Register units we're currently holding. Call every F9 so the tracker stays
        in sync with our own purchases/sales without needing separate buy/sell events."""

    def observe_shop(self, shop: list[ShopSlot]) -> None:
        """No-op in v2 — hook for future Bayesian extension."""

    def belief_for(self, champion: str) -> PoolBelief:
        """Return current belief for a specific champion."""

    def to_pool_state(self, champion: str) -> PoolState:
        """Convenience: convert a belief into the PoolState type econ.py consumes."""

    def reset(self) -> None:
        """Clear all beliefs — call when a new game starts."""
```

## Implementation notes

### Internal data structure

```python
self._k_estimate: dict[str, int]     # champion -> remaining copies
self._own_count: dict[str, int]      # champ -> copies we hold
self._cost_by_champ: dict[str, int]  # champion -> cost tier, loaded at init
```

### Initialization

For every champion in the set, `k_estimate = pool_size[cost].copies_per_champ`.
The champion list comes from `game_assets.py`:
```python
import game_assets
champions_with_costs: dict[str, int] = {
    name: info["cost"] for name, info in game_assets.CHAMPIONS.items()
}
```

### `observe_own_board`

Maintain `_own_count` separately. Re-compute every F9:
1. Compute copies in new board+bench (star 1 = 1 copy, star 2 = 3, star 3 = 9).
2. Delta = current - prior per champion.
3. Decrement/increment `_k_estimate` by delta. Clamp to `[0, copies_per_champ]`.

### `belief_for`

Return:
- `k_estimate` = `_k_estimate[champion]`
- `k_lower_90` = `max(0, k_estimate - 2)` — flat ±2 uncertainty (no scouting data to sharpen it)
- `k_upper_90` = `min(copies_per_champ, k_estimate + 2)`
- `r_t_estimate` = sum of k_estimate across all champions of the same cost tier.

### Thread safety

Not required. Single QThread per F9 press.

### Reset semantics

`session.start_game()` should call `tracker.reset()`.

## Acceptance tests

```python
import pytest
from pool import PoolTracker
from schemas import BoardUnit
from knowledge import load_set

SET17 = load_set("17")
_JINX_COPIES = 20  # Jinx is 2-cost in Set 17

def test_fresh_tracker_full_pool():
    t = PoolTracker(SET17)
    assert t.belief_for("Jinx").k_estimate == _JINX_COPIES

def test_own_board_decrements():
    t = PoolTracker(SET17)
    t.observe_own_board(board=[BoardUnit(champion="Jinx", star=2)], bench=[])
    assert t.belief_for("Jinx").k_estimate == _JINX_COPIES - 3

def test_sell_increments_back():
    t = PoolTracker(SET17)
    t.observe_own_board([BoardUnit(champion="Jinx", star=2)], [])
    t.observe_own_board([], [])
    assert t.belief_for("Jinx").k_estimate == _JINX_COPIES

def test_r_t_estimate_drops():
    t = PoolTracker(SET17)
    r_t_fresh = t.belief_for("Jinx").r_t_estimate
    t.observe_own_board([BoardUnit(champion="Jinx", star=2)], [])
    assert t.belief_for("Jinx").r_t_estimate == r_t_fresh - 3

def test_to_pool_state_round_trip():
    t = PoolTracker(SET17)
    t.observe_own_board([BoardUnit(champion="Jinx", star=1)], [])
    p = t.to_pool_state("Jinx")
    assert p.copies_of_target_remaining == _JINX_COPIES - 1

def test_reset():
    t = PoolTracker(SET17)
    t.observe_own_board([BoardUnit(champion="Jinx", star=2)], [])
    t.reset()
    assert t.belief_for("Jinx").k_estimate == _JINX_COPIES
```

## Integration step

In `state_builder.py`:
```python
import pool as _pool

_TRACKER: _pool.PoolTracker | None = None

def get_tracker(set_: SetKnowledge) -> _pool.PoolTracker:
    global _TRACKER
    if _TRACKER is None:
        _TRACKER = _pool.PoolTracker(set_)
    return _TRACKER

def build_state(...) -> GameState:
    state = _vision_step(...)
    tracker = get_tracker(knowledge.load_set(state.set_id))
    tracker.observe_own_board(state.board, state.bench)
    ...
```

In `session.py`:
```python
def start_game(...):
    from state_builder import _TRACKER
    if _TRACKER:
        _TRACKER.reset()
```

## STATE.md entry

```
## Phase 2 — DONE YYYY-MM-DD
- added: pool.py, tests/test_pool.py
- edited: state_builder.py (+ tracker hook), session.py (+ reset on new game)
- tests: 6/6 test_pool passing
- notes: own-holdings only; opponent scouting is v2.5 scope
```

## Anti-patterns to avoid

- Do not add `observe_scout` — scouting is v2.5 scope, not v2.
- Do not persist PoolTracker to SQLite. Per-game in-memory object only.
- Do not make `k_estimate` float. Copies are discrete integers.
- Do not handle champions the set doesn't have — `belief_for("UnknownName")` raises `KeyError`.
