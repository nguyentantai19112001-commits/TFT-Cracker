# PERCEPTION_OVERHAUL.md — Phase 3.5b, 3.5c, 3.5d

> Vision gets demoted. Templates + OCR do the heavy lifting for own-board
> extraction. The architectural rule is captured in `CLAUDE_MD_AMENDMENT.md`
> and should be added to CLAUDE.md before this sub-phase starts.

---

## The hierarchy (repeat it until it's internalized)

| Technique | Use for | Speed | Cost | Determinism |
|---|---|---|---|---|
| **OCR** | fixed-position text: gold, HP, level, XP, stage, round, streak, trait counts | ~10-50ms | free | high with pre-processing |
| **Template matching** | sprites with stable visual ID: champion portraits, star crowns, item sprites, augment icons | ~20-100ms | free | high when confidence ≥ 0.85 |
| **Vision (Claude)** | variable text, novel-set fallback, augment descriptions (NOT icons), low-confidence double-check | ~2-4s | $0.003-0.008 | probabilistic |

Use the cheapest technique that works. Default up the ladder when the cheaper
one fails or isn't applicable. Don't default to Vision.

---

## Sub-phase 3.5b — Template library from Community Dragon

### Deliverable

A versioned asset folder, populated by a script that can be re-run each patch:

```
assets/
  templates/
    set_17/
      patch_17_1/
        champions/
          1_cost/
            Briar.png
            Poppy.png
            ...
          2_cost/
          ...
          5_cost/
        items/
          completed/
            BF_Sword.png           # components
            Bloodthirster.png      # completed items
            ...
          radiant/
            ...
        augments/
          Tactician_Training.png
          Preparation_3.png
          ...
        stars/
          one_star.png
          two_star.png
          three_star.png
        manifest.json              # hashes, dimensions, offsets
```

### Implementation

Build `tools/fetch_set_assets.py`:

```python
"""Scrape champion portraits, item icons, augment icons from Community Dragon.
Run: python tools/fetch_set_assets.py --set 17 --patch 17.1
"""
```

Data sources (from existing `data/set_data.json` if present, else from
Community Dragon JSON):
- `https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/{id}.png`
- `https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/tft/augments/`
- `https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/tft-item-icons/{id}.png`

Manifest records: filename → hash → expected size in-game (board cells and
shop slots render at different scales). The script generates both scales in
one pass so runtime code doesn't re-scale.

### Acceptance

- `assets/templates/set_17/patch_17_1/` exists and contains all 63 champions,
  all completed items, all known Set 17 augments.
- `manifest.json` validates (checksums match, dimensions listed).
- Script is idempotent: running twice produces no diffs.

### No tests needed

Scraping + disk IO. Smoke test: assert each champion in `knowledge/set_17.yaml
.champions` has a template file on disk.

---

## Sub-phase 3.5c — Own-board extraction rewrite

### What `vision.py` does today (Phase 0-3)

Sends the whole F9 screenshot to Claude Vision, asks for everything (board,
shop, traits, augments, gold, HP, stage), parses JSON, returns a `GameState`.
Takes 8-12 seconds, costs $0.015 per call.

### What it should do after 3.5c

Run a pipeline of cheap techniques first, fall up to Vision only for the few
remaining fields. Target: 2-3 seconds, $0.003-0.005 per F9.

### Pipeline

```python
def extract_state(screenshot: np.ndarray) -> GameState:
    # Step 1 — OCR on fixed-position number/text regions
    gold = ocr_gold_region(screenshot)             # ~15ms
    hp = ocr_hp_region(screenshot)                 # ~15ms
    level = ocr_level_region(screenshot)           # ~15ms
    xp = ocr_xp_region(screenshot)                 # ~15ms
    stage = ocr_stage_region(screenshot)           # ~20ms
    streak = ocr_streak_region(screenshot)         # ~15ms
    
    # Step 2 — template match sprites
    shop_units = template_match_shop(screenshot)   # ~80ms — 5 slots
    board_units = template_match_board(screenshot) # ~150ms — up to 10 hexes
    bench_units = template_match_bench(screenshot) # ~100ms — 9 slots
    board_items = template_match_items_on_board(screenshot)   # ~200ms
    bench_items = template_match_items_on_bench(screenshot)   # ~100ms
    active_traits = template_match_trait_sidebar(screenshot)  # ~80ms, icon+OCR
    
    # Step 3 — low-confidence or templated-unavailable fields
    # Augments: icon match (3.5e adds a proper augment_scorer)
    augments = template_match_augment_sidebar(screenshot)     # ~50ms
    
    # Step 4 — confidence validation
    low_confidence_fields = collect_low_confidence(
        shop_units, board_units, bench_units,
        board_items, bench_items, active_traits
    )
    
    # Step 5 — Vision fallback for low-confidence fields only
    if low_confidence_fields:
        vision_corrections = claude_vision_targeted(
            screenshot, regions=low_confidence_fields
        )  # ~1-2s, $0.002 if any called
        merge_corrections(...)
    
    return GameState(...)
```

