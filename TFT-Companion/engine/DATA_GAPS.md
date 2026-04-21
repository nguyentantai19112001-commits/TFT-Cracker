# DATA_GAPS.md — Known missing or unverified data

> Read this before starting any phase that touches `knowledge/` or writes game-specific
> strings. The `knowledge/` files are the source of truth — never override them with
> assumptions. If something here is missing, **ask the user**, don't guess.

---

## Status key
- ✅ Verified against source
- ⚠️ Present but needs confirmation
- ❌ Missing — do not use until filled in

---

## set_17.yaml

| Field | Status | Notes |
|-------|--------|-------|
| `shop_odds` L1–L6, L8–L11 | ✅ | Verified, sums to 100 |
| `shop_odds` L7 | ✅ | `[19, 30, 40, 10, 1]` — confirmed by user |
| `pool_sizes` 1–5 cost | ✅ | Verified via game_assets cross-check |
| `spike_rounds` | ✅ | Sourced from BunnyMuffins Set 17 guide |
| `mechanic_hooks.realm_of_the_gods.trigger_stage` | ✅ | Stage 4-7 |
| `mechanic_hooks.realm_of_the_gods.gods` | ✅ | 9 gods: Ahri, Aurelion Sol, Ekko, Evelynn, Kayle, Soraka, Thresh, Varus, Yasuo. Pengu is NOT a god (generic UI element). Updated 2026-04-21 from additional-data package. |
| `gated_units` | ✅ | Zed — Invader Zed hero augment gates him (spawns stage 4-2, then enters shop). distinct=9 effective at game start. If another 5-cost is confirmed gated, drop to 8. |

## core.yaml

| Field | Status | Notes |
|-------|--------|-------|
| `xp_thresholds` | ✅ | Stable Set 14+, cross-checked |
| `streak_brackets` | ✅ | Live since patch 14.1 |
| `interest_cap`, `interest_per_10_gold` | ✅ | Standard |
| `scoring_weights` | ⚠️ | Hand-tuned placeholders — revisit after 50+ logged games |

## set_17.yaml — Phase 4 blockers

| Field | Status | Notes |
|-------|--------|-------|
| `traits[*].breakpoints` | ✅ | All 35 traits filled 2026-04-21 from data/set_data.json (Community Dragon). Comp planner trait_fit scoring now active. |
| `champions[*].traits` | ❌ **MISSING** | No champion→trait mapping in YAML. Phase 4 needs this for trait_fit scoring. Load from `data/set_data.json` (Community Dragon) or ask user. |
| `pool_sizes[5].distinct` | ⚠️ | Currently 9 (Zed gated). If another 5-cost is gated, drop to 8. Ask user. |

## knowledge/archetypes/ (Phase 4 → v3 C7 partial)

| Status | Notes |
|--------|-------|
| ✅ archetypes.yaml | 20 archetypes created in v3 C7 with core_units, breakpoints, stage_gate, bis_priority, openers |
| ⚠️ contest_rate | All values estimated — not from Mobalytics data. Flag as approximate. |
| ⚠️ augment lists | Only vex_9_5 has verified augment keys — others are stubs or empty. Pull from TFTAcademy. |
| ❌ winrate_confidence | No per-BIS-trio winrate data available. Field omitted on all units. |
| ❌ Champion BIS for 58/63 units | Only Vex, Blitzcrank, Viktor, LeBlanc, Jhin have BIS from the v3 brief. All others need fetch from TFTAcademy or Mobalytics. |

## knowledge/item_holders.yaml (v3 C7)

| Status | Notes |
|--------|-------|
| ✅ 5-cost units | Vex, Blitzcrank, Jhin, LeBlanc, Bard, Shen, Fiora, Graves, Morgana, Sona — primary family from brief |
| ✅ 4-cost units | Nami, Kindred, Karma, Xayah, Rammus, AurelionSol, Corki, Riven, MasterYi, LeBlanc |
| ✅ 3-cost carries | Viktor, Samira, Rhaast, Kai'Sa, Lulu, Diana, Illaoi, Ornn, Aurora |
| ⚠️ 2-cost holders | Pyke, Mordekaiser, Jinx, Zoe — stage roles are estimated |
| ⚠️ 1-cost holders | Ezreal, Briar, Poppy only — 11 others missing |
| ❌ BIS item recipes | item_holders.yaml references items by display name not component IDs. Needs recipe cross-reference for BISEngine. |

