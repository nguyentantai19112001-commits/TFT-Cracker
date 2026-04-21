# SCOUTING_REMOVAL.md — Phase 3.5a

> **This is a retroactive + forward removal, not a deferral.** Every trace of
> opponent-scouting logic that was built in Phases 0-3 on the assumption
> opponents would be scouted must be deleted. Every SKILL.md for Phases 4-7
> must be edited to remove scouting references.
>
> After this is done, the codebase acts as if opponent scouting was never part
> of the architecture.

---

## Why retroactive matters (read before executing)

Leaving dormant code "for later" creates three concrete problems:

1. **Silent failure modes.** `state.observed_opponents` is a typed empty list.
   Future code may index it and crash. Or worse: a future rule that filters
   empty lists will pass, fire nothing, and look like it's working.

2. **Misleading test coverage.** 12+ tests in `test_pool.py` exercise
   `observe_scout` by calling it with mock data. Those tests passing suggests
   the scouting pipeline works. It doesn't — it just has correct math for
   data that never arrives.

3. **Rule catalog liars.** `CONTESTED_HARD` is in your 40-rule list with a
   severity and action. It will never fire in production because the pool
   state it depends on is always "full pool minus own holdings." A rule that
   can't fire shouldn't exist. The advisor sees the rule catalog, weights its
   prompt around it, and talks about "contest" detection it doesn't have.

All three get fixed by physically deleting the code, not by flagging it TODO.

---

## Required pre-work — STEP 0 audit

**Before deleting anything**, produce the audit requested in `README_FIRST.md`.
Submit it to the user. Wait for greenlight. The list below is my best guess of
what's there, but the actual codebase is what Claude Code has built — there
may be additional surface area.

If the audit finds opponent-scout code or references NOT in the list below,
add them to this file with a comment `# FOUND IN AUDIT`, and include them in
the removal.

---

## Removal checklist

### Part 1 — `schemas.py`

DELETE these definitions entirely:

```python
class OpponentSnapshot(BaseModel):
    ...
```

REMOVE this field from `GameState`:

```python
observed_opponents: list[OpponentSnapshot] = Field(default_factory=list)
```

Any import of `OpponentSnapshot` elsewhere becomes an ImportError — fix those
by deleting the import line.

### Part 2 — `pool.py`

DELETE these methods from `PoolTracker`:

```python
def observe_scout(self, opponent_name: str, board: list[BoardUnit]) -> None:
    ...
```

DELETE the internal state that tracked per-opponent scouts:

```python
self._seen_per_opponent: dict[str, dict[str, int]] = {}
```

KEEP `observe_own_board()` and `belief_for()`. These still work, just against
a smaller information set (own holdings only).

KEEP `PoolTracker` itself — it's still the right API, it just has one fewer
input source.

Update docstring on the class: change "observes scouts and own holdings" to
"observes own holdings only — opponent data is v2.5 scope."

### Part 3 — `rules.py`

REMOVE these rules entirely (from the 30-rule Phase 3 catalog):

- `CONTESTED_HARD`
- `CONTESTED_SOFT`
- `ROLL_CONTESTED_BAIL`

AUDIT every remaining rule for references to `pool_tracker.belief_for(...).k_upper_90`
in a way that assumes opponent data was folded in. The pool tracker still
returns beliefs; those beliefs just have a narrower information source. Most
rules that query pool beliefs are still valid — just less sharp. If a rule's
message string uses the word "contested" or "opponents," rewrite it to reflect
what it actually detects (usually "your bench holdings" or "pool depletion").

Specifically check:
- `ROLL_EV_NEGATIVE` — still valid, uses `econ.analyze_roll` on pool belief
- `COMP_UNREACHABLE` — still valid
- Any rule with `contested` in its message — rewrite

Update `rules.ALL_RULES` count. Likely drops from ~40 to ~37.

### Part 4 — `state_builder.py`

CHECK if `observed_opponents` is written anywhere in the state-build pipeline.
If so, remove the write. If the build constructs an empty list and assigns it,
that line goes. If there's a function like `_parse_opponent_views(...)`, delete
it.

DO NOT remove any vision-prompt changes that were pre-emptively added for
opponent view detection. If such changes exist, note them in the audit and
the user will decide what to do.

### Part 5 — `assistant_overlay.py` / PipelineWorker

CHECK if PipelineWorker does anything with opponent data. If there's a step
that calls `pool.observe_scout` after state build, remove it.

If the overlay has any "opponent panel" UI scaffolding that was added
pre-emptively, surface this in the audit — the user may want to keep the UI
stub for future re-enable, or may want it removed.

### Part 6 — tests/test_pool.py

DELETE these tests (from the Phase 2 test set):

