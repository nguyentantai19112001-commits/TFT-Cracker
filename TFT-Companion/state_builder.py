"""Unified game state builder with full DB logging.

Three-source merge in fidelity order:
    1. LCU Live Client API (Riot-official) → level, hp  (perfect)
    2. Claude Vision                        → everything else, incl. board/
                                              bench/shop/augments/traits
    3. Template matching (cv2)              → available for per-region
                                              confirmation of champ/item/aug
                                              once callers provide regions

Every call is logged to SQLite via db.py. Captures are compressed JPEG q85
max 1280px wide on disk; DB holds path + sha256 only.

Template matching is NOT yet auto-invoked on board regions — that requires
either (a) Vision returning bboxes, (b) tab-screen capture, or (c) Set-17
coord calibration. For now the matcher is exposed and ready; state-builder
logs what Vision and LCU produce, and the matcher can be called ad-hoc by
future modules.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import db
import game_assets
import ocr_helpers
import vision

# Make engine/ importable so `schemas` (the v2 frozen contract) is available
# from this module. v2 files live under engine/; don't rebuild the contract here.
_ENGINE_DIR = Path(__file__).resolve().parent / "engine"
if _ENGINE_DIR.is_dir() and str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))


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

    def to_schemas(self):
        """Convert to the v2 Pydantic `schemas.GameState`.

        Phase 0 adapter. Required fields (stage, gold, hp, level, set_id) must be
        populated before calling — raises ValueError otherwise. Optional fields
        (round, xp_current, xp_needed) default sensibly when not present.
        """
        # Lazy import so modules that don't need v2 types don't load it.
        import schemas

        missing = [f for f in ("stage", "gold", "hp", "level") if getattr(self, f) is None]
        if missing:
            raise ValueError(f"state incomplete: {missing} is None; cannot build schemas.GameState")
        set_id = self.set or game_assets.SET_ID
        if set_id is None:
            raise ValueError("state incomplete: set_id is None")

        xp_current, xp_needed = _parse_xp(self.xp)

        return schemas.GameState(
            stage=self.stage,
            gold=int(self.gold),
            hp=int(self.hp),
            level=int(self.level),
            xp_current=xp_current,
            xp_needed=xp_needed,
            streak=int(self.streak) if self.streak is not None else 0,
            set_id=str(set_id),
            board=[_as_board_unit(u) for u in (self.board or [])],
            bench=[_as_board_unit(u) for u in (self.bench or [])],
            shop=[_as_shop_slot(s) for s in (self.shop or [])],
            active_traits=[_as_trait(t) for t in (self.active_traits or [])],
            augments=list(self.augments or []),
            capture_id=self.capture_id,
        )


def _parse_xp(xp: Optional[str]) -> tuple[int, int]:
    """'38/40' -> (38, 40). Missing / unparseable -> (0, 0)."""
    if not xp or not isinstance(xp, str):
        return 0, 0
    try:
        cur, need = xp.split("/", 1)
        return int(cur.strip()), int(need.strip())
    except (ValueError, AttributeError):
        return 0, 0


def _as_board_unit(u):
    import schemas
    if isinstance(u, schemas.BoardUnit):
        return u
    if isinstance(u, dict):
        return schemas.BoardUnit(
            champion=u.get("champion") or u.get("name") or "",
            star=u.get("star") or 1,
            items=list(u.get("items") or []),
        )
    return schemas.BoardUnit(champion=str(u), star=1, items=[])


def _as_shop_slot(s):
    import schemas
    if isinstance(s, schemas.ShopSlot):
        return s
    if isinstance(s, dict):
        return schemas.ShopSlot(
            champion=s.get("champion") or s.get("name") or "",
            cost=int(s.get("cost") or 0),
            locked=bool(s.get("locked") or False),
        )
    return schemas.ShopSlot(champion=str(s), cost=0, locked=False)


def _as_trait(t):
    import schemas
    if isinstance(t, schemas.TraitActivation):
        return t
    if isinstance(t, dict):
        tier = t.get("tier") or "inactive"
        return schemas.TraitActivation(
            trait=t.get("trait") or t.get("name") or "",
            count=int(t.get("count") or 0),
            tier=tier,
        )
    return schemas.TraitActivation(trait=str(t), count=0, tier="inactive")


def _lcu_step(state: GameState, capture_id: int) -> None:
    with db.Timer() as t:
        level = ocr_helpers.get_level()
    db.log_extraction(capture_id, "level", "lcu",
                      parsed=level, elapsed_ms=t.ms)
    if level is not None:
        state.level = level
        state.sources.lcu_ok = True

    with db.Timer() as t:
        hp = ocr_helpers.get_health()
    db.log_extraction(capture_id, "hp", "lcu",
                      parsed=hp, elapsed_ms=t.ms)
    if hp is not None:
        state.hp = hp
        state.sources.lcu_ok = True


def _vision_step(state: GameState, capture_id: int, png_bytes: bytes, client) -> None:
    with db.Timer() as t:
        result = vision.parse_and_meter(png_bytes, client)

    db.log_vision_call(
        capture_id=capture_id,
        model=result["model"],
        prompt_version=result["prompt_version"],
        response_json=result["raw_text"],
        parse_ok=result["parse_ok"],
        input_tokens=result["input_tokens"],
        output_tokens=result["output_tokens"],
        cost_usd=result["cost_usd"],
        error=result["error"],
        elapsed_ms=t.ms,
    )
    state.sources.vision_cost_usd = result["cost_usd"]

    if not result["parse_ok"]:
        state.sources.vision_error = result["error"]
        return

    parsed = result["parsed"]
    state.sources.vision_ok = True

    # Fill-in-on-None policy: LCU wins over Vision for level/hp.
    if state.set is None:
        state.set = parsed.get("set")
    if state.stage is None:
        state.stage = parsed.get("stage")
    if state.gold is None and parsed.get("gold") is not None:
        state.gold = parsed["gold"]
    if state.hp is None and parsed.get("hp") is not None:
        state.hp = parsed["hp"]
    if state.level is None and parsed.get("level") is not None:
        state.level = parsed["level"]
    if state.xp is None:
        state.xp = parsed.get("xp")
    if state.streak is None and parsed.get("streak") is not None:
        state.streak = parsed["streak"]

    state.board = parsed.get("board") or []
    state.bench = parsed.get("bench") or []
    state.shop = parsed.get("shop") or []
    state.active_traits = parsed.get("active_traits") or []
    state.augments = parsed.get("augments") or []

    # Log the vision-derived fields individually so query-by-field works.
    for fld in ("stage", "gold", "hp", "level", "xp", "streak",
                "board", "bench", "shop", "active_traits", "augments"):
        db.log_extraction(capture_id, fld, "vision",
                          parsed=parsed.get(fld), elapsed_ms=0)


def build_state(png_bytes: bytes, anthropic_client,
                game_id: Optional[int] = None,
                trigger: str = "hotkey") -> GameState:
    """Capture → compress → extract → log → merge → return.

    Args:
        png_bytes: raw PNG screenshot (primary monitor or file).
        anthropic_client: initialized Anthropic client.
        game_id: optional link to games row (if you've started a game session).
        trigger: why this capture happened — "hotkey", "round_change", "test".
    """
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


def capture_and_build(anthropic_client, game_id: Optional[int] = None) -> GameState:
    """Helper: capture primary monitor + build state in one call."""
    from vision import capture_screen
    png = capture_screen()
    return build_state(png, anthropic_client, game_id=game_id, trigger="live_capture")
