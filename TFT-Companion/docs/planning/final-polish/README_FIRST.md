# README_FIRST.md — Final Polish Package

> **READ COMPLETELY BEFORE TOUCHING ANY CODE.** This package is different from
> every previous one. You are modifying working, tested code (96 tests green)
> rather than building new modules. The failure mode is "breaks something that
> works," not "builds something wrong." Optimize for safety over speed.

---

## Context for this package

All 7 phases of Augie v2 are complete. The test suite is green at 96 tests.
The last remaining structural task is wiring the new pipeline (recommender +
comp_planner + advisor) into `assistant_overlay.py` so F9 actually runs
the Phase 4-6 code path in production, not just in tests.

After a deep architectural review by the user's pipeline designer, 8 specific
optimizations have been identified. This package applies them in a safe,
staged, test-gated sequence.

## The ground rules

1. **One task at a time.** This package has 9 tasks (the wiring task + 8
   optimizations). Complete each one fully before starting the next. Do not
   batch them. Do not parallelize them. Do not "do them all at once because
   they're related."
2. **Tests must be green before and after each task.** Run the full suite
   before starting a task; run it after. If any test fails after a task
   that didn't touch that area, stop and investigate. Do not paper over.
3. **Each task has explicit rollback criteria.** If the task's own acceptance
   criteria fail, revert. Do not debug inline. Revert, report to user via
   DATA_GAPS.md, wait.
4. **Commit after each green task.** One commit = one task. Makes bisect
   trivial if something shows up in playtesting later.
5. **STATE.md gets an entry per task.** Same format as prior phases.
6. **If a task says "skip if X is true," respect the skip condition.** The
   user has already thought about when each optimization is and isn't worth
   applying. Don't override by doing more than asked.

## Read in this order

1. **This file** — ground rules and task list
2. `TASK_ORDER.md` — the 9 tasks with prereqs, rollback criteria, and
   acceptance gates
3. `TASK_01_WIRING.md` — wire the pipeline into `assistant_overlay.py`
   (THIS GOES FIRST — nothing else works until this does)
4. `TASK_02_VALIDATION.md` — add state validation before scorer
5. `TASK_03_TEMPLATE_FALLBACK.md` — deterministic fallback when LLM times out
6. `TASK_04_CDRAGON_PIN.md` — pin Community Dragon URLs to `/17.1/`
7. `TASK_05_DXCAM.md` — swap `mss` for `DXcam` in screen capture
8. `TASK_06_PADDLEOCR.md` — add PaddleOCR as primary OCR, keep pytesseract
   as fallback
9. `TASK_07_DYNAMIC_PREFIX.md` — detect the active `TFT##_` prefix
   dynamically instead of hardcoding
10. `TASK_08_SENTRY.md` — add Sentry + loguru observability
11. `TASK_09_HYPOTHESIS.md` — add property-based tests for econ invariants
12. `EXPLICITLY_DEFERRED.md` — things the user decided NOT to do now, and
    why. Do not revisit these in this session.

## What this package does NOT include

The user's architecture reviewer identified these as premature or
authorship-work-disguised-as-engineering. They are NOT in scope:

- Switching narrator from Claude Haiku to Groq + Llama 3.3 70B
- Expanding archetypes from 12 to 18-22
- Custom digit classifier training
- Confidence-escalation staircase with Lowe's ratio test
- phash + colorhash replacing matchTemplate
- DPI/resolution calibration flow
- Overwolf migration

Each of these has a paragraph in `EXPLICITLY_DEFERRED.md` explaining why.
If you find yourself about to work on one of these, stop.

## Starting state you should see

Before beginning Task 1, verify:
- Test suite: `pytest` shows 96/96 passing
- `assistant_overlay.py` exists but does NOT yet call recommender, comp_planner,
  or advisor from Phases 4-6 in its F9 handler (it still uses the pre-Phase-4
  path or has a stub)
- `STATE.md` shows Phases 0-7 all complete
- No uncommitted changes in the working tree

If any of these is wrong, STOP and report to user. Do not proceed with a
dirty or unclear starting state.

## Communication protocol (unchanged)

- Unexpected finding → write to `DATA_GAPS.md` with 🛑, wait for user
- Task acceptance passes → commit, update `STATE.md`, start next task
- Task acceptance fails → revert, report to user via DATA_GAPS.md, wait
- Mid-task, question about scope → do not improvise; stop, report, wait