- `test_scout_decrements`
- `test_scout_idempotent`
- `test_scout_upgrade_detected`
- `test_scout_opponent_sells`
- `test_multiple_opponents`
- `test_uncertainty_shrinks_with_scouts`

KEEP tests that exercise `observe_own_board`, `belief_for`, `to_pool_state`,
and `reset`. These still pass and are still meaningful.

Expected test count change in `test_pool.py`: 12 tests → 6 tests.

### Part 7 — tests/test_rules.py + fixtures

DELETE tests for removed rules:
- Tests of `CONTESTED_HARD`, `CONTESTED_SOFT`, `ROLL_CONTESTED_BAIL`

DELETE fixture entries in `tests/fixtures/rule_scenarios.yaml`:
- Any entry with `rule_id: CONTESTED_*` or `ROLL_CONTESTED_BAIL`
- Any scenario under `state:` that includes non-empty `observed_opponents:`
  even for other rules — rewrite those scenarios without the field

Expected test count change in `test_rules.py`: depends on Phase 3's rule count.
Remove ~3-6 tests, keep the rest.

### Part 8 — Forward cleanup in SKILL.md files

These files are instructions for *future* phase sub-agents. They've been
written with scouting baked in. Edit them so the next sub-agent doesn't
re-introduce scouting.

**`skills/comp_planner/SKILL.md` (Phase 4 — next phase):**
- In the `p_reach` formula, the pool state parameter is still fine; it just
  reflects own-holdings only. No formula change needed, but remove any comment
  or description that says "accounts for contested pool state" or similar.
- In the example test `test_contested_lowers_rank`: delete or rewrite without
  scout setup.

**`skills/recommender/SKILL.md` (Phase 5):**
- In `reasoning_tags` list: delete `contested_hard` and `contested_soft` tags.
- Keep `pool_favored` / `pool_unfavored` — these still make sense against
  own-holdings pool state.
- In `_score_pivot_value`: any logic that reads opponent pressure is removed.

**`skills/advisor/SKILL.md` (Phase 6):**
- Remove any mention of scout data from the system prompt template.
- Remove `observed_opponents` from the example state payloads.
- If `comp_details` tool or `econ_p_hit` tool had any opponent parameter,
  remove it.

**`skills/pool/SKILL.md` (already partly covered):**
- The whole `observe_scout` section goes.
- The `uncertainty` model in `belief_for` (which used "scouted_opponent_count")
  changes: now uncertainty is flat-small or scales with how many of our
  own buys we've made. Simplify.

**`skills/rules/SKILL.md`:**
- Remove the 3 contest rules from the rule catalog table.
- Update the count from 30 to 27 new rules added in Phase 3.

---

## Part 9 — `STATE.md` update

Append an entry AFTER Phase 3's completion entry:

```
## Phase 3.5a — SCOUTING REMOVAL 2026-04-21
- retroactive removal of opponent-scouting scaffolding from Phases 0-3
- schemas.py: removed OpponentSnapshot, GameState.observed_opponents
- pool.py: removed observe_scout() method + _seen_per_opponent state
- rules.py: removed CONTESTED_HARD, CONTESTED_SOFT, ROLL_CONTESTED_BAIL (rule
  count: 40 → 37)
- tests deleted: N tests in test_pool, M tests in test_rules, K fixture
  scenarios; new total: 79 → 79-(N+M+K) passing
- skill briefs for Phases 4-7 edited to remove scouting references
- scope change: v2 is now personal-board-only analyzer. Opponent scouting
  is deferred to v2.5, not planned inside v2.
- reason: user decision, 2026-04-21 session. Latency + accuracy tradeoff
  doesn't justify scouting complexity inside v2 scope.
```

---

## Part 10 — Acceptance

Before declaring 3.5a done:

1. All remaining tests pass (expected: ~65-70 depending on fixture count).
2. `grep -r "OpponentSnapshot\|observed_opponents\|observe_scout\|CONTESTED_HARD\|CONTESTED_SOFT\|ROLL_CONTESTED_BAIL" .`
   returns zero matches outside of `STATE.md` (where historical reference is
   fine).
3. The project runs end-to-end: F9 press → state → rules → advisor → overlay,
   with no errors about missing fields.
4. Run the existing smoke test: `pytest tests/test_smoke.py -v`. Must pass.

If any of these fail, do not proceed to 3.5b. Report to user.

---

## What this enables for the rest of 3.5

Once scouting is out:
- **3.5b** (template library) has no opponent-view scaling work. Only
  own-board templates. Simpler scope.
- **3.5c** (extraction rewrite) has a smaller surface to refactor — no
  opponent-view vision prompt.
- **3.5e** (augment system) is unaffected by scouting either way.

Estimated time savings across 3.5b-3.5e: ~3 days not having to support a
parallel opponent pipeline.
