# MID_BUILD_INTEGRATION.md — Applying this package mid-build

> **The user confirmed the project is at Phase 3 (rules expansion).** That means
> Phase 0 (schemas + knowledge loader), Phase 1 (econ.py), and Phase 2 (pool.py)
> are presumed complete. This guide replaces the "start at Phase 0" integration
> path with a mid-build migration.
>
> Read `DATA_GAPS_UPDATE.md` for context first.

---

## STEP 0 — Confirm current state before touching anything

Before applying any patch, report back the following so the user knows what state
the project is in. If any assumption below is wrong, **stop and ask** — do not
auto-resolve.

```
Phase 0 — COMPLETE? (knowledge loader, schemas.py)
  - test_knowledge.py passing count:
  - schemas.py field list for SetKnowledge:

Phase 1 — COMPLETE? (econ.py)
  - test_econ.py passing count:
  - analyze_roll test fixtures that use "full pool" values (copies_of_target=10 + same_cost=120, etc.)?
    List them so we know which need updating.

Phase 2 — COMPLETE? (pool.py)
  - test_pool.py passing count:
  - Does PoolTracker init from knowledge.load_set().pool_sizes, OR from game_assets.CHAMPIONS directly?

Phase 3 — IN PROGRESS. What's done so far?
  - New rules added (from the 30-rule catalog) — list rule_ids
  - Rules blocked on data I didn't have — list them
```

Once confirmed, proceed to the applicable steps below. Skip sections marked "only if
phase N not yet started".

---

## STEP 1 — pool_sizes patch (AFFECTS PHASE 1 TESTS — READ CAREFULLY)

### Apply

In `knowledge/set_17.yaml`, replace the `pool_sizes:` block with the version from
`set_17_patches.yaml` PATCH 1. Changed numbers:

| Cost | Old `distinct` | New `distinct` |
|---|---|---|
| 1 | 13 | **14** |
| 4 | 12 | **13** |
| 5 | 8 | **9** (assumes only Zed gated; user may drop to 8 if another 5-cost is gated) |

### What this breaks and how to fix

**In `tests/test_econ.py`**, any test fixture that hard-codes pool state assuming
the old counts becomes wrong. Specifically, search for these patterns:

```python
# OLD — 4-cost full pool under distinct=12
PoolState(copies_of_target_remaining=10, same_cost_copies_remaining=120, distinct_same_cost=12)

# NEW — 4-cost full pool under distinct=13
PoolState(copies_of_target_remaining=10, same_cost_copies_remaining=130, distinct_same_cost=13)
```

```python
# OLD — 1-cost full pool under distinct=13
PoolState(22, 286, 13)

# NEW
PoolState(22, 308, 14)
```

```python
# OLD — 5-cost full pool under distinct=8
PoolState(9, 72, 8)

# NEW
PoolState(9, 81, 9)
```

**Not all tests need changes.** Tests that set contested scenarios with arbitrary
numbers (e.g. `PoolState(4, 114, 12)` meaning "3 opponents each hold 2 Jinx") stay
correct — those numbers model a specific lobby state, not a formula output.

**Expected probability bands** (e.g. "`0.75 < p < 0.90`") should still pass because
the band is wide enough to absorb the 3-8% shift from the distinct change. If any
assertion starts failing, recompute and widen the band rather than narrowing the
expected value.

### Run tests

```bash
pytest tests/test_econ.py -v
```

Record pass/fail in STATE.md. If any new failure appears that isn't a fixture
arithmetic fix, stop and ask.

---

## STEP 2 — champions + traits sections (additive, low risk)

### Apply

Append the `champions:` block (PATCH 2 from `set_17_patches.yaml`) and `traits:`
block (PATCH 3) to `knowledge/set_17.yaml`. Delete the now-obsolete comment
`# champions: []  # <-- populated at runtime from data/set_data.json` if present.

### schemas.py update

Add two fields to `SetKnowledge`:

```python
class SetKnowledge(BaseModel):
    # ... existing fields unchanged ...
    champions: list[dict] = Field(default_factory=list)
    traits: list[dict] = Field(default_factory=list)
```

This is an additive, non-breaking change. Existing code that doesn't read these
fields keeps working. This is the only schema change allowed without a fresh user
approval — it's backfilling data you already had.

### Run tests

