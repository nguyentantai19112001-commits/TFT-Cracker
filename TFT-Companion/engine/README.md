# Augie v2 — Pipeline Handoff Package

This package is the complete spec for the Augie v2 build. Drop it into your existing
`TFT-Companion/` repo root, then feed to Claude Code.

## What this is

A tight, contract-first spec for turning the existing Augie v1 (vision + 10 rules +
Sonnet advisor) into Augie v2 (vision + knowledge pack + econ math + pool tracker + 40
rules + comp planner + weighted recommender + Haiku narrator). Scope is locked at
**"beat 90% of players"** — no ML, no sim, no search.

## How to use this with Claude Code

### Step 1 — drop into your repo

```bash
# from TFT-Companion/ root
unzip augie-v2-pipeline.zip -d .
# creates ARCHITECTURE.md, CLAUDE.md, BUILD_ORDER.md, schemas.py,
# knowledge/, skills/, STATE.md, tests/test_smoke.py
```

### Step 2 — start Phase 0 in Claude Code

Open Claude Code in the repo root. Its first session reads these files, in order:

1. `CLAUDE.md` — meta-rules (hard constraints, scope ceiling, protocol)
2. `ARCHITECTURE.md` — the whole pipeline, one pass
3. `BUILD_ORDER.md` — what phase we're on
4. `skills/knowledge/SKILL.md` — the first module's brief
5. `schemas.py` — the frozen contract

Tell it: "Work on Phase 0 from `skills/knowledge/SKILL.md`. Follow the protocol in
CLAUDE.md. Stop when the acceptance tests pass and STATE.md is updated."

When Phase 0 is green, start a new Claude Code session for Phase 1 with
`skills/econ/SKILL.md`. Repeat for each phase.

### Why separate sessions per phase

So sub-agents don't load context from other modules they shouldn't touch. This is the
#1 mechanism keeping sub-agents from drifting into each other's code. Each SKILL.md has
an explicit **FILES YOU MAY EDIT** allowlist.

## The eight phases (summary — details in BUILD_ORDER.md)

| Phase | Module | Days | What ships |
|---|---|---|---|
| 0 | schemas + knowledge | 2-3 | internal refactor (dataclass → Pydantic, YAML loader) |
| 1 | econ.py | 3-4 | advisor cites exact P(hit) numbers |
| 2 | pool.py | 2-3 | contest warnings with real k/R_T numbers |
| 3 | rules.py expansion (10→40) | 7 | 5 failure modes caught with numbers |
| 4 | comp_planner.py | 7 | long-term comp target in overlay |
| 5 | recommender.py | 7 | top-3 scored actions |
| 6 | advisor.py refactor | 3 | Haiku + tool-use; cost drops 30% |
| 7 | overlay long-term panel | 2 | two-panel UI |

Total: ~5-6 weeks of focused work. Each phase ships something useful.

## The coordination story ("make sure you guys talk to each other")

Five mechanisms prevent sub-agent miscommunication:

1. **`schemas.py` is frozen.** Every module imports types only from here. No module
   redefines a shared type. No ad-hoc dicts crossing module boundaries. If a module
   needs a new field, it stops and asks — it doesn't invent.

2. **Per-module `FILES YOU MAY EDIT` allowlist.** Each SKILL.md names exactly which
   files the sub-agent may touch. Everything else is read-only. An econ sub-agent that
   silently edits rules.py would be out-of-contract.

3. **Acceptance tests written in the SKILL.md.** Not "vaguely try this"; the exact
   tests that must pass are spelled out. The sub-agent writes them first, makes them
   green, then stops.

4. **Append-only `STATE.md`.** After each phase, the sub-agent logs what changed, what
   tests passed, and any notes. Future sub-agents (and future-you) read STATE.md to
   know what already exists.

5. **Integration passes are separate sessions.** Module-build sessions don't touch
   `assistant_overlay.py`. Integration sessions wire the new module in, run the smoke
   test, log results. This keeps the build/integration seams clean.

## File map

```
augie-v2-pipeline/
├── README.md                    ← this file
├── CLAUDE.md                    ← meta-rules (sub-agents read every session)
├── ARCHITECTURE.md              ← the whole pipeline
├── BUILD_ORDER.md               ← phased sequence with acceptance criteria
├── STATE.md                     ← append-only build log (starts empty)
├── schemas.py                   ← the frozen contract (24 Pydantic types)
├── knowledge/
│   ├── core.yaml                ← set-invariant numbers (XP, interest, streaks)
│   └── set_17.yaml              ← Set 17 shop odds + pool sizes
├── skills/
│   ├── knowledge/SKILL.md       ← Phase 0 brief
│   ├── econ/SKILL.md            ← Phase 1 brief
│   ├── pool/SKILL.md            ← Phase 2 brief
│   ├── rules/SKILL.md           ← Phase 3 brief
│   ├── comp_planner/SKILL.md    ← Phase 4 brief
│   ├── recommender/SKILL.md     ← Phase 5 brief
│   └── advisor/SKILL.md         ← Phase 6 brief
└── tests/
    └── test_smoke.py            ← end-to-end smoke test stub
```

## Hard guardrails (copied from CLAUDE.md so you see them before unzipping)

- `schemas.py` frozen without explicit approval
- No new top-level deps without approval (current: anthropic, mss, keyboard, PyQt6,
  opencv, pytesseract, numpy, pydantic, pyyaml)
- `vision.py`, `overlay.py`, `db.py`, `session.py`, `ocr_helpers.py` — don't rebuild
- No value net, no combat sim, no MCTS, no Overwolf, no positioning, no Match-V1
  crawler (these are v3 scope)

## If you want to stop at a phase

Every phase is a shippable checkpoint. If Phase 3 feels like enough ("40 rules catching
the 5 mistakes is all I need"), you can stop there and skip comp_planner + recommender.
The advisor still works because v1's decider logic is preserved until Phase 6 replaces
it. Don't skip Phase 0 — everything else depends on it.

## When stuff breaks

The two most likely failure modes, pre-handled:

- **A sub-agent wants to add a field to `schemas.py`.** Answer: stop, surface the
  request, wait for user. Do not silently edit.
- **Two modules' acceptance tests pass but the integration pass fails.** Answer: that's
  what integration passes exist for. Fix in the integration session (which may touch
  `assistant_overlay.py`), not in the module sessions.

Everything else — read `CLAUDE.md`, read `ARCHITECTURE.md`, read the relevant SKILL.md.
