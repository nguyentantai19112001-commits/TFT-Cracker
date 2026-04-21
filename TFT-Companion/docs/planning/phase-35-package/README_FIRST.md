# README_FIRST.md — Phase 3.5 Handoff

> Phase 3 is complete (79 tests passing). Before starting Phase 4, Phase 3.5 is
> inserted. Read files in the order listed below.

## Read in this order

1. **This file** — orientation and high-level decisions
2. `SCOUTING_REMOVAL.md` — **retroactive + forward** removal of opponent-scouting
   code from Phases 0-3 and from skill briefs for Phases 4-7. This is NOT just
   "don't add it going forward" — it's a full rip-out of what's already been built.
3. `PERCEPTION_OVERHAUL.md` — demote Vision, promote templates + OCR
4. `AUGMENT_SYSTEM.md` — new module spec with YAML skeleton + scorer engine
5. `CLAUDE_MD_AMENDMENT.md` — architectural rules to add to CLAUDE.md

## What changed and why

After Phase 3 completion, the user made two architectural decisions that
require both retroactive cleanup and forward changes.

### Decision 1 — Drop opponent scouting from v2 ENTIRELY (retroactive + forward)

The user's rationale: 80% of TFT play is spent on your own board. An accurate,
fast personal comp analyzer is more valuable than a mediocre scouting system.
Scouting may return in v2.5+, not v2.

**This is NOT a "don't add it in future phases" instruction.** Parts of Phases
0-3 were built on the assumption that opponent data would exist. Those parts
are dead code and must be physically removed, not just left dormant.

Dead code that has to be ripped out (known — audit may find more):

- `schemas.OpponentSnapshot` class — never populated in production
- `schemas.GameState.observed_opponents` field — always `[]`
- `pool.PoolTracker.observe_scout()` method + all tests that exercise it
- Any rule in `rules.py` that references pool contest data sourced from
  opponents (CONTESTED_HARD, CONTESTED_SOFT, ROLL_CONTESTED_BAIL, possibly more)
- Any fixture in `tests/fixtures/rule_scenarios.yaml` that constructs mock
  `observed_opponents` data
- Any reference to scouting in the skill briefs for Phases 4-7 (forward cleanup)

Why ripping it out (instead of leaving dormant) matters:

- Dead fields on `GameState` invite silent bugs — future code may call
  `state.observed_opponents[0]` and crash on empty list
- Tests that pass on fake scout data give a false sense of coverage
- Rule IDs that reference contested-pool logic will mislead the advisor when
  they never fire

**Action for Claude Code:** `SCOUTING_REMOVAL.md` is a full checklist across
every file touched in Phases 0-3. Execute it completely before starting 3.5b.
All 79 existing tests must still pass after removal (with reduced count —
scouting tests are deleted, not skipped).

### Decision 2 — Perception architecture correction

The original architecture defaulted to Claude Vision for extraction. That's
backwards for a live coach. Vision is flexible but slow (13-16s per F9) and
probabilistic. The correct hierarchy for a live tool:

- **OCR** for fixed-position numbers: gold, HP, level, XP, stage, round, streak
- **Template matching** for sprites: shop units, board units, star crowns,
  items, augment icons
- **Vision** only for: novel-set recognition fallback, low-confidence
  validation, variable text that can't be templated (augment *descriptions*
  aren't needed — icons are enough)

This demotion applies retroactively too: `vision.py` as it exists today does
too much. Phase 3.5c refactors it.

### What Phase 3.5 does NOT include

- Opponent scouting (removed, not just deferred)
- Positioning recommendations (v3 scope)
- Multi-set support (Set 17 only)
- New top-level deps beyond `opencv-python` and `pytesseract` (already in v1)

## The Phase 3.5 sub-phases

| Sub-phase | Deliverable | Days | Ships to user |
|---|---|---|---|
| **3.5a** | **Scouting removal (backward + forward)** | 1-2 | internal cleanup; 79 tests → ~65 tests, all passing |
| 3.5b | Template library generated from Community Dragon | 2-3 | `assets/templates/set_17/` populated |
| 3.5c | Own-board extraction rewrite (templates + OCR; Vision narrowed) | 4-5 | F9 latency 13s → 3-4s, cost drops 30-40% |
| 3.5d | Continuous OCR poll (500ms gold/HP/stage) | 2 | HP-panic alerts without F9 |
| 3.5e | Augment system (YAML + scorer + icon match) | 3-4 | augment pick recommendations at 2-1 / 3-2 / 4-2 |

**Do 3.5a first and do it completely.** Do not start 3.5b until scouting is
fully removed and the test suite is green at its new reduced count. This is
the single most important instruction in this package.

## STEP 0 — state report before touching anything

Before any removal or new build, report to the user:

```
Phase 3 status:
  - rules in rules.py: count
  - tests passing: 79 (confirmed by user)

Scouting-related code surface (audit these files and list what you find):
  - schemas.py → search for: OpponentSnapshot, observed_opponents, observe_scout
  - pool.py → search for: observe_scout, any opponent-derived logic
  - rules.py → list rules that depend on contest-via-scout data
  - tests/test_pool.py → list tests that call observe_scout
  - tests/test_rules.py → list tests using opponent fixtures
  - tests/fixtures/rule_scenarios.yaml → list scenarios with opponent data
  - state_builder.py → check if observed_opponents is written anywhere
  - assistant_overlay.py → check if PipelineWorker touches scout data

Skill briefs (forward cleanup, for reference):
  - skills/pool/SKILL.md → mentions observe_scout throughout
  - skills/rules/SKILL.md → references contest rules
  - skills/comp_planner/SKILL.md → p_reach uses pool contest
  - skills/recommender/SKILL.md → reasoning tags reference contested state
```

Submit this audit to the user. Wait for confirmation that the list is complete
before starting actual removal. If the audit finds anything not mentioned in
`SCOUTING_REMOVAL.md`, add it to that file and report it.

## The communication protocol (unchanged)

Per the existing loop:
- User confirms audit → Claude Code executes removal
- Claude Code commits after each sub-phase, runs tests, updates `STATE.md`
- If anything unexpected is encountered, write to `DATA_GAPS.md` with a 🛑
  flag and wait for user input before improvising
