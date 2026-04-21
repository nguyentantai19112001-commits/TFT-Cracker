"""Phase 1 sprite fetcher acceptance tests."""
from __future__ import annotations
import sys
from pathlib import Path

_ENGINE = Path(__file__).resolve().parents[1]
if sys.path[0] != str(_ENGINE):
    sys.path.insert(0, str(_ENGINE))

import pytest
from sprites.paths import tex_to_png_url, sprite_for, CDRAGON_PATCH


def test_tex_to_png_transform():
    tex = "ASSETS/Maps/TFT/Icons/Augments/Hexcore/Sniper_Nest_II.TFT_Set17.tex"
    url = tex_to_png_url(tex)
    assert url == (
        f"https://raw.communitydragon.org/{CDRAGON_PATCH}/game/"
        "assets/maps/tft/icons/augments/hexcore/sniper_nest_ii.tft_set17.png"
    )


def test_tex_extension_swap():
    assert tex_to_png_url("ASSETS/X.tex").endswith(".png")


def test_dds_extension_swap():
    assert tex_to_png_url("ASSETS/X.dds").endswith(".png")


def test_empty_raises():
    with pytest.raises(ValueError):
        tex_to_png_url("")


def test_sprite_for_deterministic():
    p1 = sprite_for("TFT17_Jinx")
    p2 = sprite_for("TFT17_Jinx")
    assert p1 == p2
    assert p1.suffix == ".png"


def test_sprite_for_uses_api_name_as_filename():
    p = sprite_for("TFT17_Akali")
    assert p.stem == "TFT17_Akali"


def test_cdragon_patch_propagates_to_url():
    """URL must embed whatever CDRAGON_PATCH is, not a hardcoded string."""
    url = tex_to_png_url("ASSETS/X/Y.tex")
    assert CDRAGON_PATCH in url


@pytest.mark.skipif(True, reason="requires QApplication; run manually")
def test_cache_returns_placeholder_for_missing():
    from sprites.cache import SpriteCache
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    cache = SpriteCache()
    pm = cache.get("TFT17_Nonexistent", size=20)
    assert not pm.isNull()
    assert pm.width() == 20
