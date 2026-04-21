# BUILD_ORDER.md — Phased build sequence

> Read ARCHITECTURE.md first. This document is *when* and *how*, not *what*.
> Every phase lists: deliverable, sub-agent brief location, files to edit, acceptance
> tests, integration step, what ships to the user.

**Rule:** you may not start phase N until phase N-1 is green (tests pass, STATE.md updated).

---

## Phase 0 — Shared contract + knowledge pack (2-3 days)

### What this does
Lays down `schemas.py` (the locked contract) and `knowledge/` (all set-specific and
set-invariant numbers as YAML). Migrates existing `state_builder.py` dataclasses to
Pydantic types. Nothing ships to the user.

### Sub-agent brief
`skills/knowledge/SKILL.md`

### Files to create
- `schemas.py` (new)
- `knowledge/__init__.py` (new, the loader)
- `knowledge/core.yaml` (starter content provided in package)
- `knowledge/set_17.yaml` (starter content provided in package)

### Files to edit
- `state_builder.py` — swap `@dataclass GameState` for `schemas.GameState`. Mechanical.
- `rules.py` — change imports only; rule logic stays. (Deeper refactor is Phase 3.)

### Acceptance tests
```python
# tests/test_knowledge.py
def test_shop_odds_sum_to_100():
    k = load_set("17")
    for level in range(1, 12):
        assert abs(sum(k.shop_odds[level]) - 100) < 0.01

def test_pool_sizes_match_research():
    k = load_set("17")
    assert k.pool_sizes[1].copies_per_champ == 22
    assert k.pool_sizes[5].copies_per_champ == 9
    # etc. see fixtures/knowledge_expected.json

def test_xp_curve_cumulative():
    c = load_core()
    assert cumulative_xp_to_reach(c, level=4) == 10
    assert cumulative_xp_to_reach(c, level=7) == 76

def test_streak_bonus():
    c = load_core()
    assert streak_bonus(c, 3) == 1
    assert streak_bonus(c, 5) == 2
    assert streak_bonus(c, 7) == 3
    assert streak_bonus(c, -3) == 1  # loss streak same curve
    assert streak_bonus(c, 2) == 0

def test_state_builder_still_works():
    # integration: existing test_state_builder.py passes unchanged
    ...
```

### What ships to user
Nothing visible. Internal refactor only.

### STATE.md entry template
```
## Phase 0 — DONE yyyy-mm-dd
- schemas.py created, 12 types
- knowledge/ loader + core.yaml + set_17.yaml
- state_builder.py migrated to Pydantic
- tests green: test_knowledge, test_state_builder
- deps added: pydantic>=2, pyyaml
```

---

## Phase 1 — Econ tool (3-4 days)

### What this does
Ports wongkj12's Markov roll calculator to Python. Adds `econ.py` with:
`analyze_roll(...)`, `level_vs_roll(...)`, `interest_projection(...)`. This is the single
biggest math upgrade.

### Sub-agent brief
`skills/econ/SKILL.md`

### Files to create
- `econ.py`
- `tests/test_econ.py`

### Files to edit
None outside the module.

### Acceptance tests
```python
# tests/test_econ.py
def test_analyze_roll_uncontested_4cost_l8():
    # "Rolling 50g at L8 for uncontested Jinx (k=10, R_T=120)"
    result = analyze_roll(
        target="Jinx", level=8, gold=50,
        pool=PoolState(copies_of_target_remaining=10, same_cost_copies_remaining=120, distinct_same_cost=12),
        set_=load_set("17"),
    )
    assert 0.75 < result.p_hit_at_least_2 < 0.85  # tftodds cross-check

def test_contested_drops_p_hit():
    # 3 opponents each holding 2 copies → k=4, R_T=114
    contested = analyze_roll(
        target="Jinx", level=8, gold=50,
        pool=PoolState(4, 114, 12), set_=load_set("17"),
    )
    assert contested.p_hit_at_least_2 < 0.6

def test_zero_copies_returns_zero():
    r = analyze_roll("Jinx", 8, 50, PoolState(0, 100, 12), load_set("17"))
    assert r.p_hit_at_least_1 == 0

def test_methods_agree():
    # markov / hypergeo / iid must agree within 2% for k >= 3
    for method in ["markov", "hypergeo", "iid"]:
        ...

def test_level_vs_roll_favors_level_when_pace_behind():
    state = make_state(stage="4-2", level=6, gold=50, xp_current=30, xp_needed=36)
    d = level_vs_roll(state, target="Jinx", set_=load_set("17"))
    assert d.recommended == "LEVEL"
```

