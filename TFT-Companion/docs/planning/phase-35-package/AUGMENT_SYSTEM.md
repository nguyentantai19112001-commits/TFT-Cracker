# AUGMENT_SYSTEM.md — Phase 3.5e

> New module: augment pick recommendations at 2-1 / 3-2 / 4-2. Works by icon
> recognition (no text parsing) + multi-dimensional fit scoring against the
> current game state and top archetype prediction.

---

## Why this is its own sub-phase

Augments are the single highest-leverage decision in TFT outside of "what comp
am I playing." A bad augment pick at 2-1 can soft-lock a game. A great one at
2-1 can carry a mediocre board.

The original architecture had augments as a passive string list on `GameState`.
That was enough for the advisor to *mention* augments but not to *help pick*
them. 3.5e fixes that.

---

## The model

Every augment gets structured metadata with three components:

### 1. Stage-phase value curve

Augments have different worth at 2-1 vs 3-2 vs 4-2:

| Category | 2-1 value | 3-2 value | 4-2 value |
|---|---|---|---|
| Econ (gold, XP, rerolls) | high | medium | low |
| Combat stats (damage, AS) | medium | medium | high |
| Items (components, completed) | high | medium | low |
| Trait emblems | context-dependent | high | high |
| Hero augments | situational | high | very high |

Rationale: econ compounds over time, so early > late. Item augments fix your
item trajectory, also early > late. Combat-stat augments become more valuable
as fights decide more damage later.

### 2. Comp-affinity scores

