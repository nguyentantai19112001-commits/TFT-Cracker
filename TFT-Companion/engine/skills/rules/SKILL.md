# SKILL: rules — expand from 10 to ~40 rules (Phase 3)

> Encode every deterministic heuristic from `data/TFT_PLAYBOOK.md` as a rule. Rules call
> `econ`, `pool`, and `knowledge` — no hardcoded numbers. Each rule has a positive and a
> negative test fixture.

**Prerequisites:** Phases 0, 1, 2 complete.

## Purpose

The rules layer catches the five failure modes (leak, mislevel, break streak, over-roll,
ignore HP) directly and deterministically. Every rule fire is short, testable, and
explains exactly why it fired. The advisor narrates what the rules already determined.

## Files you may edit

- `rules.py` (extend existing — keep 10 existing rules, add ~30 new)
- `tests/test_rules.py` (extend)
- `tests/fixtures/rule_scenarios.yaml` (new)

## Public API

Already exists. Don't change the contract:

```python
# rules.py
from schemas import GameState, Fire

def evaluate(state: GameState, econ_mod, pool_tracker, knowledge_mod) -> list[Fire]:
    """Run every rule. Returns fires sorted by severity descending."""
```

## Rule catalog — the 30+ to add

Each rule: `rule_id`, what it catches, severity, action tag, trigger condition.

### Economy rules (target: no leaking gold)

| rule_id | catches | severity | action | trigger |
|---|---|---|---|---|
| `ECON_BELOW_INTEREST` | (existing) sitting under 10g | 0.7 | HOLD_ECON | gold < 10, streak > -3 |
| `ECON_INTEREST_NEAR_THRESHOLD` | (existing) 1-2g from next tier | 0.4 | HOLD_ECON | gold < 50, nearest_above - gold ≤ 2 |
| `ECON_OVER_CAP_WASTE` | at 50+ gold, not spending | 0.7 | SPEND | gold ≥ 55, stage ≥ 4-1 |
| `ECON_ROUND_LOSS_MOMENTUM` | about to break loss streak accidentally | 0.7 | HOLD_BOARD | streak ≤ -3, board strength exceeds stage expectation |
| `ECON_WIN_STREAK_MAINTAIN` | about to break win streak accidentally | 0.5 | PUSH_BOARD | streak ≥ 3, board strength below stage expectation |

### Leveling rules (target: level at the right time)

| rule_id | catches | severity | action | trigger |
|---|---|---|---|---|
| `LEVEL_PACE_BEHIND` | (existing, keep) | 0.7 | LEVEL_UP | level < expected_level(stage), delta ≥ 2 |
| `LEVEL_PACE_AHEAD` | leveling too fast (econ leak) | 0.4 | HOLD_ECON | level > expected_level(stage) + 1 |
| `LEVEL_SPIKE_WINDOW` | 1 XP from leveling into a spike round | 0.5 | LEVEL_UP | xp_for_next_level(state.level) - state.xp_current ≤ 4, spike_round_next(set, state.stage) is not None |
| `LEVEL_EV_POSITIVE` | target P(hit) jumps >15% at L+1 | 0.6 | LEVEL_UP | econ.level_vs_roll gives recommended=LEVEL with p_hit_delta > 0.15 |
| `LEVEL_EV_NEGATIVE` | leveling would collapse econ for marginal gain | 0.5 | HOLD_ECON | gold_to_level > 0.4 * state.gold and p_hit_delta < 0.05 |

### Rolling rules (target: don't over-roll)

| rule_id | catches | severity | action | trigger |
|---|---|---|---|---|
| `ROLL_EV_NEGATIVE` | rolling at terrible P(hit) | 0.8 | HOLD_ECON | a primary_target exists; analyze_roll says p_hit_at_least_2 < 0.25 for gold available |
| `ROLL_EV_STRONG` | clear green light | 0.4 | ROLL_TO | analyze_roll p_hit_at_least_2 > 0.75 for gold available |
| `ROLL_HP_PANIC` | HP low, must roll to stabilize | 1.0 | ROLL_TO | state.hp < 30, state.gold ≥ 10 |
| `ROLL_NOT_ON_LEVEL` | rolling at level where target doesn't even appear | 1.0 | LEVEL_UP | shop_odds[state.level][target_cost] == 0 |
| `ROLL_ODDS_FAVORED_NEXT_LEVEL` | wait 1 XP, P(hit) is much better | 0.5 | LEVEL_UP | p_hit_next_level > 2 * p_hit_this_level |

### HP rules (target: don't die)

