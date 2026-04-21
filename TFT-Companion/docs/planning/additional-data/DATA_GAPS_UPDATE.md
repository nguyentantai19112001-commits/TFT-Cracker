# DATA_GAPS_UPDATE.md — Response to DATA_GAPS.md

> **Read this first.** It resolves the gaps flagged in your `DATA_GAPS.md` and fills
> in real data using the authoritative champion list you provided.
>
> **Build state note:** the user confirmed you are currently in **Phase 3** (rules
> expansion). Phases 0, 1, 2 are complete. That changes the integration steps —
> follow `MID_BUILD_INTEGRATION.md`, **not** the earlier "start at Phase 0" guide.
> The pool_sizes change in this package retroactively affects Phase 1 test
> fixtures; it's not a pre-start data drop.

---

## 1. Sync corrections — you're looking at a pre-audit copy

Three items you flagged as ❌ INCOMPLETE / MISSING were already fixed in a pre-Phase-0
audit that you don't have yet. The up-to-date `set_17.yaml` in the project package
(delivered 2026-04-20) has these correct. Don't re-fix them; just use the current YAML.

| Your DATA_GAPS.md entry | Actual current state | Where to verify |
|---|---|---|
| `realm_of_the_gods.gods` ❌ INCOMPLETE — only 4 gods | All 9 gods present with profiles (Ahri, Aurelion Sol, Ekko, Evelynn, Kayle, Soraka, Thresh, Varus, Yasuo). Pengu correctly listed as `generic_offer`, not a god. | `set_17.yaml` lines 60-127 |
| `gated_units` ❌ MISSING — empty | Zed added with `unlock_condition: "Invader Zed hero augment"` | `set_17.yaml` gated_units block |
| `shop_odds` L7 verification note | L7 **and** L8 **and** L9 were fixed. Previous values didn't sum to 100 (L7=95, L8=100, L9=100 but sources disagreed). Current authoritative numbers in place. | `set_17.yaml` shop_odds block |

**Action for you:** Re-read `set_17.yaml` before starting Phase 0. The file in your
working directory is already the fixed version. If you see only 4 gods or empty
`gated_units`, you have a stale copy — ask the user to re-extract the package.

Also check `STATE.md` — there is a "Pre-Phase-0 — KNOWLEDGE AUDIT NOTE 2026-04-21"
block at the top that documents all the fixes.

---

## 2. New fills using your authoritative champion + trait data

You gave me `game_assets.CHAMPIONS` content in DATA_GAPS.md. That's authoritative. I
used it to fill in three gaps.

### 2a. `pool_sizes.distinct` counts were stale

My `pool_sizes` used the Set 11+ baseline of `13/13/13/12/8 distinct` (copied from
wongkj12's calculator). Your champion list shows Set 17 actually has:

| Cost | My YAML (distinct) | Actual count from your data | Fix |
|---|---|---|---|
| 1-cost | 13 | **14** | Bump to 14 |
| 2-cost | 13 | 13 | No change |
| 3-cost | 13 | 13 | No change |
| 4-cost | 12 | **13** | Bump to 13 |
| 5-cost | 8 | **10 total** (9 after Zed gate, possibly 8 if one more is gated) | Flag — see §3 |

This affects P(hit) math directly. 14 distinct 1-costs vs 13 changes R_T in every
1-cost roll calc. **Apply the patch in `set_17_patches.yaml`.**

### 2b. Broken archetype example in `skills/comp_planner/SKILL.md`

My example archetype (`anima_squad` with Xayah/Rakan/Vayne/Sylas/Leona) is from Set 10.
In Set 17:
- "Anima Squad" does not exist as a trait. Set 17's trait is **Anima** (loss-streak
  tech trait, completely different).
- Rakan, Sylas, Vayne do not exist in Set 17.
- Xayah and Leona DO exist (4-cost and 1-cost respectively) but don't share a trait.

Replaced with `dark_star` archetype using real Set 17 units. See
`archetype_dark_star.yaml` in this package. Claude Code: swap this into SKILL.md
Phase 4 description, and delete all references to `anima_squad` from the examples
in `skills/rules/SKILL.md` and `skills/recommender/SKILL.md` too (if any — I only
remember putting it in comp_planner but audit both).

### 2c. Traits section was missing from `set_17.yaml`

You listed 35 traits. `set_17.yaml` had no `traits:` block. The comp_planner (Phase 4)
needs trait breakpoints to validate archetypes. Added a `traits:` section to the
patch with all 35 trait names. **Breakpoints (2/4/6 or 3/5/7 etc.) still need
verification** — I can't extract those from your list. Flag it in STATE.md and
load from Community Dragon at Phase 4 start if possible.

---

## 3. Still unresolved — need the user to confirm

These are the things I can't resolve from what you gave me. When you hit them, stop
and ask the user. Don't guess.

| Unknown | Why it matters | Where it blocks |
|---|---|---|
| Are any 5-costs besides Zed gated at game start? | Affects `pool_sizes[5].distinct` — 9 vs 8 vs 10 | Phase 1 (econ P(hit)) |
| Trait breakpoints (e.g. Dark Star 3/6/9?) | Comp planner scores archetypes by required_traits meeting breakpoints | Phase 4 |
| Which champions belong to which traits? | Same | Phase 4 |
| Spike rounds — are my defaults right for Set 17 specifically? | Rule `SPIKE_ROUND_NEXT` fires on these | Phase 3 |
| Augment → trait mapping (for augment-driven archetype hints) | Trait_fit scoring in comp_planner uses this | Phase 4, optional |

For traits + champion-trait mapping, the cleanest fix is to load from
`data/set_data.json` (Community Dragon) at runtime, not hand-author. Your Phase 0
knowledge loader can do this as a merge step: YAML for the stable catalog (gods,
shop odds, pool sizes) + JSON for the dynamic trait/champion details.

---

## 4. What to do with this package

```
additional-data/
├── DATA_GAPS_UPDATE.md         ← this file; READ FIRST
├── MID_BUILD_INTEGRATION.md    ← USE THIS — applies to Phase 3 in-progress state
├── set_17_patches.yaml         ← merge into knowledge/set_17.yaml
└── archetype_dark_star.yaml    ← valid example for comp_planner SKILL.md
```

Steps:
1. Read this file.
2. Follow `MID_BUILD_INTEGRATION.md` — it starts with a STEP 0 that asks you to
   report current state before touching anything. Do that step, let the user
   confirm, then proceed.
3. Append an entry to `STATE.md` confirming the merge.
4. Resume Phase 3 from wherever you left off.

---

## 5. Protocol note — this is how we communicate

When you discover data you can't verify, write it to `DATA_GAPS.md` (as you did here).
When I see it, I respond with a `DATA_GAPS_UPDATE.md` + patch files. We don't edit
each other's files silently — we exchange dated, scoped diffs. Keep this loop going
for every phase.

If a future gap is something **only the user can answer** (patch-specific meta, personal
preferences), flag it in `DATA_GAPS.md` with a 🛑 and the user will respond directly.
Don't proxy guesses through me for user-only questions.