### What ships to user
Advisor can cite exact P(hit) — rules layer starts using `econ.analyze_roll` for the
`ROLL_EV_*` fires. First time the user sees "Jinx: 68% P(2-star) at 40g, L8 uncontested"
in the overlay reasoning.

---

## Phase 2 — Pool tracker (2-3 days)

### What this does
Builds `pool.py` — a point-estimate tracker that maintains `k_effective` and
`R_T_effective` for every champion based on observed scout data, bought/sold units, and
own shop history.

### Sub-agent brief
`skills/pool/SKILL.md`

### Files to create
- `pool.py`
- `tests/test_pool.py`

### Files to edit
- `state_builder.py` — add a `PoolTracker` instance to the module; hook the `observe_*`
  methods into the state-build pipeline.

### Acceptance tests
```python
def test_bought_decrements_pool():
    t = PoolTracker(load_set("17"))
    belief_before = t.belief_for("Jinx")
    t.observe_bought("Jinx")
    assert t.belief_for("Jinx").k_estimate == belief_before.k_estimate - 1

def test_scout_updates_belief():
    t = PoolTracker(load_set("17"))
    before = t.belief_for("Jinx")
    t.observe_scout([BoardUnit(champion="Jinx", star=2, items=[])])  # they have 2 copies
    assert t.belief_for("Jinx").k_estimate == before.k_estimate - 2

def test_idempotent_scout():
    # Scouting the same board twice in a row should not double-count
    ...
```

### What ships to user
New rule fires: `CONTESTED_HARD` when `k_upper_90 < 6`; `CONTESTED_SOFT` at `< 8`.

---

## Phase 3 — Rules expansion 10 → ~40 (1 week)

### What this does
Reads `data/TFT_PLAYBOOK.md` end-to-end and encodes every deterministic heuristic from
sections 1-5 as a rule. Rules call `econ`, `pool`, `knowledge` — no hardcoded numbers.

### Sub-agent brief
`skills/rules/SKILL.md` (includes the full list of 30 new rules to write)

### Files to create
- `tests/test_rules.py` (expand existing)
- `tests/fixtures/rule_scenarios.yaml` (hand-crafted scenarios for each rule)

### Files to edit
- `rules.py` — add new rules, keep the existing `Fire` dataclass contract.

### Acceptance tests
One test per rule. Each rule has a positive fixture (should fire) and a negative fixture
(should not fire). See `skills/rules/SKILL.md` for the full fixture spec.

### What ships to user
Noticeably smarter advisor. The five failure modes get caught end-to-end now, with
specific numbers. Example messages:
- "Over-roll: rolling at L6 with 8g, P(hit Annie) = 11%. Stop, hold for interest."
- "Streak break: you're on -4 loss streak, winning this round costs +2g/round future
  income. If HP > 50, consider throwing."
- "Pace behind: L6 at 4-2, expected L7. Level now unless rolling for a specific 2-cost
  3-star."

---

## Phase 4 — Comp planner (1 week)

### What this does
Hand-authors 12 dominant Set 17 archetypes as YAML. Builds `comp_planner.py` that, given
current state + pool, ranks reachable comps by `P(reach) × expected_power × trait_fit`.

### Sub-agent brief
`skills/comp_planner/SKILL.md`

### Files to create
- `comp_planner.py`
- `knowledge/archetypes/*.yaml` (12 files)
- `tests/test_comp_planner.py`
- `tests/fixtures/comp_scenarios.yaml`

### Files to edit
None outside the module.

### Acceptance tests
```python
def test_top_archetype_on_strong_augment():
    # Given an Anima Squad soul augment, anima_squad should top the ranking
    state = make_state(augments=["Anima Squad Soul"], stage="3-1", level=6)
    top = top_k_comps(state, empty_pool, archetypes, k=3)
    assert top[0].archetype_id == "anima_squad"

def test_contested_lowers_rank():
    state = make_state(level=7, board=[...])
    pool = contested_pool(target="Jinx", k_remaining=3)
    top = top_k_comps(state, pool, archetypes, k=3)
    jinx_comps = [c for c in top if "Jinx" in c.target_units]
    assert all(c.p_reach < 0.4 for c in jinx_comps)

def test_all_archetypes_load():
    archetypes = load_archetypes()
    assert len(archetypes) >= 12
    for a in archetypes:
        assert a.validate() is True
```