Total budget when templates all succeed: ~750ms + OCR.
Total budget when Vision fallback fires: ~2-3s + OCR.

### Confidence rules

- Template match returns confidence ∈ [0, 1]. Threshold 0.85 = accepted.
- 0.70-0.85 = "suspect" — log the match but include it, flag for Vision
  fallback.
- <0.70 = rejected — definitely send to Vision fallback.
- Every extracted field on `GameState.source_confidence` gets populated with
  its numerical confidence. Low-confidence fields trigger a small overlay
  indicator.

### Constraints the templates need

When calling `cv2.matchTemplate`:
- Use `TM_CCOEFF_NORMED` (scale-robust, orientation-sensitive; fine here).
- Iterate over known board-hex pixel positions, not sliding window. Hex
  positions are stable per game resolution; compute once from a calibration
  screenshot and cache.
- Constrain template search to the known sprite list at the cost tier
  shop_odds allow at this level. (Matching a 5-cost sprite at level 3 shop
  is wasteful — odds are 0.)

### Vision call shape (when it fires)

System prompt (tight):
```
You are identifying small sprite regions in a TFT screenshot. I will send
a cropped image and a list of candidate champion/item names. Return JSON:
{"identity": "<name>", "confidence": 0.0-1.0}.
Name MUST be from the provided list or "unknown".
```

Input: cropped region (small image, ~60px × 60px), list of constrained
candidates (say 5-10 names). Output token budget: ~30 tokens.

Latency: ~1s per call. Cost: <$0.001 per call.

Only fires if templates scored <0.85.

### Acceptance for 3.5c

Build a corpus first: 50 logged screenshots with hand-labeled ground-truth
state. Save under `tests/fixtures/screenshots/`.

Accuracy targets on the corpus:
- Gold, HP, level, XP, stage: ≥99% exact match
- Shop units: ≥97%
- Board units: ≥95%
- Items on units: ≥90% (items are small, hardest)
- Augments: ≥95% by icon

Latency: median F9 ≤ 3s (measured end-to-end), with Vision fallback firing
on ≤20% of calls.

Cost: median F9 ≤ $0.005.

### Integration with existing `vision.py`

Don't delete `vision.py` wholesale. Refactor it into:
- `vision/ocr.py` — OCR helpers (extend `ocr_helpers.py`)
- `vision/templates.py` — template matching
- `vision/claude_vision.py` — the narrow Claude Vision wrapper (augment
  fallback, low-confidence re-check)
- `vision/pipeline.py` — the orchestrator that runs the pipeline above

The public entry point stays `extract_state(screenshot) -> GameState`.
Callers (state_builder, PipelineWorker) don't change.

---

## Sub-phase 3.5d — Continuous OCR poll

### What

A background thread that samples gold, HP, stage, round-timer every 500ms
using the OCR functions from 3.5c. No F9 needed.

### Why

- HP panic alerts without user intervention — if HP drops below 25, overlay
  flashes a warning.
- Interest-break detection — if gold is about to cross a 10-gold threshold
  downward (player about to spend and lose interest), pre-emptively warn.
- Stage transition detection — triggers automatic state refresh at round start.

### Implementation

```python
# ocr_poll.py
class ContinuousPoller(QThread):
    hpDropped = pyqtSignal(int)
    interestRiskDetected = pyqtSignal(int)  # new gold value
    stageChanged = pyqtSignal(str)
    
    def run(self):
        last_hp, last_gold, last_stage = None, None, None
        while not self.stopped:
            screenshot = capture_screen_fast()
            hp = ocr_hp_region(screenshot)
            gold = ocr_gold_region(screenshot)
            stage = ocr_stage_region(screenshot)
            
            if last_hp is not None and hp < last_hp - 10:
                self.hpDropped.emit(hp)
            if last_gold is not None and last_gold >= 10 and gold < 10:
                self.interestRiskDetected.emit(gold)
            if stage != last_stage:
                self.stageChanged.emit(stage)
            
            last_hp, last_gold, last_stage = hp, gold, stage
            self.msleep(500)
```

### Cost

Zero. All OCR, no API calls.

### Acceptance

- Thread doesn't block main UI (PyQt threading model, not GIL-bound since OCR
  releases the GIL in C extensions).
- HP drop alerts fire within 1 second of the HP change visible on screen.
- No false positives when the player isn't in a game (OCR returns "unknown"
  or same value as before).

### Integration

PipelineWorker stays on F9 as before for full state extraction. The poller
is additive — it emits signals to the overlay for passive alerts. Overlay
gets a new method `show_passive_alert(msg, severity)`.

---

## What's deferred out of 3.5

Explicitly NOT in 3.5c:
- Opponent-view extraction (scouting — removed entirely)
- Carousel detection (legacy, replaced by Realm of the Gods in Set 17)
- Item-component detection on bench during combat phase (items rearrange;
  pre-combat snapshot only)
- Damage prediction from trait interactions (v3)

Document these in STATE.md at 3.5c completion so a future sub-agent doesn't
accidentally re-introduce them.
