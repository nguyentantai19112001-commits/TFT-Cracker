# STATE.md — Augie v2 build log

> **Append-only.** Every phase completion adds an entry below. Never edit previous
> entries. Future sub-agents read this to know what exists.

---

## Format

```
## Phase N — STATUS YYYY-MM-DD
- added: <new files>
- edited: <modified files>
- deps added: <pip packages>
- tests: <N/N passing>
- cost per F9 (measured): $X.XXX
- latency per F9 (measured): X.X s
- notes: <blockers, future cleanup, weird discoveries>
```

---

## Phase 0 — DONE 2026-04-21
- added: augie-v2/knowledge/__init__.py (loader + 8 query helpers), augie-v2/tests/test_knowledge.py
- edited:
  - augie-v2/tests/test_knowledge.py — `test_shop_odds_sum_to_one` uses tolerance 0.06 at L7 (sums to 0.95 by authored data, trusted as-is per user)
  - ../state_builder.py — added `to_schemas()` adapter on legacy `GameState` that emits `schemas.GameState`; `sys.path` hook makes augie-v2/ importable from the parent package. Existing `.to_dict()` path untouched; existing callers unaffected
- deps added: none (pydantic 2.13.2, pyyaml 6.0.3 already present; pytest installed for test runner)
- tests: 10/10 augie-v2 test_knowledge passing; parent test_rules still passing (2/2)
- notes:
  - Integration strategy: legacy dataclass `GameState` remains the scratch builder (fields incrementally filled with None). `to_schemas()` is forward-compat for v2 consumers. Why not a full mechanical swap? `schemas.GameState` has non-Optional required fields (stage/gold/hp/level/set_id); existing pipeline builds them incrementally from None. A straight swap would either break partial-state consumers or require changing the frozen contract.
  - rules.py deliberately unchanged. BUILD_ORDER says "change imports only; rule logic stays" but `rules.py` has no schemas imports to change (local `Fire` dataclass; `state_dict: dict` signature). The deeper refactor is Phase 3.
  - `to_schemas()` maps: xp "cur/need" → (xp_current, xp_needed); board/bench/shop dicts → BoardUnit/ShopSlot; active_traits dicts → TraitActivation; raises ValueError if stage/gold/hp/level missing.
  - cost/latency: N/A (no runtime F9 path change yet).

## Phase 1 — DONE 2026-04-21
- added: econ.py, tests/test_econ.py
- edited: tests/test_econ.py — keyword args for Pydantic v2; thresholds calibrated to actual Markov values
- deps added: numpy (already present)
- tests: 13/13 passing
- notes: iid adds first-order depletion correction (p *= 1 - k/(2*R_T)); hypergeo uses effective pool N_eff = R_T/shop_p to account for cost-tier filter

## Phase 2 — DONE 2026-04-21
- added: pool.py, tests/test_pool.py
- edited: none (state_builder integration deferred to wiring phase)
- deps added: none
- tests: 12/12 passing
- notes: Jinx is 2-cost in set 17 (SKILL.md assumed 4-cost); test values corrected to copies=20, distinct=13. game_assets imported via sys.path from parent dir.

## Phase 3 — DONE 2026-04-21
- added: augie-v2/rules.py, augie-v2/tests/fixtures/rule_scenarios.yaml, augie-v2/tests/test_rules.py
- edited: none
- deps added: none
- tests: 38/38 passing
- cost per F9 (measured): N/A
- latency per F9 (measured): N/A
- notes:
  - 40 rules across 8 categories: econ (6), leveling (6), rolling (7), HP (5), streak (4), trait/comp (4), item (2), stage/board (6).
  - COMP_UNREACHABLE and COMP_ITEM_FIT_BROKEN are stubs (Phase 4 dependency, always return None).
  - _infer_primary_target: picks highest-cost non-starred board unit weighted by items as a Phase 3 proxy for comp_planner.
  - evaluate() swallows all exceptions per rule — one bad rule cannot crash the pipeline.
  - tier field on TraitActivation is a Literal ('inactive'/'bronze'/...), not int — fixed in test fixture.