## constants.yaml (v3 C2)

| Field | Status | Notes |
|-------|--------|-------|
| interest_tiers | ✅ | Standard TFT math |
| streak_bonus | ✅ | Standard |
| shop_odds | ✅ (L7 ≈95%) | Level 7 sums to 95 not 100 — source rounding in brief; 5% margin applied in tests |
| xp_to_next_level | ✅ | Standard |
| econ_curve | ✅ | From bunnymuffins.lol |
| augment_distribution | ✅ | From tftodds.com |
| item_recipes | ❌ MISSING | BISEngine tests use inline recipe dict; canonical item recipes not yet in any YAML |

---

## Verified champion data (from game_assets.CHAMPIONS)

Real playable champions per cost — use these names exactly:

**1-cost:** Briar, Poppy, Veigar, Aatrox, Caitlyn, Teemo, Nasus, Twisted Fate, Talon, Ezreal, Leona, Cho'Gath, Lissandra, Rek'Sai

**2-cost:** Bel'Veth, Akali, Jinx, Gnar, Pyke, Gragas, Gwen, Jax, Milio, Zoe, Meepsie, Mordekaiser, Pantheon

**3-cost:** Miss Fortune, Illaoi, Aurora, Fizz, Maokai, Kai'Sa, Urgot, Viktor, Samira, Ornn, Lulu, Diana, Rhaast

**4-cost:** Rammus, Corki, Kindred, Karma, Aurelion Sol, The Mighty Mech, Master Yi, Nami, Nunu & Willump, Riven, LeBlanc, Xayah, Tahm Kench

**5-cost:** Bard, Fiora, Jhin, Blitzcrank, Sona, Vex, Shen, Zed, Graves, Morgana

**Real traits:** Anima, Arbiter, Bastion, Brawler, Bulwark, Challenger, Commander, Conduit, Dark Lady, Dark Star, Divine Duelist, Doomer, Eradicator, Factory New, Fateweaver, Galaxy Hunter, Gun Goddess, Marauder, Mecha, Meeple, N.O.V.A., Oracle, Party Animal, Primordian, Psionic, Redeemer, Replicator, Rogue, Shepherd, Sniper, Space Groove, Stargazer, Timebreaker, Vanguard, Voyager

---

## UI bindings gaps (added 2026-04-21)

| Gap | Status | Notes |
|-----|--------|-------|
| Augment tier (silver/gold/prismatic) | ❌ | Vision pipeline returns augment API names only. Tier not extracted. `bindings.on_state_extracted` defaults all augments to "silver". Needs either OCR tier-text recognition or icon-region template match against tier art. |
| Trait breakpoint tier per chip | ⚠️ | `on_comp_plan` uses comp archetype power tier (S/A/B/C) as a proxy for chip tier. Actual per-trait breakpoint tiers are in set_17.yaml but not wired to the TraitChip call. Wire when comp_planner exposes trait activation counts. |
| Roll p_hit in ProbCard | ❌ | ProbCard currently shows `p_reach` from top CompCandidate. The recommender computes `p_hit_at_least_1` via `econ.analyze_roll()` for ROLL_TO actions but does not persist it in `ActionCandidate.params`. Needs `params["p_hit"]` added to ROLL_TO candidates in recommender.py. |

## Known code bugs (found by Hypothesis — Task 9)

| Bug | Location | Minimal reproducer | Fix status |
|-----|----------|--------------------|------------|
| `p_hit_at_least_1` can exceed 1.0 by ~2e-16 | `econ._markov_roll()` + `_hypergeo_roll()` | level=1, gold=60, pool=(k=1, R_T=3, distinct=14) | ✅ Fixed 2026-04-21 — `min(1.0, ...)` applied to p1/p2/p3 in both functions; property test reverted to strict [0.0, 1.0]. |