| rule_id | catches | severity | action | trigger |
|---|---|---|---|---|
| `HP_URGENT` | (existing) HP < 30 | 1.0 | ROLL_TO | hp < 30 |
| `HP_CAUTION` | (existing) 30 ≤ HP < 50 | 0.4 | BOARD_CHECK | 30 ≤ hp < 50 |
| `HP_DANGER_ZONE` | HP < 40 + no streak gold | 0.7 | ROLL_TO | hp < 40 and abs(streak) < 3 |
| `HP_LOSE_STREAK_CAP` | HP too low to keep loss-streaking | 0.8 | ROLL_TO | streak ≤ -3 and hp < 35 |

### Streak rules (target: maintain streak momentum)

| rule_id | catches | severity | action | trigger |
|---|---|---|---|---|
| `STREAK_LOSE_BONUS` | (existing info) | 0.1 | INFO | streak ≤ -2 |
| `STREAK_WIN_BONUS` | (existing info) | 0.1 | INFO | streak ≥ 2 |
| `STREAK_LOSE_CAP_APPROACHING` | about to hit cap, plan stabilization | 0.5 | PLAN_STAB | streak == -5, hp > 35 |
| `STREAK_WIN_CAP_APPROACHING` | similar for winstreak | 0.4 | PUSH_BOARD | streak == 5 |

### Comp / pivot rules

| rule_id | catches | severity | action | trigger |
|---|---|---|---|---|
| `TRAIT_UNCOMMITTED` | (existing) <2 real traits at stage 3-2+ | 0.4 | COMMIT_DIRECTION | stage_key ≥ 3.2 and real_traits < 2 |
| `TRAIT_VERTICAL_OVER_INVEST` | >2 copies of same mid-cost unit with no trait payoff | 0.4 | PIVOT_COMP | same-cost-same-champ >= 3 and that champ isn't in any active trait breakpoint |
| `COMP_UNREACHABLE` | top comp P(reach) < 15% | 0.6 | PIVOT_COMP | comp_planner top.p_reach < 0.15 |
| `COMP_ITEM_FIT_BROKEN` | holding items that don't fit any reachable comp | 0.5 | PIVOT_COMP | completed_items don't map to any top-3 CompCandidate's ideal_items |

### Item / slam rules

| rule_id | catches | severity | action | trigger |
|---|---|---|---|---|
| `ITEM_SLAM_MANDATE` | 3+ uncombined components at stage 3-2+ | 0.5 | SLAM_ITEM | len(component_bench) ≥ 3 and stage_key ≥ 3.2 |
| `ITEM_WRONG_CARRIER` | completed item on a unit that isn't a carrier | 0.3 | ITEM_REPLAN | heuristic: item on <3-cost unit that isn't in an active trait |

### Stage / mechanic rules

| rule_id | catches | severity | action | trigger |
|---|---|---|---|---|
| `SPIKE_ROUND_NEXT` | (existing) | 0.4 | PLAN_ROLL | next round is in set_.spike_rounds |
| `REALM_OF_GODS_NEXT` | (existing Set 17 specific) | 0.7 | PLAN_GOD_PICK | stage == 4-6 |
| `STAGE_3_1_DECISION_POINT` | classic roll-or-level inflection | 0.3 | INFO | stage == "3-1" |
| `STAGE_4_2_FASTSPIKE` | fast-8 players should spike here | 0.4 | PLAN_ROLL | stage == "4-2" and state.level ≥ 8 |

### Board / power rules

| rule_id | catches | severity | action | trigger |
|---|---|---|---|---|
| `BOARD_WEAK_FOR_STAGE` | board_strength < 40 at stage_key ≥ 3.2 | 0.6 | ROLL_TO | scoring.compute_board_strength < 40 and stage_key ≥ 3.2 |
| `BOARD_UNDER_CAP` | fewer units than level allows (cap exists, not enforced by game but bad) | 0.3 | BUY | len(board) < state.level |

**Rules total:** 10 existing + 29 above = 39. (ROLL_CONTESTED_BAIL removed in Phase 3.5a — requires scouting data not available in v2.)

## Implementation notes

### Rule function signature

Every rule function takes `(state, econ_mod, pool_tracker, knowledge_mod)` and returns
`Fire | None`. Keep them pure. Swallow exceptions at the top-level `evaluate()` so one
bad rule can't crash the pipeline (pattern already exists in v1).

### Example rule implementation

```python
def _roll_ev_negative(state: GameState, econ_mod, pool_tracker, km) -> Fire | None:
    """Don't roll at garbage odds."""
    primary_target = _infer_primary_target(state, pool_tracker)  # helper
    if primary_target is None:
        return None
    if state.gold < 10:
        return None  # nothing to roll
    set_ = km.load_set(state.set_id)
    pool_state = pool_tracker.to_pool_state(primary_target)
    analysis = econ_mod.analyze_roll(
        target=primary_target, level=state.level, gold=state.gold,
        pool=pool_state, set_=set_,
    )
    if analysis.p_hit_at_least_2 >= 0.25:
        return None
    return Fire(
        rule_id="ROLL_EV_NEGATIVE",
        severity=0.8,
        action="HOLD_ECON",
        message=f"Rolling for {primary_target} at L{state.level}, {state.gold}g → only {analysis.p_hit_at_least_2:.0%} P(2-star). Hold.",
        data={"target": primary_target, "p_hit_at_least_2": analysis.p_hit_at_least_2},
    )
```

