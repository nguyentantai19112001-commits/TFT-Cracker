# CLAUDE.md — Read this every session

You are working on **Augie v2**, a personal-use live TFT coach that builds on an existing
working project. The existing project is in this repo; the v2 plan is in `ARCHITECTURE.md`.

## Hard rules (non-negotiable)

1. **Read `ARCHITECTURE.md` at the start of every new session.** One pass. It's the map.
2. **Read `BUILD_ORDER.md` to know what phase you're in.** Don't jump phases.
3. **`schemas.py` is frozen.** Do not add, remove, or change any field without the user
   explicitly saying "edit schemas". If a module needs a new field, surface the request
   and wait. This prevents the #1 source of sub-agent drift.
4. **One module at a time.** When working from `skills/<module>/SKILL.md`, you may only
   edit the files in that skill's **FILES YOU MAY EDIT** list. Everything else is
   read-only for you.
5. **Acceptance tests come first.** Every SKILL.md lists the tests the module must pass.
   Run them. Don't claim done until they're green.
6. **No new top-level dependencies without a line-item justification.** Current deps:
   `anthropic`, `mss`, `keyboard`, `PyQt6`, `opencv-python`, `pytesseract`, `numpy`,
   `pydantic>=2`, `pyyaml`. Adding `torch` / `sklearn` / anything else requires user
   approval in writing.
7. **Do not rebuild existing components.** `vision.py`, `overlay.py`, `db.py`, `session.py`,
   `ocr_helpers.py`, the SQLite schema, the PyQt threading model — all stay. New work is
   additive.
8. **Set-specific numbers live only in `knowledge/set_*.yaml`.** No shop odds, pool sizes,
   XP costs, streak bonuses, or champion lists hardcoded in `.py` files. Ever.
9. **LLM calls are last resort.** The advisor (Phase 6) is a narrator that calls tools.
   It does not decide. Do not write prompts that ask the LLM to compute numbers.
10. **Perception hierarchy (added 2026-04-21, Phase 3.5).** When extracting game state,
    use the cheapest technique that works:
    - **OCR** for fixed-position text/numbers: gold, HP, level, XP, stage, round, streak,
      trait counts. Fast (<50ms), free, deterministic.
    - **Template matching** for sprites with stable visual identity: champion portraits,
      star crowns, item icons, augment icons. Fast (<200ms), free, high-confidence-scored.
    - **Claude Vision** ONLY for: (a) novel-set recognition before a template library
      exists, (b) low-confidence fallback when template match scored <0.85, (c) genuinely
      variable text that resists templating. Vision is slow (~2-4s) and costs money.
    Default to the cheaper tier. When in doubt, ask the user — do not default to Vision.
    If a sub-agent proposes using Vision for a field that OCR or template could handle,
    push back.

## Scope ceiling (say "out of scope" if asked to build these)

- Value net / any neural net training
- Combat simulator (tick-level or otherwise)
- Monte Carlo Tree Search / ISMCTS
- Riot Match-V1 data crawler
- Overwolf client-side collector
- Positioning recommendations (needs x/y data we don't have)
- Multi-user, networking, authentication, deployment-at-scale
- **Opponent scouting** (removed from v2 scope 2026-04-21; deferred to v2.5). Do not add
  scout-related types, methods, rules, or UI panels. If a feature request seems to need
  opponent data, confirm with user before building.

Everything above lives in a future v3 plan that has been explicitly deferred.

## Anti-patterns

- **Don't reach for Vision first.** See rule 10. When tempted to write a Vision prompt,
  first ask: can OCR do this? Can template matching do this? Vision is a fallback tier.
- **Don't add dormant scaffolding for deferred features.** Opponent scouting fields were
  added pre-emptively and caused silent bugs. If a feature is deferred, do NOT add empty
  types, empty fields, or empty test fixtures for it.
- **Don't parse augment descriptions.** Augment identification is icon-based (template
  match). Augment metadata lives in YAML. Vision reading augment description text is
  out of scope.

## Dev-time protocol for sub-agents

When the user spawns you to work on a specific module:

1. Load `CLAUDE.md` (this file), `ARCHITECTURE.md`, `schemas.py`, and `skills/<your_module>/SKILL.md`.
2. Do NOT load other modules' files unless `SKILL.md` tells you to.
3. Build the module. Only touch files in the **FILES YOU MAY EDIT** list.
4. Run the acceptance tests listed in SKILL.md. Fix until green.
5. Update `STATE.md` (append-only log) with: phase completed, files changed, test results.
6. Stop. Do not start the next module.

## Integration protocol (separate from module builds)

Integration passes are their own sessions. They:
- Wire a completed module into `assistant_overlay.py`
- Run the end-to-end smoke test (`tests/test_smoke.py`) against a logged capture
- Record cost + latency in `STATE.md`

Integration sessions may touch `assistant_overlay.py` and `advisor.py`. Module builds may not.

## Tone and style

- Code style: match existing Augie (type hints everywhere, `from __future__ import annotations`,
  dataclass-style or Pydantic v2, no surprise abstractions).
- Comments: explain "why", not "what". Reference research sources in comments where numbers
  come from (tftactics.gg, wongkj12, etc.).
- Commits (if asked): one phase = one logical commit. Don't squash phases together.

## When in doubt

Ask the user. Do not guess at contracts, do not guess at numbers, do not silently expand
scope. The whole point of this structure is tight coordination; guessing defeats it.
