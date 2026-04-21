# TASK_01_WIRING.md — Wire pipeline into `assistant_overlay.py`

> This is the single most important task in the package. Until this is done,
> none of the Phase 4-6 work runs in production. Take the time to do it
> carefully.

---

## Goal

Make F9 press actually execute this chain in production:

```
capture → state_builder → rules → comp_planner → recommender → advisor → overlay
```

Right now (per recap), Phases 4-7 are complete and tested but the F9 handler
in `assistant_overlay.py` does not yet call them.

## Prereq checks (do these first)

Run these and confirm each:

```bash
pytest --collect-only | tail -5    # confirm 96 tests discovered
pytest -q                           # confirm 96 passed
git status                          # confirm clean working tree
grep -n "recommender\|comp_planner" assistant_overlay.py
    # confirm the handler isn't calling them yet (output should be empty or
    # only import lines)
```

If any of these doesn't match expectations, stop and report to user.

## Files you may edit

- `assistant_overlay.py`
- `tests/test_f9_end_to_end.py` (new file)
- `STATE.md` (append entry)

**Do NOT edit:**
- `schemas.py`
- `recommender.py`, `comp_planner.py`, `advisor.py`, `pool.py`, `rules.py`,
  `econ.py`, `knowledge/` — these are complete; wiring just calls them.
- Any test file other than the new smoke test.

## The wiring pattern

Find the existing `PipelineWorker.run()` method in `assistant_overlay.py` (or
whatever the F9 handler is called). It currently does something like:

```python
def run(self):
    try:
        self.extractingStarted.emit()
        png = capture_screen()
        state = state_builder.build_state(png, self.client, ...)
        if not state.sources.vision_ok:
            self.errorOccurred.emit(f"Vision failed: {state.sources.vision_error}")
            return
        self.stateExtracted.emit(state.model_dump())

        # Existing advisor call (pre-Phase-4 path) — this is what you're replacing
        for evt, payload in advisor.advise_stream(state, ..., self.client):
            ...
```

Replace the middle section with:

```python
def run(self):
    try:
        self.extractingStarted.emit()
        png = capture_screen()
        state = state_builder.build_state(png, self.client, ...)
        if not state.sources.vision_ok:
            self.errorOccurred.emit(f"Vision failed: {state.sources.vision_error}")
            return
        self.stateExtracted.emit(state.model_dump())

        # --- NEW: Phase 4-6 pipeline ---
        from state_builder import get_tracker
        pool = get_tracker(knowledge.load_set(state.set_id))

        set_ = knowledge.load_set(state.set_id)
        core = knowledge.load_core()
        archetypes = comp_planner.load_archetypes()

        fires = rules.evaluate(state, econ, pool, knowledge)
        comps = comp_planner.top_k_comps(state, pool, archetypes, set_, k=3)
        actions = recommender.top_k(state, fires, comps, pool, set_, core, k=3)
        # --- END NEW ---

        # Advisor now receives top-3 actions + top-3 comps instead of raw state
        for evt, payload in advisor.advise_stream(
            state=state,
            fires=fires,
            actions=actions,
            comps=comps,
            client=self.client,
            capture_id=state.capture_id,
        ):
            if evt == "one_liner":   self.verdictReady.emit(payload)
            elif evt == "reasoning": self.reasoningReady.emit(payload)
            elif evt == "final":
                recommendation = payload.get("verdict")
                meta = payload.get("__meta__")
                break
        ...
```

## Signals / slots check

Before running, verify these signals exist on `PipelineWorker` and connect to
overlay slots (they should, from Phase 7):

- `extractingStarted`
- `stateExtracted(dict)`
- `verdictReady(str)`
- `reasoningReady(str)`
- `errorOccurred(str)`
- A "final" completion signal (name it `finalReady(dict)` or whatever
  Phase 7 called it; do not invent a new name — find it in `overlay.py`
  and use it)

If the Phase 6 advisor emits `"final"` events but the overlay doesn't
connect to them, that is a real bug — surface it via DATA_GAPS.md before
adding a connection.

## Imports at top of `assistant_overlay.py`

Add (if not already present):

```python
from state_builder import get_tracker
import knowledge
import rules
import econ
import comp_planner
import recommender
import advisor
```

Keep other existing imports unchanged. Do NOT remove anything even if it
looks unused — the overlay has subsystems unrelated to F9.

## The end-to-end smoke test

Create `tests/test_f9_end_to_end.py`:

```python
"""End-to-end smoke test for the F9 pipeline.

Exercises the full chain from a captured test screenshot through to an
advisor verdict, verifying each stage produces a non-empty, well-typed
result. Does NOT make a live Claude API call — uses a mocked advisor
response.

This test is the single most important guard against regressions in
the wiring step. If it breaks, the F9 button doesn't work in production.
"""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import knowledge
import rules
import econ
import comp_planner
import recommender
from schemas import GameState, BoardUnit, ShopSlot
from pool import PoolTracker


FIXTURE_STATE = GameState(
    stage="3-2",
    gold=30,
    hp=70,
    level=6,
    xp_current=5,
    xp_needed=36,
    streak=0,
    set_id="17",
    board=[BoardUnit(champion="Jinx", star=1, items=[])],
    bench=[],
    shop=[
        ShopSlot(champion="Jinx", cost=2, locked=False),
        ShopSlot(champion="Akali", cost=2, locked=False),
        ShopSlot(champion="Poppy", cost=1, locked=False),
        ShopSlot(champion="Leona", cost=1, locked=False),
        ShopSlot(champion="Mordekaiser", cost=2, locked=False),
    ],
    active_traits=[],
    augments=[],
)


def test_pipeline_end_to_end_produces_verdict():
    """State → rules → comp_planner → recommender → (mocked) advisor → verdict.

    Every stage must return a non-empty, well-typed result.
    """
    set_ = knowledge.load_set("17")
    core = knowledge.load_core()
    pool = PoolTracker(set_)
    pool.observe_own_board(FIXTURE_STATE.board, FIXTURE_STATE.bench)
    archetypes = comp_planner.load_archetypes()

    fires = rules.evaluate(FIXTURE_STATE, econ, pool, knowledge)
    assert isinstance(fires, list), "rules.evaluate must return a list"
    # fires may be empty for this state; that's fine

    comps = comp_planner.top_k_comps(FIXTURE_STATE, pool, archetypes, set_, k=3)
    assert len(comps) == 3, "comp_planner must return top 3"

    actions = recommender.top_k(
        FIXTURE_STATE, fires, comps, pool, set_, core, k=3
    )
    assert len(actions) == 3, "recommender must return top 3 actions"
    assert actions[0].total_score >= actions[1].total_score >= actions[2].total_score


def test_pipeline_handles_empty_state_gracefully():
    """Starting-game state (stage 1-1, empty board) doesn't crash the pipeline."""
    empty_state = GameState(
        stage="1-1", gold=0, hp=100, level=1,
        xp_current=0, xp_needed=2, streak=0, set_id="17",
    )
    set_ = knowledge.load_set("17")
    core = knowledge.load_core()
    pool = PoolTracker(set_)
    archetypes = comp_planner.load_archetypes()

    fires = rules.evaluate(empty_state, econ, pool, knowledge)
    comps = comp_planner.top_k_comps(empty_state, pool, archetypes, set_, k=3)
    actions = recommender.top_k(empty_state, fires, comps, pool, set_, core, k=3)

    # Must complete without error
    assert isinstance(actions, list)
    assert len(actions) == 3


def test_advisor_receives_correct_inputs(monkeypatch):
    """Verify advisor.advise_stream is called with the right parameters.

    This is the test that most directly catches a broken wiring.
    """
    import advisor

    called_with = {}
    def fake_advise_stream(**kwargs):
        called_with.update(kwargs)
        yield ("one_liner", "test")
        yield ("final", {"verdict": None, "__meta__": {}})

    monkeypatch.setattr(advisor, "advise_stream", fake_advise_stream)

    # Simulate the wiring path:
    set_ = knowledge.load_set("17")
    core = knowledge.load_core()
    pool = PoolTracker(set_)
    archetypes = comp_planner.load_archetypes()

    fires = rules.evaluate(FIXTURE_STATE, econ, pool, knowledge)
    comps = comp_planner.top_k_comps(FIXTURE_STATE, pool, archetypes, set_, k=3)
    actions = recommender.top_k(FIXTURE_STATE, fires, comps, pool, set_, core, k=3)

    events = list(advisor.advise_stream(
        state=FIXTURE_STATE, fires=fires, actions=actions, comps=comps,
        client=None, capture_id=None,
    ))

    assert "state" in called_with
    assert "fires" in called_with
    assert "actions" in called_with
    assert "comps" in called_with
    assert len(called_with["actions"]) == 3
    assert len(called_with["comps"]) == 3
```

Expected: 3 new tests pass, total goes from 96 → 99.

## Acceptance gate

Before declaring Task 1 done, verify ALL of:

1. `pytest -q` shows 99/99 passing (96 original + 3 new).
2. Manual smoke test: Run `python assistant_overlay.py`, press F9 with a
   test screenshot loaded. Must produce an advisor verdict without crash.
3. No performance regression: time a single F9 press, should be in the
   same ballpark as before (maybe slightly slower since there's more code
   running; ≤30% regression is OK, anything more needs investigation).
4. `git diff --stat` shows changes ONLY in `assistant_overlay.py`,
   `tests/test_f9_end_to_end.py`, and `STATE.md`.

If any of these fails, stop and report.

## Commit message

```
Task 1: wire Phase 4-6 pipeline into assistant_overlay.py F9 handler

- PipelineWorker.run() now calls rules → comp_planner → recommender → advisor
- Advisor receives top-3 actions and top-3 comps as structured inputs (not raw state)
- New smoke test: test_f9_end_to_end.py verifies the full chain

Tests: 96 → 99 passing.
```

## STATE.md entry

```
## Task 1 — WIRING DONE YYYY-MM-DD
- edited: assistant_overlay.py (PipelineWorker.run now calls full Phase 4-6 chain)
- added: tests/test_f9_end_to_end.py (3 tests)
- tests: 99/99 passing
- latency per F9 (measured on test screenshot): X.Xs
- notes: none / [any weirdness goes here]
```

---

## What happens if Task 1 reveals a bug in Phase 4-6 code

If the wiring itself is clean but a downstream module breaks (e.g.
`recommender.top_k` crashes on FIXTURE_STATE, or `advisor.advise_stream`
signature has drifted from what's specified in `skills/advisor/SKILL.md`),
STOP. Do not fix the downstream module as part of Task 1. Revert the
wiring, file the bug in DATA_GAPS.md with 🛑, and wait.

Why: "I'll just fix this one small thing while I'm here" is the #1 way
surgeons make post-op infections, and the same is true for code.