### `_infer_primary_target` helper

Heuristic: the champion with the highest cost on-board that is not yet 2-star, weighted
by items on it. Formalize as:
```
candidates = [unit for unit in state.board if unit.star < 2]
return max(candidates, key=lambda u: u.cost * (1 + 0.5 * len(u.items)), default=None)
```
Or if no obvious candidate, fall back to the top-CompCandidate's missing units if
comp_planner is available. In Phase 3 comp_planner doesn't exist yet, so heuristic only.

### Loading `data/TFT_PLAYBOOK.md`

Don't load it at runtime. Use the playbook as your reference during implementation:
every number in a rule should trace to a section of the playbook OR to `knowledge/core.yaml`
or `knowledge/set_17.yaml`. If you find a number in the playbook that isn't in the YAML
yet, STOP and add it to YAML first (you may edit `core.yaml` or `set_17.yaml` for this,
documented in your STATE.md entry).

## Fixtures

`tests/fixtures/rule_scenarios.yaml`:

```yaml
# One entry per rule. positive = should fire. negative = should not fire.
rules:
  - rule_id: ROLL_EV_NEGATIVE
    positive:
      state:
        stage: "4-2"
        gold: 8
        hp: 70
        level: 7
        streak: 0
        set_id: "17"
        board:
          - {champion: "Jinx", star: 1, items: []}
        bench: []
        shop: []
        active_traits: []
        augments: []
      pool:
        Jinx: {k: 2, r_t: 60}
    negative:
      state:
        stage: "4-2"
        gold: 50
        hp: 70
        level: 8
        ...
      pool:
        Jinx: {k: 10, r_t: 120}

  - rule_id: HP_URGENT
    positive:
      state: {... hp: 20 ...}
    negative:
      state: {... hp: 60 ...}

  # ...one entry per rule
```

## Acceptance tests

```python
import pytest
import yaml
from pathlib import Path
from rules import evaluate
from schemas import GameState
import knowledge, pool, econ

FIXTURES = yaml.safe_load(Path("tests/fixtures/rule_scenarios.yaml").read_text())

@pytest.mark.parametrize("entry", FIXTURES["rules"])
def test_rule_positive_fires(entry):
    state = GameState(**entry["positive"]["state"])
    pt = _mock_pool_tracker(entry["positive"].get("pool", {}))
    fires = evaluate(state, econ, pt, knowledge)
    assert any(f.rule_id == entry["rule_id"] for f in fires), \
        f"{entry['rule_id']} should fire but did not"

@pytest.mark.parametrize("entry", FIXTURES["rules"])
def test_rule_negative_silent(entry):
    if "negative" not in entry: pytest.skip("no negative fixture")
    state = GameState(**entry["negative"]["state"])
    pt = _mock_pool_tracker(entry["negative"].get("pool", {}))
    fires = evaluate(state, econ, pt, knowledge)
    assert not any(f.rule_id == entry["rule_id"] for f in fires), \
        f"{entry['rule_id']} fired when it shouldn't"

def test_total_rule_count():
    """Smoke: we have at least 39 rules registered (ROLL_CONTESTED_BAIL removed in 3.5a)."""
    from rules import ALL_RULES
    assert len(ALL_RULES) >= 39

def test_no_rule_crashes_on_empty_state():
    state = GameState(stage="1-1", gold=0, hp=100, level=1, set_id="17")
    pt = _mock_pool_tracker({})
    fires = evaluate(state, econ, pt, knowledge)  # should not raise
```

## STATE.md entry

```
## Phase 3 — DONE YYYY-MM-DD
- added: 30 rules in rules.py (now 40 total)
- added: tests/fixtures/rule_scenarios.yaml with 40 positive + 35 negative scenarios
- tests: 40/40 positive fires, 35/35 negative silent
- notes: rules using a "primary_target" heuristic; Phase 4 will replace with comp_planner feed
```

## Anti-patterns to avoid

- Do not write rules that need access to opponents' HP or future state. Rules are
  evaluated on one snapshot.
- Do not add a severity > 1.0 "super-critical" tier. Severity is [0.1, 1.0].
- Do not nest econ/pool imports inside rule functions — import once at module top.
  (Exception: `knowledge` can be lazy-loaded via the module passed in.)
- Do not make rules mutate the pool_tracker or state. Rules are pure readers.