Per archetype, each augment has an affinity in [-2, +2]:
- +2: perfect synergy (hero augment for primary carry; emblem that unlocks vertical)
- +1: good fit (combat aug that scales with archetype's playstyle)
- 0: neutral
- -1: poor fit (ranged-carry AS buff on a Brawler comp)
- -2: actively bad (econ when you're a loss-streak comp that needs stabilization)

### 3. Contextual modifiers

Augments can interact with current state:
- "Only useful if you hold completed items" (gets +1 if bench has ≥2 completed)
- "Scales with team size" (gets +1 per level ≥ 7)
- "Useless if stage 5+" (hard-zero after stage 5-1)

---

## Files to create

### `knowledge/augments_set_17.yaml`

Schema for each augment:

```yaml
augments:
  - augment_id: tactician_training
    display_name: "Tactician's Training"
    tier: silver              # silver | gold | prismatic
    category: econ
    icon_path: "augments/Tactician_Training.png"
    stage_phase_value:
      "2-1": 3
      "3-2": 1
      "4-2": -1
    comp_affinity:
      default: 0
      fast_8_standard: 2
      reroll_1cost: -1
      reroll_3cost: 1
      vertical_trait: 0
    conditions:
      min_stage: null
      max_stage: null
      requires_items: false
      requires_level: null
    notes: "Free XP each round — compounds early, dead late."

  - augment_id: preparation_3
    display_name: "Preparation III"
    tier: prismatic
    category: combat
    icon_path: "augments/Preparation_3.png"
    stage_phase_value:
      "2-1": 1
      "3-2": 2
      "4-2": 2
    comp_affinity:
      default: 1
      reroll_1cost: 3
      reroll_3cost: 3
      fast_8_standard: 0
    conditions:
      requires_level: null
    notes: "Scales with time spent on board — rerolls benefit most."
```

### `knowledge/augments_set_17.yaml` initial population

**Claude Code does NOT hand-author `comp_affinity` values.** Build the
skeleton: every augment entry with `display_name`, `category`, `tier`,
`icon_path`, `stage_phase_value` (best-guess from category), and
`comp_affinity: {default: 0}` as a placeholder.

The user fills in per-archetype affinities manually. This is the taste layer
— it's meta-specific and patch-specific, and it's the input that makes the
tool feel like the user's own tool rather than generic.

### Where the augment list comes from

Pull from Community Dragon via `tools/fetch_set_assets.py` (extended from
3.5b). The same script that fetches augment icons can fetch augment
definitions (`{augment_id, display_name, tier, description}`) and generate
the skeleton YAML automatically.

Expected count: ~70 entries (~40 new Set 17, ~30 returning generics).

### `augment_scorer.py`

```python
# augment_scorer.py
from __future__ import annotations
from schemas import GameState, CompCandidate, AugmentPick, AugmentScore

def score_offered_augments(
    offered: list[str],           # 3 augment IDs on offer
    state: GameState,
    top_comps: list[CompCandidate],
    augment_catalog: dict,        # loaded from YAML
) -> list[AugmentPick]:
    """Returns ranked picks with scores and reasoning. List length = 3."""
```

Scoring:
```python
def _score_one(augment, state, top_comps, catalog):
    entry = catalog[augment]
    stage_value = entry.stage_phase_value.get(state.stage, 0)
    
    top = top_comps[0] if top_comps else None
    affinity = entry.comp_affinity.get(top.archetype_id, entry.comp_affinity["default"]) if top else 0
    
    secondary = top_comps[1] if len(top_comps) > 1 else None
    secondary_affinity = (entry.comp_affinity.get(secondary.archetype_id, 0) * 0.5) if secondary else 0
    
    condition_modifier = _evaluate_conditions(entry.conditions, state)
    
    return stage_value + affinity + secondary_affinity + condition_modifier
```

Output: each augment gets a total score, a breakdown (stage / affinity / conditions),
and a reasoning tag list.

### New schemas.py types

Add to `schemas.py` (additive, requires note in STATE.md but no user approval
needed per existing protocol — these are for data Claude Code already has):

```python
class AugmentScore(BaseModel):
    stage_value: float
    primary_affinity: float
    secondary_affinity: float
    condition_modifier: float
    total: float

class AugmentPick(BaseModel):
    augment_id: str
    display_name: str
    score: AugmentScore
    reasoning_tags: list[str]
    rank: int  # 1, 2, or 3

class OfferedAugments(BaseModel):
    """Attached to GameState when augment UI detected."""
    stage: str  # "2-1" etc.
    offered: list[str]  # 3 augment IDs
    detected_at_round: str
```

Add to `GameState`:
```python
offered_augments: Optional[OfferedAugments] = None
```

### New recommender integration

Add a new `ActionType.PICK_AUGMENT`. When `state.offered_augments` is
populated, the recommender's `enumerate_candidates` produces 3 candidates
(one per offered augment) with scores from `augment_scorer`.

The advisor's system prompt gets an additional rule: "When the state includes
`offered_augments`, prioritize the augment-pick decision above all else. Other
actions (buy, roll, level) are secondary until the augment is picked."

---

## Icon recognition (already covered by 3.5b + 3.5c)

The augment-selection UI appears at known screen positions at 2-1, 3-2, 4-2.
State builder detects this screen type via template matching the UI
background, then extracts the 3 offered augments by icon-match against
`assets/templates/set_17/patch_17_1/augments/`.

Each match gets a confidence score. If any match is <0.85, fall back to
Claude Vision with a constrained prompt: "Identify this augment icon. It must
be one of: [list of known Set 17 augment names]." Vision handles rare
augments and cosmetic icon variants.

No augment description text is ever parsed. Icons only.

---

## Acceptance

### Tests for augment_scorer

```python
def test_econ_augment_prefers_early():
    state_21 = make_state(stage="2-1")
    state_42 = make_state(stage="4-2")
    tactician = CATALOG["tactician_training"]
    assert score_one(tactician, state_21, []) > score_one(tactician, state_42, [])

def test_hero_augment_prefers_matching_comp():
    dark_star_hero = CATALOG["supernova_jhin"]  # hypothetical
    dark_star_top = [make_comp("dark_star", total_score=0.9)]
    other_top = [make_comp("reroll_1cost", total_score=0.9)]
    assert score_one(dark_star_hero, state, dark_star_top) > score_one(dark_star_hero, state, other_top)

def test_three_augments_ranked():
    result = score_offered_augments(
        offered=["tactician_training", "preparation_3", "dark_star_soul"],
        state=make_state(stage="2-1"),
        top_comps=[make_comp("dark_star")],
        augment_catalog=CATALOG,
    )
    assert len(result) == 3
    assert result[0].rank == 1
    assert result[0].score.total >= result[1].score.total >= result[2].score.total
```

### Integration test

Run end-to-end on a logged screenshot of the augment-selection UI at 2-1.
Assert the advisor output mentions the top-ranked augment name and gives a
one-sentence rationale including "stage value" or "comp fit" as a reason.

### Acceptance numbers

- Augment icon recognition accuracy: ≥95% on 20 logged screenshots.
- Advisor turnaround on augment-pick state: ≤3s end-to-end.
- Augment scorer is deterministic: same inputs → same outputs.

---

## What the user fills in manually

After 3.5e code is complete and the YAML skeleton is generated, Claude Code
hands `knowledge/augments_set_17.yaml` back to the user with empty
`comp_affinity` blocks for all ~70 augments. The user fills in affinities
per archetype.

Time estimate: 3-4 hours for 70 augments × 12 archetypes = 840 numbers. In
practice many augments are "neutral" for most comps, so actual filled count
is ~200-300 non-zero values. Closer to 2 hours.

The user can also revise `stage_phase_value` — Claude Code's defaults are
based on augment category (econ = high-early, combat = high-late) but
specific augments may differ.

This is explicitly not Claude Code's job. The YAML skeleton is the deliverable
for 3.5e; the affinity data is the user's job.

---

## Maintenance plan

Every patch, rerun `tools/fetch_set_assets.py --update-augments`. It compares
Community Dragon's current augment list to the YAML, emits:
- NEW augments found (skeleton entries appended, flagged with `# NEW — user fill`)
- REMOVED augments (flagged with `# REMOVED` comment, not deleted in case
  user wants history)
- CHANGED display_names (flagged with `# NAME CHANGED`)

The user reviews the diff, fills in affinities for NEW augments, and the tool
stays current with ~30 min of work per patch.
