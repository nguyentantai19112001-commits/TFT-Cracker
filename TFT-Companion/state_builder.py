"""Unified game state builder.

Merges three data sources into one state dict, in order of fidelity:
  1. LCU Live Client API (Riot-official) → level, hp
  2. OCR (Tesseract on fixed regions)    → gold, round/stage
  3. Claude Vision (LLM)                 → board, bench, shop, traits,
                                           augments, streak, xp (fuzzy stuff)

Each source fills what it can. Later sources do NOT overwrite earlier ones
unless the earlier returned None. LCU is trusted absolutely; OCR is trusted
with a parse-success gate; Claude Vision is the catch-all fallback.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from io import BytesIO
from typing import Optional

from PIL import Image

import game_assets
import ocr_helpers
import round_reader
import vision


@dataclass
class SourceStatus:
    lcu_ok: bool = False
    ocr_gold_ok: bool = False
    ocr_round_ok: bool = False
    vision_ok: bool = False
    vision_error: Optional[str] = None
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

    def to_dict(self) -> dict:
        d = asdict(self)
        d["sources"] = asdict(self.sources)
        return d


def _vision_fill(state: GameState, png_bytes: bytes, client) -> None:
    try:
        parsed = vision.parse_game_state(png_bytes, client)
    except Exception as e:
        state.sources.vision_error = f"{type(e).__name__}: {e}"
        return

    state.sources.vision_ok = True

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


def build_state(png_bytes: bytes, anthropic_client) -> GameState:
    """Capture everything about the current game state.

    Args:
        png_bytes: screenshot already captured (primary monitor PNG).
        anthropic_client: initialized Anthropic client for Claude Vision.
    """
    t0 = time.time()
    state = GameState()

    # 1. LCU — perfect fidelity for level / hp when available.
    level = ocr_helpers.get_level()
    hp = ocr_helpers.get_health()
    if level is not None:
        state.level = level
        state.sources.lcu_ok = True
    if hp is not None:
        state.hp = hp
        state.sources.lcu_ok = True

    # 2. OCR — gold and round.
    gold = ocr_helpers.get_gold()
    if gold > 0:
        state.gold = gold
        state.sources.ocr_gold_ok = True

    stage = round_reader.get_round()
    if stage:
        state.stage = stage
        state.sources.ocr_round_ok = True

    # 3. Claude Vision — everything else + fallback for the above.
    _vision_fill(state, png_bytes, anthropic_client)

    state.set = state.set or game_assets.SET_ID
    state.sources.elapsed_s = round(time.time() - t0, 2)
    return state


def capture_and_build(anthropic_client) -> GameState:
    """Helper: capture primary monitor + build state in one call."""
    from vision import capture_screen
    png = capture_screen()
    return build_state(png, anthropic_client)