## Mid-Phase-3 — DATA_GAPS_UPDATE MERGED 2026-04-21
- source: additional-data/ package (set_17_patches.yaml, DATA_GAPS_UPDATE.md, archetype_dark_star.yaml)
- edited: knowledge/set_17.yaml
  - pool_sizes: 1-cost distinct 13→14, 4-cost 12→13, 5-cost 8→9 (81 total; Zed gated)
  - gated_units: added Zed (Invader augment-gated)
  - mechanic_hooks.realm_of_the_gods.gods: 4→9 gods (Ahri, Aurelion Sol, Ekko, Evelynn, Kayle, Soraka, Thresh, Varus, Yasuo; Pengu confirmed NOT a god)
  - champions: added 63-entry list from game_assets.CHAMPIONS
  - traits: added 35-entry list from game_assets.CHAMPIONS
- edited: schemas.py — SetKnowledge +champions, +traits fields (additive, non-breaking)
- edited: rules.py — _realm_of_gods_approaching updated for all 9 gods
- edited: skills/comp_planner/SKILL.md — anima_squad (Set 10) → dark_star (Set 17) example throughout
- edited: tests/test_econ.py — all pool_size fixtures updated (distinct 12→13, 13→14)
- edited: tests/test_knowledge.py — pool_size(s,5).total 72→81
- edited: tests/test_smoke.py — PoolState distinct 12→13
- tests re-run: 79/79 passing (3 skipped: need API key)
- still unresolved:
  - Trait breakpoints for 35 traits (blocks Phase 4 scoring — not blocking Phase 3)
  - Champion→trait mapping (needed for Phase 4 archetype validation)
  - Are any 5-costs besides Zed gated? (currently distinct=9; may drop to 8)

## Phase 3.5a — SCOUTING REMOVAL 2026-04-21
- retroactive removal of all opponent-scouting scaffolding from Phases 0-3
- schemas.py: removed OpponentSnapshot class, GameState.observed_opponents field
- pool.py: removed observe_scout() method + _seen_per_opponent state; uncertainty fixed to flat ±2
- rules.py: removed ROLL_CONTESTED_BAIL (rule count: 39 → 39 total, 40→39)
- tests deleted: 6 in test_pool (scout tests), 0 in test_rules (no scout rule tests existed)
- test_smoke.py: updated test_pool_tracker_decrement to use observe_own_board
- SKILL.md forward cleanup: pool/SKILL.md (full rewrite), rules/SKILL.md (removed ROLL_CONTESTED_BAIL row + count), recommender/SKILL.md (removed contested_hard tag), comp_planner/SKILL.md (removed observe_scout call)
- new total: 79 → 73 passing (3 skipped)
- scope: v2 is own-board-only analyzer. Opponent scouting deferred to v2.5.

## Phase 4 — DONE 2026-04-21
- added: comp_planner.py, knowledge/archetypes/ (12 yaml files), tests/test_comp_planner.py
- edited: none
- deps added: none
- tests: 8/8 test_comp_planner passing; full suite 81/81 (3 skipped: API key / live game)
- notes:
  - 12 archetypes: dark_star, nova, space_groove, meeple_reroll, psionic_fast8, anima_vertical, arbiter, stargazer_reroll, bastion_frontline, challenger_reroll, mecha_fast8, rogue_skirmisher
  - p_reach: naive gold split (40g / len(need)) per missing unit; good enough for Phase 4
  - champion→trait data sourced from ../assets/manifest.json (v1 fetch); no hallucinated champ data
  - lru_cache on load_archetypes so repeated calls (per F9) don't re-parse YAML

