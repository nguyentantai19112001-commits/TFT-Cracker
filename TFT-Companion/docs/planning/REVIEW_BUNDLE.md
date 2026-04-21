# Augie — Pipeline Review Bundle

> Single-file snapshot of the TFT live-advisor pipeline, built so a reviewer
> can understand the whole thing in one pass and propose a cleaner/better
> pipeline design. All source is pasted inline.

---

## 0. What the project is

**Augie** is a live, hotkey-driven TFT (Teamfight Tactics) coach. The user
presses **F9** mid-game → Augie screenshots the screen, extracts game state,
runs deterministic rules + scoring, then asks Claude (Sonnet 4.6) for a
one-liner recommendation + reasoning, and streams the verdict back into an
always-on-top glass overlay.

Key goals:
- Fast enough to be useful between rounds (~3s first token, ~16s complete).
- Cheap enough to spam (~$0.015 vision + ~$0.005 advisor = **~$0.02/call**).
- Set-agnostic: works on a set Claude has never seen (vision reads labels,
  doesn't rely on trained names).
- Logs *everything* to SQLite so future models / fine-tunes can replay.

### What the reviewer is asked to propose

A **better pipeline**, given the current one. Specifically:
1. Are the layers right? (vision → rules → scoring → advisor → overlay)
2. Is the LLM being used in the right places, and are the cheap layers
   (rules/scoring) carrying enough of the load?
3. What's missing or wasteful?
4. Any architectural hazards (coupling, coordination, future-proofing)?

---

## 1. High-level architecture

```
 ┌─ Screen capture (mss) ──────────────────────────────────────┐
 │  primary monitor → PNG bytes                                │
 └──────────────────┬──────────────────────────────────────────┘
                    │
      ┌─────────────┴──────────────┐
      │                            │
  [LCU API]                  [Claude Vision]
  localhost:2999             claude-sonnet-4-6
  live client data           one call, returns JSON
  (Riot-official)            board/bench/shop/traits/augments/
  level, hp                  stage/gold/streak/xp/set
  — "perfect" source         — extracts everything else
                             — robust to new sets
      │                            │
      └────────────┬───────────────┘
                   │
           [state_builder]
           merge policy: LCU > Vision for level/hp;
           Vision fills the rest.
           Logs capture + per-field extraction + vision call to DB.
                   │
        ┌──────────┴──────────┐
        │                     │
    [rules.py]          [scoring.py]
    10 pure rules        board-strength 0–100
    (HP_URGENT,          cost × star^1.5
    ECON_BELOW_INTEREST, + item bonus
    LEVEL_PACE_BEHIND,   × trait multiplier
    SPIKE_ROUND_NEXT,    normalized by
    REALM_OF_GODS_NEXT,  stage baseline
    etc.)                (HIGH/MED/LOW conf)
        │                     │
        └──────────┬──────────┘
                   │
              [advisor.py]
              claude-sonnet-4-6
              text-only (no re-sending image)
              streaming → yields one_liner → reasoning → final JSON
              ~3s first token, ~16s complete
                   │
                   ▼
              [overlay.py]
              frameless, translucent, always-on-top
              PyQt6 acrylic blur panel
              shows: verdict, reasoning, severity chips, warnings,
              cost + wall-time + game_id telemetry

              + SQLite log of every call for replay/fine-tune
```

---

## 2. Source-of-truth decisions (what's locked in vs open)

| Decision | Current answer | Why | Open to change? |
|---|---|---|---|
| Set rotation safety | Vision reads labels from screenshot; `game_assets.py` hot-loads `set_data.json` from Community Dragon | TFT rotates sets every ~3 months; hardcoded lists rot | No |
| Fidelity source for level/hp | LCU live-client API | Riot-official, zero-cost, always correct | No |
| Everything else | Claude Vision (Sonnet 4.6) | Cheaper than Opus, comparable on structured extraction; one call per F9 | Yes — could hybridize with OCR/CV for shop/gold |
| Advisor model | Sonnet 4.6 (text-only) | Cheap, fast, enough reasoning for coach-level advice | Maybe Haiku for even cheaper calls? |
| Trigger model | Manual F9 hotkey | User's idea — keeps user in control, avoids "always on" creepiness + cost | Yes, could add round-change auto-trigger |
| UI surface | PyQt6 frameless always-on-top with acrylic blur | Overlay must feel like part of the game | Yes |
| Storage | SQLite file at `db/tftcoach.db` | Simple, portable, enough for single-user logging | Could grow to Postgres later |
| Captures | Compressed JPEG q85, max 1280px wide, hashed | Keep disk bounded while preserving fidelity | No |
| Prompt versioning | `prompt_version` column on every vision_call + advisor_call | Enables offline replay of old captures against new prompts | No |

**Intentionally NOT in the pipeline (decisions already made):**
- No CNN / YOLO trained on TFT assets — template-matching hooks exist
  (`template_match.py`) but aren't wired into the active pipeline. The bet
  is Vision is "good enough" and templates are a fallback.
- No Riot Match-V5 API integration — rate limits + latency are wrong for
  live advice. Post-match replay could use it later.
- No Overwolf / in-game overlay SDK — using PyQt acrylic instead for
  portability.

---

## 3. Request lifecycle — one F9 press

Times from live harness on a 2k-ish resolution screenshot:

| Step | Where | Time | Notes |
|---|---|---|---|
| 1. Screenshot | `vision.capture_screen` (mss) | ~30ms | primary monitor → PNG bytes |
| 2. JPEG compress + log capture | `db.log_capture` | ~80ms | resize to 1280w, hash, write disk |
| 3. LCU call (level + hp) | `ocr_helpers.get_level/health` | ~5ms local | localhost:2999/liveclientdata/allgamedata |
| 4. Claude Vision extract | `vision.parse_and_meter` | ~3–6s | sonnet-4-6, ~$0.015/call |
| 5. Merge into GameState | `state_builder._vision_step` | <1ms | LCU overrides Vision on level/hp |
| 6. Rule eval | `rules.evaluate` | <1ms | 10 pure functions; sorted by severity |
| 7. Board scoring | `scoring.compute_board_strength` | <1ms | deterministic formula |
| 8. Advisor stream | `advisor.advise_stream` | first token ~3s, done ~10s | sonnet-4-6 text only |
| 9. Overlay paints | Qt signals from pipeline thread → main | inline | QueuedConnection |

Total: **~3s to useful advice, ~13–16s to full reasoning + chips.**
Cost: **~$0.02 per F9 press.**

---

## 4. Source — critical files (full)

### 4.1 `vision.py` — Claude screen reader (147 lines)

```python
"""Claude Opus 4.7 vision wrapper — screenshot bytes in, structured TFT game state out."""

import base64
import json
import re
from io import BytesIO

from anthropic import Anthropic
from PIL import Image

MODEL = "claude-sonnet-4-6"
PROMPT_VERSION = "v2"

# Rough pricing ($/M tokens) for Sonnet 4.6 — update if Anthropic changes rates.
# Opus 4.7 ($15 in / $75 out) costs ~5x more; we've measured $0.086/call on
# a 1280px TFT screenshot. Sonnet gives comparable structured extraction for
# ~$0.015/call, which is the economics we need for iteration.
COST_INPUT_PER_MTOK = 3.0
COST_OUTPUT_PER_MTOK = 15.0

VISION_SYSTEM_PROMPT = """You are a Teamfight Tactics (TFT) screen reader.

You will receive a screenshot of an active TFT game and must extract the game state as structured JSON.
The screenshot may be from ANY TFT set, including sets released after your training cutoff. Do not assume champion names, trait names, or item names from prior sets — read them directly from the image (portraits, tooltips, sidebar text, shop row labels).

Return ONLY valid JSON (no prose, no markdown fences) with this exact shape:

{
  "set": "<set number or name as shown in UI, or null>",
  "stage": "<X-Y>",
  "gold": <int>,
  "hp": <int>,
  "level": <int>,
  "xp": "<current>/<needed> or null",
  "streak": <int, positive for win streak, negative for loss streak, 0 for none>,
  "board": [
    {"champion": "<name as shown>", "star": <1|2|3>, "items": ["<full item name>", ...]}
  ],
  "bench": [
    {"champion": "<name as shown>", "star": <1|2|3>, "items": ["<full item name>", ...]}
  ],
  "shop": ["<champion name>", "<champion name>", ...],
  "active_traits": [
    {"trait": "<trait name as shown>", "count": <int>, "tier": "<bronze|silver|gold|prismatic|chromatic>"}
  ],
  "augments": ["<augment name>", ...],
  "visible_opponents": []
}

Rules:
- If a field is genuinely not visible or readable, use null or an empty array — never guess.
- Stage format is always "X-Y" (e.g., "3-2").
- `star` is determined by the colored border on the champion portrait (bronze=1, silver=2, gold=3).
- Item names must be the full in-game English name as it would appear in the item tooltip, not abbreviations.
- Champion and trait names must be transcribed exactly as shown in the current set's UI, even if unfamiliar.
- Output MUST be parseable by json.loads. No trailing commas, no comments, no markdown fences.

Entities to EXCLUDE from `board` and `bench`:
- Little Legend avatars: the player-controlled pet that walks around the board during carousel/orb rounds or between rounds. Signals: a small non-humanoid creature model (not a champion portrait), a BLUE HP bar above it (champion units have GREEN HP bars), no item slots, no star-tier border. It may have a custom display name (e.g., "trick") — treat any entity with a blue HP bar or a non-champion model as a Little Legend and omit it.
- Opponent champions: only list the player's own units. If multiple teams are visible on the board (combat or shared-map rounds), exclude anything that isn't clearly on the player's side.
- Orbs, loot, and map decorations."""


def capture_screen() -> bytes:
    """Capture the primary monitor and return PNG bytes."""
    import mss
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # primary monitor
        shot = sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        buf = BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()


def parse_and_meter(png_bytes: bytes, client: Anthropic) -> dict:
    """Send screenshot to Claude + return parsed JSON with cost/error metadata for logging."""
    b64 = base64.standard_b64encode(png_bytes).decode("utf-8")
    out = {
        "parsed": None, "raw_text": None,
        "input_tokens": None, "output_tokens": None, "cost_usd": None,
        "model": MODEL, "prompt_version": PROMPT_VERSION,
        "parse_ok": False, "error": None,
    }
    try:
        resp = client.messages.create(
            model=MODEL, max_tokens=2048, system=VISION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                {"type": "text", "text": "Extract the game state from this TFT screenshot."},
            ]}],
        )
        out["input_tokens"] = getattr(resp.usage, "input_tokens", None)
        out["output_tokens"] = getattr(resp.usage, "output_tokens", None)
        if out["input_tokens"] is not None and out["output_tokens"] is not None:
            out["cost_usd"] = round(
                out["input_tokens"] / 1_000_000 * COST_INPUT_PER_MTOK
                + out["output_tokens"] / 1_000_000 * COST_OUTPUT_PER_MTOK, 4,
            )
        raw = resp.content[0].text.strip()
        out["raw_text"] = raw
        fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", raw, re.DOTALL)
        if fence:
            raw = fence.group(1)
        out["parsed"] = json.loads(raw)
        out["parse_ok"] = True
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out
```

### 4.2 `state_builder.py` — merge LCU + Vision + log everything

```python
"""Three-source merge in fidelity order:
    1. LCU Live Client API (Riot-official) → level, hp  (perfect)
    2. Claude Vision                        → everything else
    3. Template matching (cv2)              → ready but not auto-invoked yet
"""
from __future__ import annotations
import json, time
from dataclasses import asdict, dataclass, field
from typing import Optional
import db, game_assets, ocr_helpers, vision


@dataclass
class SourceStatus:
    lcu_ok: bool = False
    vision_ok: bool = False
    vision_error: Optional[str] = None
    vision_cost_usd: Optional[float] = None
    elapsed_s: float = 0.0


@dataclass
class GameState:
    stage: Optional[str] = None
    gold: Optional[int] = None
    hp: Optional[int] = None
    level: Optional[int] = None
    xp: Optional[str] = None
    streak: Optional[int] = None
    board: list = field(default_factory=list)
    bench: list = field(default_factory=list)
    shop: list = field(default_factory=list)
    active_traits: list = field(default_factory=list)
    augments: list = field(default_factory=list)
    set: Optional[str] = None
    sources: SourceStatus = field(default_factory=SourceStatus)
    capture_id: Optional[int] = None
    game_state_id: Optional[int] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["sources"] = asdict(self.sources)
        return d


def _lcu_step(state: GameState, capture_id: int) -> None:
    with db.Timer() as t:
        level = ocr_helpers.get_level()
    db.log_extraction(capture_id, "level", "lcu", parsed=level, elapsed_ms=t.ms)
    if level is not None:
        state.level = level
        state.sources.lcu_ok = True

    with db.Timer() as t:
        hp = ocr_helpers.get_health()
    db.log_extraction(capture_id, "hp", "lcu", parsed=hp, elapsed_ms=t.ms)
    if hp is not None:
        state.hp = hp
        state.sources.lcu_ok = True


def _vision_step(state: GameState, capture_id: int, png_bytes: bytes, client) -> None:
    with db.Timer() as t:
        result = vision.parse_and_meter(png_bytes, client)

    db.log_vision_call(
        capture_id=capture_id, model=result["model"], prompt_version=result["prompt_version"],
        response_json=result["raw_text"], parse_ok=result["parse_ok"],
        input_tokens=result["input_tokens"], output_tokens=result["output_tokens"],
        cost_usd=result["cost_usd"], error=result["error"], elapsed_ms=t.ms,
    )
    state.sources.vision_cost_usd = result["cost_usd"]

    if not result["parse_ok"]:
        state.sources.vision_error = result["error"]
        return

    parsed = result["parsed"]
    state.sources.vision_ok = True

    # Fill-in-on-None policy: LCU wins over Vision for level/hp.
    if state.set is None: state.set = parsed.get("set")
    if state.stage is None: state.stage = parsed.get("stage")
    if state.gold is None and parsed.get("gold") is not None: state.gold = parsed["gold"]
    if state.hp is None and parsed.get("hp") is not None: state.hp = parsed["hp"]
    if state.level is None and parsed.get("level") is not None: state.level = parsed["level"]
    if state.xp is None: state.xp = parsed.get("xp")
    if state.streak is None and parsed.get("streak") is not None: state.streak = parsed["streak"]

    state.board = parsed.get("board") or []
    state.bench = parsed.get("bench") or []
    state.shop = parsed.get("shop") or []
    state.active_traits = parsed.get("active_traits") or []
    state.augments = parsed.get("augments") or []

    for fld in ("stage","gold","hp","level","xp","streak","board","bench","shop","active_traits","augments"):
        db.log_extraction(capture_id, fld, "vision", parsed=parsed.get(fld), elapsed_ms=0)


def build_state(png_bytes: bytes, anthropic_client, game_id: Optional[int] = None,
                trigger: str = "hotkey") -> GameState:
    """Capture → compress → extract → log → merge → return."""
    db.init_db()
    t0 = time.time()
    state = GameState()

    capture_id = db.log_capture(png_bytes, game_id=game_id, trigger=trigger)
    state.capture_id = capture_id

    _lcu_step(state, capture_id)
    _vision_step(state, capture_id, png_bytes, anthropic_client)

    state.set = state.set or game_assets.SET_ID
    state.sources.elapsed_s = round(time.time() - t0, 2)

    if game_id is not None:
        state.game_state_id = db.log_game_state(game_id, capture_id, state.to_dict())
    return state
```

### 4.3 `rules.py` — deterministic rule engine (10 rules)

```python
"""Pure-function rule engine. Each rule: (state) -> Optional[Fire].
Severity: 1.0 critical, 0.7 important, 0.4 notable, 0.1 info.
Zero-cost layer that catches obvious calls before the LLM sees the state."""
from __future__ import annotations
import re
from dataclasses import dataclass, asdict
from typing import Callable, Optional


@dataclass
class Fire:
    rule_id: str
    severity: float
    action: str          # "ROLL_DOWN", "HOLD_ECON", "LEVEL_UP", "INFO", ...
    message: str
    data: dict = None

    def to_dict(self) -> dict:
        return asdict(self)


_STAGE_RE = re.compile(r"^(\d)-(\d)$")

def _parse_stage(stage):
    if not stage: return None
    m = _STAGE_RE.match(stage.strip())
    return (int(m.group(1)), int(m.group(2))) if m else None

def _stage_key(stage):
    p = _parse_stage(stage)
    return p[0] + p[1]/10.0 if p else 0.0

EXPECTED_LEVEL = [(2.0,4),(2.5,5),(3.1,6),(3.5,7),(4.2,7),(4.5,8),(5.1,8),(5.5,9)]

def expected_level(stage):
    k = _stage_key(stage)
    if k == 0.0: return None
    last = None
    for threshold, lvl in EXPECTED_LEVEL:
        if k >= threshold: last = lvl
    return last


def _econ_below_interest(state):
    """Gold < 10 while not on deep lose-streak = leaking interest."""
    gold = state.get("gold"); streak = state.get("streak") or 0
    if gold is None or gold >= 10 or streak <= -3: return None
    return Fire("ECON_BELOW_INTEREST", 0.7, "HOLD_GOLD",
        f"Gold {gold} < 10. No interest this round.",
        {"gold": gold, "streak": streak})

def _econ_interest_threshold_miss(state):
    gold = state.get("gold")
    if gold is None or gold >= 50: return None
    thresholds = [10,20,30,40,50]
    nearest_above = min((t for t in thresholds if gold < t), default=50)
    if nearest_above - gold <= 2:
        return Fire("ECON_INTEREST_NEAR_THRESHOLD", 0.4, "HOLD_GOLD",
            f"Gold {gold}, only {nearest_above - gold}g to next interest tier.",
            {"gold": gold, "next_threshold": nearest_above})
    return None

def _lose_streak_bonus(state):
    streak = state.get("streak") or 0
    if streak > -2: return None
    bonus = 1 if streak >= -4 else (2 if streak == -5 else 3)
    return Fire("STREAK_LOSE_BONUS", 0.1, "INFO",
        f"Lose-streak {abs(streak)} → +{bonus}g/round. Extend until HP~40 or stabilize.",
        {"streak": streak, "bonus_gold": bonus})

def _win_streak_bonus(state):
    streak = state.get("streak") or 0
    if streak < 2: return None
    bonus = 1 if streak <= 4 else (2 if streak == 5 else 3)
    return Fire("STREAK_WIN_BONUS", 0.1, "INFO",
        f"Win-streak {streak} → +{bonus}g/round. Push board strength.",
        {"streak": streak, "bonus_gold": bonus})

def _hp_urgent(state):
    hp = state.get("hp")
    if hp is None or hp >= 30: return None
    return Fire("HP_URGENT", 1.0, "ROLL_DOWN",
        f"HP {hp} — critical. Spend gold on board strength NOW; tempo > economy.",
        {"hp": hp})

def _hp_caution(state):
    hp = state.get("hp")
    if hp is None or hp >= 50 or hp < 30: return None
    return Fire("HP_CAUTION", 0.4, "BOARD_CHECK",
        f"HP {hp} — verify board can win rounds. Plan stabilization roll within 1–2 stages.",
        {"hp": hp})

def _level_pace_behind(state):
    level, stage = state.get("level"), state.get("stage")
    exp = expected_level(stage)
    if level is None or exp is None or level >= exp: return None
    return Fire("LEVEL_PACE_BEHIND", 0.7 if exp - level >= 2 else 0.4, "LEVEL_UP",
        f"Level {level} at {stage} — expected ~{exp}. Buy XP unless holding for a reroll spike.",
        {"level": level, "stage": stage, "expected": exp})

def _spike_round_next(state):
    stage = state.get("stage"); p = _parse_stage(stage)
    if not p: return None
    spike_next = {(3,1):"3-2",(3,4):"3-5",(3,7):"4-1",(4,1):"4-2",(4,4):"4-5",(4,7):"5-1"}.get(p)
    if not spike_next: return None
    return Fire("SPIKE_ROUND_NEXT", 0.4, "PLAN_ROLL",
        f"Next round is {spike_next} — classic spike round. Plan your roll/level decision now.",
        {"current": stage, "spike": spike_next})

def _realm_of_gods_approaching(state):
    """Set 17 mechanic: 4-7 is Realm of the Gods, a one-time god-boon pick."""
    stage = state.get("stage"); p = _parse_stage(stage)
    if p != (4, 6): return None
    hp = state.get("hp") or 100; streak = state.get("streak") or 0
    if hp < 40 or streak <= -3:
        pick = "loss-streak / Pengu 3-cost offer (Evelynn) — stabilize"
    elif streak >= 3:
        pick = "win-streak god (Soraka HP extend, Evelynn aggressive)"
    else:
        pick = "aligned god for your comp; Kayle if you have a completed item to Radiant"
    return Fire("REALM_OF_GODS_NEXT", 0.7, "PLAN_GOD_PICK",
        f"Next round 4-7 (Realm of the Gods). Given HP {hp} and streak {streak}, lean: {pick}.",
        {"hp": hp, "streak": streak})

def _trait_uncommitted(state):
    """Stage ≥ 3-2, fewer than 2 active ≥2-count traits = uncommitted board."""
    if _stage_key(state.get("stage")) < 3.2: return None
    traits = state.get("active_traits") or []
    real_traits = [t for t in traits if (t.get("count") or 0) >= 2]
    if len(real_traits) >= 2: return None
    return Fire("TRAIT_UNCOMMITTED", 0.4, "COMMIT_DIRECTION",
        f"Only {len(real_traits)} trait(s) with 2+ units at {state.get('stage')}. Commit — random boards fall off.",
        {"active_traits": traits})


ALL_RULES: list[Callable] = [
    _econ_below_interest, _econ_interest_threshold_miss,
    _lose_streak_bonus, _win_streak_bonus,
    _hp_urgent, _hp_caution,
    _level_pace_behind, _spike_round_next, _realm_of_gods_approaching,
    _trait_uncommitted,
]


def evaluate(state_dict: dict) -> list[Fire]:
    fires: list[Fire] = []
    for rule in ALL_RULES:
        try:
            f = rule(state_dict)
            if f: fires.append(f)
        except Exception:
            pass  # rules must never crash the pipeline
    fires.sort(key=lambda f: f.severity, reverse=True)
    return fires
```

### 4.4 `scoring.py` — board strength 0–100

```python
"""Deterministic board-strength score so the advisor can reason about
"strong for this stage" vs "weak for this stage" without re-deriving it.

Formula:
    unit_value  = cost * (star ** 1.5)        # 2-star ~2x, 3-star ~2.8x
    items_bonus = total_items * 1.5           # 1 item ≈ 1.5 cost-points
    trait_mult  = 1 + 0.08 * active_traits_≥2
    raw         = (sum(unit_value) + items_bonus) * trait_mult
    score       = 100 * raw / expected_raw[stage]   # clipped to [0, 100]

Expected raw-by-stage curve (derived from typical Challenger pace):
    2-x:15  3-x:35  4-x:65  5-x:100  6-x:150

Unknown units (Vision failed to name them) fall back to assumed 2-cost;
function returns uncertainty so advisor can flag LOW confidence."""
from __future__ import annotations
import re
from typing import Optional
import game_assets

EXPECTED_RAW = {1:5, 2:15, 3:35, 4:65, 5:100, 6:150, 7:180}
UNKNOWN_UNIT_ASSUMED_COST = 2

def _parse_stage_num(stage):
    if not stage: return 0
    m = re.match(r"^(\d)-\d$", stage.strip())
    return int(m.group(1)) if m else 0

def _unit_cost(name):
    if not name or name == "Unknown": return None
    champ = game_assets.CHAMPIONS.get(name)
    return (champ or {}).get("cost")


def compute_board_strength(state: dict) -> dict:
    board = state.get("board") or []
    stage_num = _parse_stage_num(state.get("stage"))
    expected = EXPECTED_RAW.get(stage_num, 15)

    unit_value_sum = 0.0
    item_count = 0
    unknown_count = 0
    breakdown = []

    for unit in board:
        name = unit.get("champion", "Unknown")
        star = max(1, int(unit.get("star") or 1))
        items = unit.get("items") or []
        item_count += len(items)

        cost = _unit_cost(name)
        if cost is None:
            cost = UNKNOWN_UNIT_ASSUMED_COST
            unknown_count += 1

        value = cost * (star ** 1.5)
        unit_value_sum += value
        breakdown.append({"champion": name, "star": star, "items": len(items),
                          "cost": cost, "value": round(value, 2)})

    items_bonus = item_count * 1.5
    traits = state.get("active_traits") or []
    active_real = sum(1 for t in traits if (t.get("count") or 0) >= 2)
    trait_mult = 1 + 0.08 * active_real

    raw = (unit_value_sum + items_bonus) * trait_mult
    score = max(0.0, min(100.0, 100.0 * raw / expected if expected else 0))

    total_units = len(board)
    confidence = "LOW" if (total_units and unknown_count / total_units > 0.5) \
                 else "MEDIUM" if unknown_count else "HIGH"

    return {"score": round(score, 1), "raw": round(raw, 2), "expected_raw": expected,
            "stage_num": stage_num, "unit_value_sum": round(unit_value_sum, 2),
            "item_count": item_count, "items_bonus": round(items_bonus, 2),
            "active_traits": active_real, "trait_mult": round(trait_mult, 3),
            "unknown_units": unknown_count, "total_units": total_units,
            "confidence": confidence, "breakdown": breakdown}
```

### 4.5 `advisor.py` — streaming Claude coach (Sonnet 4.6 text-only)

```python
"""Advisor layer — text-only Claude call with streaming JSON parse.

Ingests: merged state + rule fires + board-strength score.
Outputs: structured JSON recommendation.

Streaming design: the system prompt locks the JSON key ORDER so the
client can parse `one_liner` and `reasoning` from the partial buffer
before the full response arrives — gets first token to user in ~3s
instead of ~16s."""
from __future__ import annotations
import json, re
from typing import Generator, Optional, Tuple
from anthropic import Anthropic
import db

MODEL = "claude-sonnet-4-6"
PROMPT_VERSION = "advisor_v1"
COST_INPUT_PER_MTOK = 3.0
COST_OUTPUT_PER_MTOK = 15.0


SYSTEM = """You are a Challenger-level Teamfight Tactics coach specialized in Set 17 "Space Gods".

You receive a JSON object with: current game state, pre-computed deterministic rule fires,
and a board-strength score (0–100 relative to ideal for the stage).

You return ONLY a JSON object (no prose, no markdown fences). The keys MUST appear in this
exact order — the client streams output and relies on one_liner and reasoning arriving first:

{
  "one_liner": "<one-sentence call, imperative, <=120 chars>",
  "confidence": "<HIGH|MEDIUM|LOW>",
  "tempo_read": "<AHEAD|ON_PACE|BEHIND|CRITICAL>",
  "primary_action": "<ROLL_DOWN|LEVEL_UP|HOLD_ECON|COMMIT_DIRECTION|PLAN_GOD_PICK|SCOUT|POSITION|OTHER>",
  "reasoning": "<2–4 sentences explaining WHY>",
  "considerations": ["<secondary point>", ...],
  "warnings": ["<warning if any>", ...],
  "data_quality_note": "<if board units are 'Unknown' or key fields missing, say so; else null>"
}

Rules:
- Direct Challenger coach tone, no hedging.
- If board_strength.confidence is LOW, explicitly call it out and drop your overall confidence to LOW.
- If HP_URGENT rule fired, primary_action is almost always ROLL_DOWN.
- Reference Set 17 mechanics naturally (Realm of the Gods at 4-7, Kayle's Radiant boon, Meeple, N.O.V.A., Psionic, lose-streak gold bonus).
- Do NOT invent champions/items — use what's in the state.
- Output must be valid JSON parseable by json.loads."""


def _build_user_payload(state: dict, rule_fires: list, board_strength: dict) -> str:
    compact_state = {
        "stage": state.get("stage"), "gold": state.get("gold"),
        "hp": state.get("hp"), "level": state.get("level"),
        "xp": state.get("xp"), "streak": state.get("streak"),
        "augments": state.get("augments") or [],
        "active_traits": state.get("active_traits") or [],
        "board_units": [{"champion": u.get("champion"), "star": u.get("star"),
                         "items": u.get("items") or []}
                        for u in (state.get("board") or [])],
        "bench": state.get("bench") or [],
        "shop": state.get("shop") or [],
    }
    fires_out = [{"id": f.rule_id, "severity": f.severity, "action": f.action,
                  "message": f.message} for f in rule_fires]
    payload = {"state": compact_state, "rule_fires": fires_out,
               "board_strength": {"score": board_strength.get("score"),
                                  "expected_raw": board_strength.get("expected_raw"),
                                  "raw": board_strength.get("raw"),
                                  "confidence": board_strength.get("confidence"),
                                  "unknown_units": board_strength.get("unknown_units"),
                                  "active_traits": board_strength.get("active_traits")}}
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _extract_complete_string_field(buf: str, key: str) -> Optional[str]:
    """Return the complete string value for `key` if the string has fully closed in buf.
    Handles escaped quotes inside the string."""
    pattern = re.compile(r'"' + re.escape(key) + r'"\s*:\s*"')
    m = pattern.search(buf)
    if not m: return None
    i = m.end(); out = []; n = len(buf)
    while i < n:
        c = buf[i]
        if c == "\\" and i+1 < n:
            out.append(buf[i:i+2]); i += 2; continue
        if c == '"':
            try: return json.loads('"' + "".join(out) + '"')
            except json.JSONDecodeError: return None
        out.append(c); i += 1
    return None


def advise_stream(state, rule_fires, board_strength, client, capture_id=None):
    """Stream the advisor call. Yields:
        ("one_liner", text)  — as soon as the one_liner JSON string closes
        ("reasoning", text)  — as soon as reasoning closes
        ("final", payload)   — terminal, full parsed recommendation + meta
    """
    user_text = _build_user_payload(state, rule_fires, board_strength)
    buf = ""
    emitted: set[str] = set()
    streamable = ("one_liner", "reasoning")

    meta = {"model": MODEL, "prompt_version": PROMPT_VERSION,
            "input_tokens": None, "output_tokens": None, "cost_usd": None,
            "parse_ok": False, "error": None, "elapsed_ms": 0}
    recommendation = None

    with db.Timer() as t:
        try:
            with client.messages.stream(
                model=MODEL, max_tokens=1024, system=SYSTEM,
                messages=[{"role":"user","content":user_text}],
            ) as stream:
                for chunk in stream.text_stream:
                    buf += chunk
                    for key in streamable:
                        if key in emitted: continue
                        val = _extract_complete_string_field(buf, key)
                        if val is not None:
                            emitted.add(key)
                            yield (key, val)
                final_msg = stream.get_final_message()

            in_tok = getattr(final_msg.usage, "input_tokens", None)
            out_tok = getattr(final_msg.usage, "output_tokens", None)
            meta["input_tokens"] = in_tok; meta["output_tokens"] = out_tok
            if in_tok is not None and out_tok is not None:
                meta["cost_usd"] = round(
                    in_tok/1_000_000*COST_INPUT_PER_MTOK + out_tok/1_000_000*COST_OUTPUT_PER_MTOK, 4)

            raw = buf.strip()
            fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", raw, re.DOTALL)
            if fence: raw = fence.group(1)
            recommendation = json.loads(raw)
            meta["parse_ok"] = True
            meta["raw_text"] = raw
        except Exception as e:
            meta["error"] = f"{type(e).__name__}: {e}"
    meta["elapsed_ms"] = t.ms

    if capture_id is not None:
        db.log_vision_call(capture_id=capture_id, model=MODEL, prompt_version=PROMPT_VERSION,
                           response_json=meta.get("raw_text"), parse_ok=meta["parse_ok"],
                           input_tokens=meta["input_tokens"], output_tokens=meta["output_tokens"],
                           cost_usd=meta["cost_usd"], error=meta["error"], elapsed_ms=meta["elapsed_ms"])

    yield ("final", {"recommendation": recommendation, "__meta__": meta})
```

### 4.6 `assistant_overlay.py` — entry point (Phase B4, PyQt overlay)

```python
"""Augie — overlay-driven live TFT advisor (Phase B4).

Threading:
    Main thread       — QApplication + OverlayPanel (all UI updates)
    Hotkey thread     — `keyboard` lib. F9 callback emits a Qt signal.
    Pipeline thread   — QThread per F9 press. Emits signals for each stream
                        event; overlay updates via QueuedConnection.
"""
from __future__ import annotations
import os, sys, time
from typing import Optional
import keyboard
from anthropic import Anthropic
from dotenv import load_dotenv
from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication

import advisor, rules, scoring, session
from overlay import OverlayPanel
from state_builder import build_state
from vision import capture_screen

HOTKEY_ADVISE = "f9"; HOTKEY_START = "f10"; HOTKEY_END = "f11"; HOTKEY_QUIT = "esc"


class PipelineWorker(QThread):
    """Runs one F9 pipeline invocation on a background thread."""
    extractingStarted = pyqtSignal()
    stateExtracted = pyqtSignal(dict)
    verdictReady = pyqtSignal(str)
    reasoningReady = pyqtSignal(str)
    finalReady = pyqtSignal(dict, dict, float, float, object)  # rec, meta, wall_s, vision_cost, game_id
    errorOccurred = pyqtSignal(str)

    def __init__(self, client: Anthropic) -> None:
        super().__init__()
        self.client = client

    def run(self) -> None:
        try:
            self.extractingStarted.emit()
            t0 = time.time()
            png = capture_screen()
            game_id = session.current_game_id()

            state = build_state(png, self.client, game_id=game_id, trigger="hotkey")
            d = state.to_dict()
            if not state.sources.vision_ok:
                self.errorOccurred.emit(f"Vision failed: {state.sources.vision_error}")
                return
            self.stateExtracted.emit(d)

            fires = rules.evaluate(d)
            bs = scoring.compute_board_strength(d)

            recommendation = None; meta = None
            for evt, payload in advisor.advise_stream(d, fires, bs, self.client,
                                                      capture_id=state.capture_id):
                if evt == "one_liner":   self.verdictReady.emit(payload)
                elif evt == "reasoning": self.reasoningReady.emit(payload)
                elif evt == "final":
                    recommendation = payload.get("recommendation")
                    meta = payload.get("__meta__")
                    break

            if not meta or not meta.get("parse_ok"):
                err = meta.get("error") if meta else "no final event"
                self.errorOccurred.emit(f"Advisor failed: {err}")
                return

            wall_s = time.time() - t0
            vision_cost = d["sources"]["vision_cost_usd"] or 0
            self.finalReady.emit(recommendation or {}, meta, wall_s, vision_cost, game_id)
        except Exception as e:
            self.errorOccurred.emit(f"{type(e).__name__}: {e}")


# (Main + hotkey bridge + AppController wiring below — unchanged pattern.)
```

### 4.7 `db.py` + `db/schema.sql` — SQLite logging layer (summary + full schema)

`db.py` exposes: `init_db()`, `log_capture(png_bytes, game_id, trigger) → capture_id`,
`log_extraction(capture_id, field, source, parsed, elapsed_ms, ...)`,
`log_template_match(...)`, `log_vision_call(...)`, `log_game_state(game_id, capture_id, state)`,
plus a `Timer` context manager. Captures are compressed JPEG q85, max 1280w; DB holds
path + sha256 only.

```sql
-- Full schema (6 tables, all with FK cascades)

CREATE TABLE games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    set_id TEXT, patch_version TEXT, queue_type TEXT,
    final_placement INTEGER, notes TEXT
);

CREATE TABLE captures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER REFERENCES games(id) ON DELETE CASCADE,
    captured_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    file_path TEXT NOT NULL, sha256 TEXT NOT NULL,
    width INTEGER NOT NULL, height INTEGER NOT NULL,
    bytes_on_disk INTEGER NOT NULL,
    trigger TEXT  -- "hotkey", "round_change", "test"
);

CREATE TABLE game_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    capture_id INTEGER REFERENCES captures(id) ON DELETE SET NULL,
    captured_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    stage TEXT, gold INTEGER, hp INTEGER, level INTEGER,
    xp_current INTEGER, xp_needed INTEGER, streak INTEGER,
    state_json TEXT NOT NULL
);

-- Per-field extraction log: source + confidence + time, used to debug fidelity.
CREATE TABLE extractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capture_id INTEGER NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
    field TEXT NOT NULL,        -- "gold", "board", "augments", ...
    source TEXT NOT NULL,       -- "lcu", "vision", "template", "ocr"
    raw_value TEXT, parsed_value TEXT,
    confidence REAL, elapsed_ms INTEGER NOT NULL, error TEXT
);

-- Every template-match attempt. Intended as the YOLO-training set eventually:
-- on ambiguous matches we dump the crop for later relabeling.
CREATE TABLE template_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capture_id INTEGER NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
    category TEXT NOT NULL,     -- "champion", "item", "augment"
    region_x INTEGER, region_y INTEGER, region_w INTEGER, region_h INTEGER,
    dumped_crop_path TEXT,      -- PNG of exact region, for later labeling
    winner_name TEXT, winner_score REAL,
    runner_up_name TEXT, runner_up_score REAL,
    is_ambiguous INTEGER DEFAULT 0, is_rejected INTEGER DEFAULT 0,
    elapsed_ms INTEGER NOT NULL
);

-- Every Claude call (vision AND advisor). prompt_version bumps when SYSTEM changes
-- → lets us replay old captures against new prompts offline.
CREATE TABLE vision_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capture_id INTEGER NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
    model TEXT NOT NULL, prompt_version TEXT NOT NULL,
    input_tokens INTEGER, output_tokens INTEGER, cost_usd REAL,
    response_json TEXT, parse_ok INTEGER NOT NULL, error TEXT,
    elapsed_ms INTEGER NOT NULL
);

CREATE TABLE rule_fires (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_state_id INTEGER NOT NULL REFERENCES game_states(id) ON DELETE CASCADE,
    rule_id TEXT NOT NULL, severity REAL NOT NULL,
    action TEXT, message TEXT
);

CREATE TABLE feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_fire_id INTEGER NOT NULL REFERENCES rule_fires(id) ON DELETE CASCADE,
    rating TEXT NOT NULL CHECK (rating IN ('agreed','disagreed','ignored')),
    note TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### 4.8 `session.py` — game-lifecycle binding

```python
"""Bind every capture / recommendation to a game_id."""
import sqlite3
from typing import Optional
import db, game_assets

_CURRENT: Optional[int] = None

def start_game(queue_type=None, notes=None) -> int:
    global _CURRENT
    db.init_db()
    conn = sqlite3.connect(db.DB_PATH)
    try:
        cur = conn.execute(
            "INSERT INTO games (set_id, patch_version, queue_type, notes) VALUES (?,?,?,?)",
            (game_assets.SET_ID, game_assets.PATCH, queue_type, notes))
        conn.commit()
        _CURRENT = cur.lastrowid
        return _CURRENT
    finally:
        conn.close()

def end_game(final_placement=None) -> None:
    global _CURRENT
    if _CURRENT is None: return
    conn = sqlite3.connect(db.DB_PATH)
    try:
        conn.execute("UPDATE games SET end_time=CURRENT_TIMESTAMP, final_placement=? WHERE id=?",
                     (final_placement, _CURRENT))
        conn.commit()
    finally:
        conn.close()
    _CURRENT = None

def current_game_id() -> Optional[int]:
    return _CURRENT
```

---

## 5. Support modules (summary, not full source)

These exist and work but aren't load-bearing to the review:

- **`ocr.py`** (60 lines) — pytesseract wrapper for regional OCR (gold,
  round number). Pipeline adapted from jfd02/TFT-OCR-BOT (GPLv3).
- **`ocr_helpers.py`** (110 lines) — LCU API helpers (`get_level`,
  `get_health`) + fuzzy-match shop reader.
- **`round_reader.py`** (35 lines) — 3-position OCR fallback for round
  indicator.
- **`screen_coords.py`** (161 lines) — **WARNING: stale.** Contains Set-15-era
  coordinates for 1920×1080. Used by OCR helpers but NOT validated against
  Set 17 UI. Vision layer bypasses these entirely.
- **`template_match.py`** (145 lines) — cv2.TM_CCOEFF_NORMED matcher
  against Community-Dragon portrait banks. Hooks ready, NOT auto-invoked.
- **`game_assets.py`** (48 lines) — hot-loads `data/set_data.json` for
  the current set (champions, items, traits). `reload()` after running
  `data/fetch_community_dragon.py`.
- **`overlay.py`** (1115 lines) — the PyQt6 glass overlay widget. All
  cosmetics: acrylic blur, severity chips, staggered fade-ins, draggable
  frameless window. Zero pipeline logic — reacts to signals only.
- **`assistant.py`** (178 lines) — older console entry point; same
  pipeline as `assistant_overlay.py` but prints to terminal.

---

## 6. The Playbook (`data/TFT_PLAYBOOK.md`, 802 lines)

Single source of truth for how the advisor should think. Structured as:

1. **TFT as Math** — resources (gold/HP/items/tempo), the clock, lobby-relative reasoning.
2. **Board Strength** — unit-contribution formula (DMG_ST/DMG_AOE/EHP/CC/UTIL), star + item + trait multipliers, composite scoring.
3. **Economy Math** — interest curve, streak income, XP cost, shop odds by level, pool depth, roll EV.
4. **Stage Benchmarks** — healthy / fast-8 / reroll curves; damage-per-loss table.
5. **Decision Trees** — level vs roll vs save; when to pivot; scouting for contest.
6. **Set 17 specifics** — [VERIFY-tagged] trait breakpoints, god-offerings, archetypes. The fastest-to-rot section.

**Current usage:** content is baked into the advisor's SYSTEM prompt as
references (Realm of the Gods, lose-streak bonus, etc.). The playbook is
NOT yet machine-consumed — future work would extract tables into
structured YAML and feed them into `rules.py` (so interest thresholds,
XP costs, trait breakpoints come from one authoritative file).

---

## 7. Known gaps + open questions for the reviewer

1. **Vision is the bottleneck.** ~3–6s per call and ~$0.015. Is there a
   smarter split — e.g., use OCR/CV for gold/stage/shop (near-instant,
   zero cost) and reserve Vision for the board read? Or cache the state
   across rounds so Vision only runs on real deltas?

2. **Advisor has no history.** Every F9 press is stateless. Should the
   advisor see the last N game_states for this game_id so it can reason
   about trajectory ("you're committing to Anima; you rolled down 20g
   at 3-5 — stay the line")?

3. **Rule layer is thin.** 10 rules. Playbook has dozens of heuristics
   encoded as tables (roll-EV math, contest thresholds, shop-odds
   decisions). Most of these are deterministic — they should probably
   live in rules, not in the LLM's head. What's the right cut?

4. **No post-game loop.** `games.final_placement` is captured, but
   there's no analysis of "which advisor calls preceded a good
   placement vs a bad one?" This is the ML gold mine — the schema's
   ready for it, the logic isn't written.

5. **Template matcher is orphaned.** `template_match.py` is wired to DB
   and ready to run, but no caller invokes it on real board regions
   because no one has calibrated Set-17 hex coordinates. Kill it, or
   use it to cross-validate Vision output?

6. **Overlay state is transient.** Verdict disappears on next F9. Should
   advice persist until explicitly dismissed? Should it auto-refresh on
   round change?

7. **Playbook → rules pipeline is manual.** Interest thresholds in
   rules.py are hand-copied from the playbook. When the playbook
   updates, rules drift. Should the playbook generate a YAML that
   rules.py reads?

8. **Single advisor call per F9.** No re-prompting, no self-critique,
   no ensemble. For ~$0.005 more we could do a two-pass call (first:
   verdict; second: sanity-check). Worth it?

---

## 8. Test coverage

Tests exist for the deterministic layers (rules, scoring, state-builder)
and as live smoke harnesses for the advisor stream timing:

- `test_rules.py` — 24 assertions, all pass. Covers edge cases for each rule.
- `test_state_builder.py` — merge policy unit tests.
- `test_advisor.py` — mocked Anthropic client + JSON parse validation.
- `test_advisor_stream.py` — streaming event sequence validation.
- `test_advisor_stream_live.py` — real API call timing harness. ~$0.02/run.
- `test_vision.py` — end-to-end with a real screenshot fixture.
- `test_phase_a2.py` — LCU + OCR integration.
- `test_imports.py` — smoke test: every module imports cleanly.

No tests yet for: overlay rendering, template matcher, session lifecycle.

---

## 9. File tree

```
TFT-Companion/
├── assistant.py              # console entry point (Phase B3)
├── assistant_overlay.py      # overlay entry point (Phase B4) ← current
├── overlay.py                # PyQt6 glass widget (1115 LOC, cosmetics)
├── run_augie.bat             # auto-elevates to admin (keyboard hotkeys)
│
├── vision.py                 # Claude screen reader
├── state_builder.py          # LCU + Vision merge
├── rules.py                  # 10 deterministic rules
├── scoring.py                # board strength 0-100
├── advisor.py                # Claude coach (streaming)
├── session.py                # game lifecycle
│
├── ocr.py / ocr_helpers.py   # tesseract + LCU API wrapper (adapted from TFT-OCR-BOT)
├── round_reader.py           # round-number OCR fallback
├── template_match.py         # cv2 matcher (not yet auto-invoked)
├── screen_coords.py          # 1920x1080 coords (stale for Set 17)
├── vec2.py / vec4.py         # coord helpers
├── game_assets.py            # loads data/set_data.json
│
├── data/
│   ├── TFT_PLAYBOOK.md       # 802-line source of truth
│   ├── tft_set17_rules.md    # rule extraction target
│   ├── fetch_community_dragon.py  # populates set_data.json
│   └── set_data.json         # gitignored; re-fetch per patch
│
├── db.py                     # SQLite logging layer
├── db/schema.sql             # 6 tables (games, captures, game_states,
│                             #           extractions, template_matches,
│                             #           vision_calls, rule_fires, feedback)
│
├── assets/                   # Community-Dragon portrait bank (gitignored)
│   ├── fetch_images.py       # downloads champion/item/augment icons
│   ├── manifest.json         # name → file mapping
│   └── champions/ items/ augments/ traits/   # (all gitignored)
│
├── captures/                 # JPEG captures (gitignored)
├── requirements.txt          # anthropic, mss, keyboard, PyQt6, cv2, pytesseract...
├── LICENSE
├── THIRD_PARTY_NOTICES.md    # credits TFT-OCR-BOT (GPLv3)
└── _unused_reference/        # TFT-OCR-BOT source, kept for reference
    └── TFT-OCR-BOT/          # jfd02's original (GPLv3) — DO NOT IMPORT
```

---

## 10. What "a proper pipeline" should answer

When the reviewer proposes a new pipeline, the key questions to land:

1. **Where does each cost (time + $) live, and what's the budget envelope?**
   Current: $0.02/call, 3–16s wall. Is there a design that's 10x cheaper
   without losing fidelity?

2. **What should be deterministic vs learned vs LLM?** Current cut:
   - Deterministic: LCU reads, 10 rules, board scoring, stage expectations.
   - Learned (TODO): None.
   - LLM: vision extraction + advice.
   Is that ratio right?

3. **What's the replay story?** Everything logs to SQLite, prompt versions
   track, captures are on disk. Can a reviewer take this schema and
   design an offline eval harness for prompt/rule tweaks?

4. **How does this survive a set rotation?** Current bet: Vision reads
   labels, assets hot-load from Community Dragon, playbook sections 6+
   get manually refreshed per patch. Strong enough, or brittle?

5. **What's the path from "advisor" to "coach that knows me"?** The
   `feedback` table exists, no UI yet. Schema's ready for per-user
   rule-fire ratings → personalized advice. Is that the right next leap,
   or should post-game analysis come first?
