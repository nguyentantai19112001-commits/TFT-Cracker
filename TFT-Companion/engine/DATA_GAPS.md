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
| `traits[*].breakpoints` | ❌ **MISSING** | All 35 traits have empty breakpoints. Comp planner scores archetypes by required_traits meeting breakpoints. Needs Community Dragon or tactics.tools verification. |
| `champions[*].traits` | ❌ **MISSING** | No champion→trait mapping in YAML. Phase 4 needs this for trait_fit scoring. Load from `data/set_data.json` (Community Dragon) or ask user. |
| `pool_sizes[5].distinct` | ⚠️ | Currently 9 (Zed gated). If another 5-cost is gated, drop to 8. Ask user. |

## knowledge/archetypes/ (Phase 4 — NOT STARTED)

| Status | Notes |
|--------|-------|
| ❌ **NOT CREATED** | 12 archetype YAML files needed. Source from tactics.tools / Mobalytics Set 17 tier lists. All champion names must be verified against `game_assets.CHAMPIONS` before writing. |

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

## Known code bugs (found by Hypothesis — Task 9)

| Bug | Location | Minimal reproducer | Fix needed |
|-----|----------|--------------------|------------|
| `p_hit_at_least_1` can exceed 1.0 by ~2e-16 | `econ._markov_roll()` | level=1, gold=60, pool=(k=1, R_T=3, distinct=14) | Clamp outputs: `p1 = min(1.0, float(np.sum(dist[1:])))`. Not fixed in Task 9 (protocol: report only). |