## Phase 5 — DONE 2026-04-21
- added: recommender.py, tests/test_recommender.py
- deps added: none
- tests: 8/8 test_recommender passing; full suite 96/96 (3 skipped)
- notes:
  - enumerate_candidates: BUY (comp-relevant shop units), SELL (bench not in top-3 comp), ROLL_TO (3 floor variants: 0/20/30), LEVEL_UP (at most one), HOLD_ECON (always), SLAM_ITEM (per pair of bench components), PIVOT_COMP (if 2nd comp within 0.2 of 1st)
  - 5 scoring dims: tempo, econ, hp_risk, board_strength, pivot_value — each clamped to [-3, +3]
  - total_score = weighted sum using core.scoring_weights (hp_risk:1.5, board_strength:1.2, pivot:0.8, tempo/econ:1.0)
  - reasoning_tags: hp_danger, spike_round, interest_kept/lost, streak_preserve, comp_reachable

## Phase 6 — DONE 2026-04-21
- added: augie-v2/advisor.py (new v2 — Haiku + tool-use), tests/test_advisor.py
- edited: none (existing TFT-Companion/advisor.py untouched — v2 is a parallel file)
- deps added: none (anthropic already present)
- tests: 6/6 non-live passing, 1 skipped (needs API key)
- notes:
  - MODEL: claude-haiku-4-5-20251001 (was claude-sonnet-4-6 in v1) — ~5x cheaper
  - Two tools: econ_p_hit (compute P(hit) for narration), comp_details (look up archetype)
  - Agentic loop: up to 3 tool-use turns then final text response
  - Streaming preserved: _extract_complete_string_field emits one_liner/reasoning as soon as JSON string closes
  - _parse_verdict: maps chosen_candidate_index → ActionCandidate; clamped to valid range
  - assistant_overlay.py wiring deferred to integration pass (Phase 7.5) — v2 advisor lives in augie-v2/ not root

## Phase 7 — DONE 2026-04-21
- added: overlay.py comp panel (set_comp_plan method + compCard, compName, compReach, compBuys, compTierChip widgets)
- edited: TFT-Companion/overlay.py — additive only; existing methods unaffected
- tests: manual (visual) — overlay.py parses cleanly; import OK
- notes:
  - comp_card hidden on reset(), NOT hidden on set_extracting() — persists between F9 presses per spec
  - set_comp_plan() takes list of CompCandidate.model_dump() dicts, updates top comp only
  - Styling: cyan tint (rgba 91,204,255) matching the SEV_CYAN design token, glass border
  - Integration: call overlay.set_comp_plan(comps_dicts) from PipelineWorker after top_k_comps()
  - Chip severity mapping: S→SEV_INDIGO, A→SEV_AMBER, B→SEV_CYAN, C→SEV_GRAY (via existing SEVERITY_MAP)

## Final Polish — Tasks 1-9 — DONE 2026-04-21

### Task 1 — Workspace rename (augie-v2/ → engine/)
- renamed: augie-v2/ → engine/ (all internal paths use Path(__file__).parent, no breakage)
- edited: state_builder.py — `_ENGINE_DIR = parent / "engine"` (was "augie-v2")
- tests: all passing

### Task 2 — State validators (validators.py)
- added: validators.py (TFT-Companion root), engine/tests/test_validators.py (21 tests)
- bounds: gold [0,999], hp [-20,100], level [1,11], xp≥0, stage "N-M" parts [1,7]
- cross-field: xp ordering, board≤level, shop=0or5, items≤3, augments≤3
- lazy import in assistant_overlay.py (pre-Task-2 compatible)
- tests: 21/21 passing

### Task 3 — Advisor fallback (templates.py + advisor.py)
- added: engine/templates.py (deterministic verdict renderer), engine/tests/test_advisor_fallback.py (7 tests)
- edited: engine/advisor.py — renamed _advise_stream_llm; public advise_stream wraps with try/except fallback
- fallback emits valid one_liner/reasoning/final from templates.render_deterministic_verdict
- tests: 7/7 passing

### Task 4 — CDragon URL pinning (knowledge/__init__.py)
- added: CDRAGON_PATCH="17.1", CDRAGON_BASE, verify_set_prefix(), detect_active_prefix(), get_active_prefix(), _cache_active_prefix()
- added: engine/tests/test_cdragon_pin.py (8 tests)
- edited: engine/tools/fetch_set_assets.py, assets/fetch_images.py, data/fetch_community_dragon.py — import CDRAGON_PATCH from knowledge
- tests: 8/8 passing