```bash
pytest tests/test_knowledge.py -v
pytest tests/test_pool.py -v   # in case PoolTracker cross-references this
```

If `test_pool.py` fails because `PoolTracker` was iterating over the old short
pool and now sees extra champions, that's actually a **bug caught** — the tracker
should accept the full list. Fix the tracker, not the data.

---

## STEP 3 — Fix Phase 3 rule fixtures referencing broken archetype

If any of your new rule tests in `tests/fixtures/rule_scenarios.yaml` or
`tests/test_rules.py` reference:
- archetype `anima_squad`
- trait `Anima Squad`
- units `Xayah` paired with `Rakan` / `Sylas` / `Vayne`

…those are from Set 10, not Set 17. Replace with `dark_star` / `Dark Star` and
the Set 17 Dark Star units (Jhin, Karma, Kai'Sa, Mordekaiser, Cho'Gath,
Lissandra). See `archetype_dark_star.yaml` in this package for the structure.

If Phase 3 rules haven't touched archetype names yet (because comp_planner isn't
built), you can skip this step — just don't introduce anima_squad references in
new rules.

---

## STEP 4 — Fix the Phase 4 skill brief (mechanical, harmless)

Edit `skills/comp_planner/SKILL.md`:
1. Find the "Archetype YAML format" section with the `anima_squad` example.
2. Replace the whole example with the contents of `archetype_dark_star.yaml`.

This file is read by whoever starts Phase 4, which isn't you yet. Fixing now
prevents the next sub-agent from inheriting a bad template. No code runs from
this file.

Also `grep -r "anima_squad\|Anima Squad" skills/` and fix any other references.

---

## STEP 5 — Update STATE.md

Append under the existing "Pre-Phase-0 — KNOWLEDGE AUDIT NOTE" block:

```
## Mid-Phase-3 — DATA_GAPS_UPDATE MERGED 2026-04-21
- project was at Phase 3 when this merge landed (Phases 0-2 complete)
- edited: knowledge/set_17.yaml (pool_sizes distinct fix, +champions, +traits)
- edited: schemas.py (SetKnowledge: +champions, +traits fields)
- edited: skills/comp_planner/SKILL.md (anima_squad → dark_star example)
- tests/test_econ.py: fixtures updated for new pool_sizes distinct values
  - list exact tests touched
- tests re-run: test_knowledge N/N, test_econ N/N, test_pool N/N, test_rules (partial — Phase 3 still in progress)
- still unresolved (need user):
  - Are any 5-costs besides Zed gated at game start? (currently distinct=9)
  - Trait breakpoints for 35 traits (blocks Phase 4 — not blocking current Phase 3)
```

---

## STEP 6 — Resume Phase 3

Continue from wherever you were in the 30-rule catalog. If any rule you've
written or are about to write depends on champion-trait mapping or trait
breakpoints, flag it in `DATA_GAPS.md` as 🛑 needs user, and move to the next
rule. Don't block on data the user hasn't confirmed.

---

## Sanity check script (run before STEP 6)

```bash
python3 -c "
import yaml
with open('knowledge/set_17.yaml') as f: s = yaml.safe_load(f)
assert len(s['mechanic_hooks']['realm_of_the_gods']['gods']) == 9, 'god count'
assert s['pool_sizes'][1]['distinct'] == 14, '1-cost distinct'
assert s['pool_sizes'][4]['distinct'] == 13, '4-cost distinct'
assert s['pool_sizes'][5]['distinct'] == 9, '5-cost distinct'
assert len(s['champions']) == 63, 'champion count'
assert len(s['traits']) >= 35, 'trait count'
for L, odds in s['shop_odds'].items():
    assert sum(odds) == 100, f'L{L} odds sum'
print('OK — YAML sanity passed')
"

pytest tests/test_knowledge.py tests/test_econ.py tests/test_pool.py -v --tb=short
```

If the YAML assertion passes but pytest shows failures that aren't fixture
arithmetic corrections, stop and report to the user via DATA_GAPS.md.

---

## If you've already done more than Phase 3 (Phase 4+)

Treat this as a data correction, not a restart. The `anima_squad` example was a
teaching template; if you hand-wrote 12 real archetypes from current meta reports,
those are fine. Just verify each archetype's champion names appear in the new
`champions:` list and each trait appears in the new `traits:` list. Fix mismatches
in place.
