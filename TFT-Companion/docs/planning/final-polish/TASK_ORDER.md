# TASK_ORDER.md — The 9 tasks

> Execute in this order. Do not skip ahead. Do not batch. Each task has a
> prerequisite ("what must be true before starting"), a success gate
> ("what must be true before committing"), and a rollback rule ("if the
> gate fails, revert and stop").

---

## Task 1 — Wire the pipeline into `assistant_overlay.py`

**Prereq:** 96 tests green, Phases 0-7 complete per STATE.md.
**Gate:** F9 press in dev (with a captured test screenshot) flows end-to-end
through state_builder → rules → comp_planner → recommender → advisor →
overlay without error. All 96 existing tests still pass. New smoke test
`test_f9_end_to_end` passes.
**Rollback rule:** If F9 errors or test count drops, revert the wiring commit
and report.
**Full detail:** `TASK_01_WIRING.md`
**Estimated time:** 4-6 hours.

---

## Task 2 — Add state validation layer before scorer

**Prereq:** Task 1 complete and green.
**Gate:** Every field on `GameState` that reaches the scorer has passed
bounds + cross-field sanity checks. On validation failure, scorer is
skipped, UI shows "verifying state…", log captures the bad state. All
prior tests still pass. New tests `test_state_validation.py` all pass.
**Rollback rule:** If any existing test breaks, revert.
**Full detail:** `TASK_02_VALIDATION.md`
**Estimated time:** 4-6 hours.

---

## Task 3 — Deterministic template-string fallback when LLM fails

**Prereq:** Task 2 complete and green.
**Gate:** If the advisor LLM call times out (2.5s) or errors, the overlay
shows a deterministic verdict string assembled from the same state the
LLM would have seen. No hang, no crash, no blank UI. New test
`test_advisor_timeout_fallback.py` passes.
**Rollback rule:** If advisor success path gets slower or breaks, revert.
**Full detail:** `TASK_03_TEMPLATE_FALLBACK.md`
**Estimated time:** 3-4 hours.

---

## Task 4 — Pin Community Dragon URLs to patch version

**Prereq:** Task 3 complete and green.
**Gate:** All CDragon URL references use `/17.1/` (patch-pinned), not
`/latest/`. Startup sanity check loads Set 17 data and verifies the
active apiName prefix is actually `TFT17_` (if it isn't, halt with a
clear error message, don't silently proceed).
**Rollback rule:** If startup fails on the sanity check, figure out why
(likely: real prefix differs from expected) before continuing. Do NOT
remove the sanity check to make it "pass."
**Full detail:** `TASK_04_CDRAGON_PIN.md`
**Estimated time:** 1-2 hours.

---

## Task 5 — Swap `mss` for `DXcam` in screen capture

**Prereq:** Task 4 complete and green.
**Gate:** F9 latency on screen capture portion drops measurably (expect
~13ms → ~4ms). All vision/OCR/template extraction still works. All
existing tests still pass.
**Rollback rule:** If DXcam fails on the target Windows version, or if
any perception test breaks, revert.
**Full detail:** `TASK_05_DXCAM.md`
**Estimated time:** 2-3 hours.

---

## Task 6 — Add PaddleOCR as primary OCR

**Prereq:** Task 5 complete and green.
**Gate:** PaddleOCR handles gold/HP/level/XP/stage/round/streak reads
with ≥98% accuracy on the existing labeled screenshot corpus.
pytesseract remains as fallback (if PaddleOCR returns empty or
low-confidence). Total OCR latency per F9 stays under 150ms.
**Rollback rule:** If PaddleOCR accuracy is worse than pytesseract on the
corpus (unlikely but possible), revert and keep pytesseract as primary.
**Full detail:** `TASK_06_PADDLEOCR.md`
**Estimated time:** 4-6 hours.

---

## Task 7 — Dynamic `TFT##_` prefix detection

**Prereq:** Task 6 complete and green.
**Gate:** A grep for hardcoded `"TFT17_"` in .py files returns zero
matches outside of test fixtures or historical STATE.md. The active
prefix is detected at knowledge-load time from the apiName list.
**Rollback rule:** If the detection logic produces a different prefix
than `TFT17_` for current data, something is wrong — report to user
before continuing.
**Full detail:** `TASK_07_DYNAMIC_PREFIX.md`
**Estimated time:** 1-2 hours.

---

## Task 8 — Add Sentry + loguru observability

**Prereq:** Task 7 complete and green.
**Gate:** All uncaught exceptions go to Sentry (free tier, rate-limited
to ~170 events/day). loguru handles structured logging with rotation.
Existing print/logging statements migrated. Debug logs include enough
context to reproduce perception failures (screenshot hash, extracted
state, confidence).
**Rollback rule:** If Sentry spam exceeds rate limit in dev, tighten
filter rules before proceeding, don't disable entirely.
**Full detail:** `TASK_08_SENTRY.md`
**Estimated time:** 3-4 hours.

---

## Task 9 — Property-based tests for econ invariants

**Prereq:** Task 8 complete and green.
**Gate:** `hypothesis` is added to test deps. New file
`tests/test_econ_properties.py` has property tests for monotonicity,
bounds, and algebraic invariants on econ and pool math. Total test
count goes up by 10-15. All tests pass.
**Rollback rule:** If any property test finds an actual bug in existing
math — stop, report to user, do NOT auto-fix. The bug might be in
their intuition, not the code.
**Full detail:** `TASK_09_HYPOTHESIS.md`
**Estimated time:** 3-4 hours.

---

## Total estimated effort

~26-37 hours of focused work across 9 tasks. Two working weeks at a
realistic personal-project pace. Do not attempt to compress this.

## Big-picture sanity check before starting

After Task 1 (wiring), the system is running live and you have a real
baseline. After Task 2-3 (validation + fallback), reliability hardening
is in place. After Task 4-7 (CDragon pin + DXcam + PaddleOCR + prefix),
the perception stack is modernized. After Task 8-9 (Sentry + Hypothesis),
the observability and test layers support future changes safely.

Each task ships ONE kind of improvement. You do not need to understand
the whole sequence to execute one task correctly. Just execute the task
in front of you using its TASK_##_*.md file as the authority.