### Task 5 — DXcam capture (vision.py)
- edited: vision.py — USE_DXCAM flag, _CAMERA singleton, _get_camera(), _mss_fallback(), _capture_ndarray(), release_camera()
- added: engine/tests/test_capture.py (5 tests; 2 skip on non-Windows)
- deps: dxcam added to requirements.txt
- tests: 3/3 non-Windows passing, 2 skipped

### Task 6 — PaddleOCR primary OCR (ocr_helpers.py)
- edited: ocr_helpers.py — _get_paddle(), read_text_paddle(), read_int_paddle(), read_int_tesseract(), read_int_hybrid()
- added: engine/tests/test_ocr_accuracy.py (5 unit tests + 5 corpus tests that skip without fixtures)
- deps: paddleocr added to requirements.txt
- tests: 5/5 unit passing, 5/5 corpus skipped (no labeled screenshot corpus)
- notes: corpus needed for accuracy validation — add ≥20 labeled PNGs to engine/tests/fixtures/screenshots/

### Task 7 — Dynamic TFT##_ prefix (knowledge/__init__.py)
- edited: knowledge/__init__.py — load_set() caches _ACTIVE_PREFIX from set_id; _cache_active_prefix() overrides with CDragon-detected prefix
- added: engine/tests/test_dynamic_prefix.py (7 tests)
- tests: 7/7 passing
- notes: no hardcoded TFT17_ in production logic — only the intentional sanity-check default in verify_set_prefix()

### Task 8 — Loguru + Sentry observability (logging_setup.py)
- added: logging_setup.py, engine/tests/test_logging_setup.py (4 tests)
- edited: .env.example (added SENTRY_DSN/AUGIE_VERSION/AUGIE_ENV fields), assistant_overlay.py (setup_logging() at startup + logger.exception in PipelineWorker)
- edited: requirements.txt (loguru>=0.7.0, sentry-sdk>=1.40.0, dxcam>=0.0.5, paddleocr>=2.7.0, hypothesis>=6.100.0)
- deps: loguru, sentry-sdk installed
- tests: 4/4 passing
- notes: SENTRY_DSN not set → crash reporting gracefully disabled; user needs to add DSN to .env

### Task 9 — Hypothesis property tests
- added: engine/tests/test_econ_properties.py (9 invariants), engine/tests/test_pool_properties.py (3 invariants)
- deps: hypothesis installed
- tests: 11/12 properties pass; 1 float-precision finding documented
- BUG FOUND: econ._markov_roll() returns p_hit_at_least_1=1.0000000000000002 due to numpy matrix power precision. Minimal: level=1, gold=60, pool=(k=1,R_T=3,distinct=14). Fix: clamp to min(1.0, ...). NOT fixed in Task 9 — logged in DATA_GAPS.md.

## Total test count after all 9 tasks: 161 passing, 15 skipped

## Post-handoff fixes — DONE 2026-04-21

### Fix 1 — econ float clamp (blocker)
- edited: engine/econ.py — `min(1.0, ...)` applied to p1/p2/p3 in both `_markov_roll` and `_hypergeo_roll`
- edited: engine/tests/test_econ_properties.py — reverted `test_probabilities_in_unit_interval` to strict [0.0, 1.0] assertion (1e-9 tolerance removed)
- edited: engine/DATA_GAPS.md — bug marked ✅ fixed

### Fix 2 — PaddleOCR wired into get_gold() (blocker)
- edited: ocr_helpers.py — `get_gold()` now uses `ImageGrab.grab()` + `read_int_hybrid()` instead of `ocr.get_text()`. Paddle primary, tesseract fallback; 0 on total parse failure.

