"""Canonical paths and URL transforms for TFT sprites."""
from __future__ import annotations
from pathlib import Path

# --------------------------------------------------------------------------
# Local filesystem layout
# --------------------------------------------------------------------------

def sprite_dir() -> Path:
    """~/.augie/sprites/ — single source of truth for all cached PNGs."""
    d = Path.home() / ".augie" / "sprites"
    d.mkdir(parents=True, exist_ok=True)
    return d


def manifest_path() -> Path:
    return sprite_dir() / "manifest.json"


def sprite_for(api_name: str) -> Path:
    """Deterministic on-disk path for a sprite keyed by apiName."""
    return sprite_dir() / f"{api_name}.png"


# --------------------------------------------------------------------------
# CDragon URL transform
# --------------------------------------------------------------------------
# "latest" while Set 17 is active. Pin to e.g. "16.8" at patch transitions.
# Must stay in sync with knowledge/__init__.py CDRAGON_PATCH.
CDRAGON_PATCH = "latest"
CDRAGON_BASE  = f"https://raw.communitydragon.org/{CDRAGON_PATCH}"


def tex_to_png_url(tex_path: str) -> str:
    """Apply the canonical CommunityDragon .tex → .png URL transform.

    ASSETS/Characters/TFT17_Jinx/HUD/TFT17_Jinx_Square.TFT_Set17.tex
    →
    https://raw.communitydragon.org/latest/game/assets/characters/tft17_jinx/hud/tft17_jinx_square.tft_set17.png

    Verified against 4 asset classes in Phase 0 (all HTTP 200).
    """
    if not tex_path:
        raise ValueError("empty tex_path")
    lower = tex_path.lower()
    if lower.endswith(".tex"):
        lower = lower[:-4] + ".png"
    elif lower.endswith(".dds"):
        lower = lower[:-4] + ".png"
    return f"{CDRAGON_BASE}/game/{lower}"