### What ships to user
`advisor.py` starts including top-3 comps in its state payload. Overlay reasoning
starts mentioning target comp names ("you're set up for Anima Squad, need 1 more Xayah").

---

## Phase 5 — Recommender (1 week)

### What this does
Builds `recommender.py` — enumerates candidate actions of each of the 7 types, computes
5-dimension scores for each, returns top-3 with reasoning tags.

### Sub-agent brief
`skills/recommender/SKILL.md`

### Files to create
- `recommender.py`
- `tests/test_recommender.py`
- `tests/fixtures/recommender_scenarios.yaml`

### Files to edit
- None outside the module. (Advisor integration is Phase 6.)

### Acceptance tests
```python
def test_hp_urgent_favors_roll():
    state = make_state(hp=25, gold=40, level=7)
    top = top_k(state, ...)
    assert top[0].action_type == "ROLL_TO"

def test_interest_cap_favors_spend():
    state = make_state(hp=70, gold=54, level=6, streak=0)
    top = top_k(state, ...)
    assert top[0].action_type in ("BUY", "LEVEL_UP", "ROLL_TO")  # not HOLD

def test_streak_8_favors_hold():
    state = make_state(hp=80, gold=48, level=6, streak=8)
    top = top_k(state, ...)
    assert top[0].action_type == "HOLD_ECON"
```

### What ships to user
Recommender output visible in overlay as ranked candidate list (debug mode first, then
integrated by Phase 6). User can see "top 3 actions + why each".

---

## Phase 6 — Advisor refactor (3 days)

### What this does
Refactors `advisor.py` from Sonnet-4.6-freeform-JSON to Haiku-4.5-with-tool-use. Advisor
receives top-3 actions + top-3 comps from recommender/planner and picks one + writes
the one-liner.

### Sub-agent brief
`skills/advisor/SKILL.md`

### Files to create
- `tests/test_advisor.py` (expand existing)

### Files to edit
- `advisor.py` (full refactor)
- `assistant_overlay.py` (PipelineWorker — wire recommender + comp_planner in before
  advisor call)

### Acceptance tests
```python
def test_advisor_picks_from_top_k():
    # Advisor output's primary_action must match one of the top-3 candidate actions
    ...

def test_advisor_cites_numbers():
    # one_liner or reasoning must reference at least one number from the tools
    ...

def test_advisor_is_haiku():
    assert MODEL == "claude-haiku-4-5-20251001"

def test_cost_under_0_005():
    # on a fixture scenario, full advisor call costs < $0.005
    ...
```

### What ships to user
Cost drops from ~$0.02 → ~$0.018/call. Latency improves. Advisor output is more
consistent because it's ranking pre-computed options instead of generating from scratch.

---

## Phase 7 — Overlay long-term panel (2 days)

### What this does
Adds a second panel to the overlay: target comp + next 3 buys + P(reach) + projected
placement. Stable across F9 presses (doesn't flicker on every refresh).

### Sub-agent brief
None required — this is straight PyQt work. Refer to `overlay.py` directly.

### Files to edit
- `overlay.py`

### Acceptance tests
Manual (visual).

### What ships to user
User sees both panels — long-term (which comp, which buys) and per-round (what to do
this turn). The tool now *feels* like a coach, not an alert system.

---

## Critical integration checkpoints

After Phase 1: manually F9 through a real game, verify econ numbers show in reasoning.
After Phase 3: check all 40 rules fire on at least one logged capture.
After Phase 5: compare recommender top-1 against your own judgment on 10 replays.
After Phase 7: ship. Play 20 games. Log mistakes the tool missed. Iterate.

## Notes for the sub-agents running each phase

- Load `CLAUDE.md`, `ARCHITECTURE.md`, `schemas.py`, your `skills/<module>/SKILL.md`.
  Do not load other skills.
- When SKILL.md says "see schemas.RollAnalysis", open schemas.py and read that type.
  Don't guess the fields.
- When SKILL.md says "see data/TFT_PLAYBOOK.md section 3", open that file. Don't invent
  numbers.
- Write tests first. Iterate until green. Then update STATE.md. Then stop.

---

## STATE.md format (append-only)

Create `STATE.md` at repo root. After each phase, append:

```
## Phase N — <status> YYYY-MM-DD
- files added: ...
- files edited: ...
- deps added: ...
- tests: <pass/fail count>
- cost per F9 (measured): $X.XXX
- latency per F9 (measured): X.X s
- notes: (anything weird, blockers, future cleanup)
```

Future sub-agents (and future-you) read this to know what's already done.