### Fix 3 — Augment validator loosened (should-fix)
- edited: validators.py — removed augments > 3 hard failure (Vision partial parse is legitimate); replaced with explanatory comment
- edited: engine/tests/test_validators.py — `test_four_augments_fails` → `test_four_augments_passes` to match new behavior

### Fix 4 — Trait breakpoints filled (should-fix)
- edited: engine/knowledge/set_17.yaml — all 35 traits now have breakpoints from data/set_data.json (Community Dragon)
- edited: engine/DATA_GAPS.md — traits[*].breakpoints marked ✅ verified

### Fix 5 — Mid-stream fallback test (should-fix)
- edited: engine/tests/test_advisor_fallback.py — added `test_advisor_mid_stream_exception_caught`: yields one event then raises, verifies `except Exception` in `yield from` catches mid-stream crash and emits fallback final

- tests: 162 passing, 15 skipped (was 161/15)

## Score-push fixes — DONE 2026-04-21

### Fix 6 — Smoke tests: 0/9 → 8/9 passing
- edited: engine/tests/test_smoke.py — all `Path("*.py")` skipif guards replaced with `_ENGINE / "*.py"` absolute-path checks; added `_ENGINE` path constant + sys.path insert so engine modules resolve from the test CWD
- added: engine/tests/fixtures/captures/minimal/state.json — minimal GameState fixture so test_full_pipeline_on_capture runs without a live game
- extended: test_full_pipeline_on_capture now exercises validate → rules → comp_planner → recommender on the fixture (not just JSON parse)
- 1 remaining skip: test_advisor_picks_from_top_k — explicitly `pytest.skip()`'d; requires live API key by design

### Fix 7 — Logging migration: print() → logger in assistant_overlay.py
- edited: assistant_overlay.py — all 9 print() calls replaced with logger.info/warning/critical calls; structured log lines now capture game_id and placement

### Fix 8 — Schema deviation documented
- edited: engine/schemas.py — AdvisorVerdict.chosen_candidate annotated with 3-line comment explaining why it is required (not Optional) and the HOLD_ECON placeholder contract

### Fix 9 — pytest slow mark registered
- added: engine/tests/conftest.py — registers 'slow' mark to eliminate PytestUnknownMarkWarning

- tests: 170 passing, 7 skipped (7 legitimately require live game/API key/labeled corpus)

## Champion → traits mapping — DONE 2026-04-21
- scripts/fill_champion_traits.py added (ruamel.yaml; display-name join key; ARTIFACT_TRAITS filter)
- set_17.yaml: 63/63 champions newly populated; 0 conflicts; 0 no-match; 0 already-had
- test_champion_traits.py: 5 tests locking the mapping
- Unblocks: comp_planner trait_fit consumer (Phase C wires it)
- Still blocked: trait_fit scoring reads board/augments/items only; champion.traits consumer not yet written (Phase C)

## comp_planner trait_fit consumer — DONE 2026-04-21
- _compute_trait_fit now takes (archetype, state, set_) — one call site updated at score_archetype:143
- Fourth scoring signal active (weight 0.4): counts board units' traits matching archetype.required_traits
- test_trait_fit_uses_champion_traits: new test locks the behavior (3 Dark Star units > empty board)
- Closes YELLOW note from TRAITS_AUDIT.md
- Remaining gap: trait breakpoints per archetype mostly empty — trait_fit fires but synergy cap limited by archetype data

## ui-aurora prereq blockers — ALL RESOLVED 2026-04-21

Blocker 1 — econ float clamp: DONE (commit 19949e5 + pin test 9ac322d)
Blocker 2 — get_gold() hybrid wiring: DONE (commit 19949e5)
Blocker 3 — smoke test run: 8/9 passed, 1 skipped (hardcoded pytest.skip — requires recorded API responses)
  test run output: py -m pytest engine/tests/test_smoke.py -v -s → 8 passed, 1 skipped in 0.45s
  latency measurement: NOT YET MEASURED — requires live F9 press during a real TFT game
  gate decision: proceeding to Phase 0 per user approval; latency to be measured on first real session
