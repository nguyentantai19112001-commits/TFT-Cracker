# PHASE_1_SPRITE_FETCHER.md — Sprite fetcher + cache

> Download every Set 17 champion portrait, item icon, trait icon, and
> augment icon once. Cache to disk. Serve from local QPixmaps at runtime.
> Zero network during F9.

---

## Prereq

`SCHEMA_REPORT.md` from Phase 0 exists and has been user-approved. The
field names in this phase's code come FROM that report, not from
assumptions.

## Architecture

```
    ┌─────────────────────────────────────────────┐
    │  First app launch: SpriteFetcher.ensure()   │
    │    reads CDragon JSON,                      │
    │    enumerates champions/items/augments,     │
    │    transforms .tex→.png,                    │
    │    downloads ~250 PNGs,                     │
    │    writes to ~/.augie/sprites/              │
    │    writes manifest.json                     │
    └─────────────────────────────────────────────┘
                         ↓
    ┌─────────────────────────────────────────────┐
    │  Every subsequent launch:                    │
    │    SpriteCache reads manifest.json,         │
    │    lazy-loads QPixmap on first reference,   │
    │    caches in memory for session             │
    └─────────────────────────────────────────────┘
```

## Files to create

```
engine/sprites/__init__.py       — public API
engine/sprites/fetcher.py        — one-shot download
engine/sprites/cache.py          — runtime pixmap cache
engine/sprites/paths.py          — .tex→.png transform + manifest location
engine/tests/test_sprites.py     — tests
```

## sprites/paths.py

```python
"""Canonical paths and URL transforms for TFT sprites."""
from __future__ import annotations
from pathlib import Path
import os

# --- Local filesystem ---

def sprite_dir() -> Path:
    """Where sprites live on disk. ~/.augie/sprites on all platforms."""
    d = Path.home() / ".augie" / "sprites"
    d.mkdir(parents=True, exist_ok=True)
    return d

def manifest_path() -> Path:
    return sprite_dir() / "manifest.json"

def sprite_for(api_name: str) -> Path:
    """Deterministic path for a sprite by apiName."""
    # Sanitize: apiName is already path-safe (e.g. "TFT17_Jinx")
    return sprite_dir() / f"{api_name}.png"


# --- URL transform ---

CDRAGON_PATCH = "latest"   # "latest" while Set 17 is active; pin to e.g. "16.8" at transitions
CDRAGON_BASE = f"https://raw.communitydragon.org/{CDRAGON_PATCH}"


def tex_to_png_url(tex_path: str) -> str:
    """Apply the canonical CommunityDragon transform.

    ASSETS/Maps/TFT/Icons/Augments/X.TFT_Set17.tex
    →
    https://raw.communitydragon.org/latest/game/assets/maps/tft/icons/augments/x.tft_set17.png
    """
    if not tex_path:
        raise ValueError("empty tex_path")
    # Lowercase, swap extension
    lower = tex_path.lower()
    if lower.endswith(".tex"):
        lower = lower[:-4] + ".png"
    elif lower.endswith(".dds"):
        lower = lower[:-4] + ".png"
    # Prepend the game asset base
    return f"{CDRAGON_BASE}/game/{lower}"
```

## sprites/fetcher.py

```python
"""One-shot sprite downloader. Run at first app launch."""
from __future__ import annotations
import json
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable
from loguru import logger

from .paths import (
    CDRAGON_BASE, sprite_dir, manifest_path, sprite_for, tex_to_png_url,
)

# --- Field names come from SCHEMA_REPORT.md — update if schema differs ---
# These are placeholders. Claude Code: fill from the verified report.
CHAMP_ICON_FIELD = "<from SCHEMA_REPORT.md>"   # e.g. "squareIcon"
ITEM_ICON_FIELD = "icon"                       # confirmed from real data
TRAIT_ICON_FIELD = "icon"                      # confirmed from real data

TIMEOUT_SECONDS = 15
MAX_CONCURRENT = 5   # be polite to CDragon


def fetch_all_sprites(force: bool = False) -> dict:
    """Download all Set 17 sprites to ~/.augie/sprites/.

    Returns the manifest dict. Safe to call repeatedly — skips files
    already present unless force=True.
    """
    manifest = _load_or_init_manifest()
    if manifest.get("complete") and not force:
        logger.info("sprite cache already populated; skipping fetch")
        return manifest

    logger.info("fetching Set 17 sprites from CommunityDragon")

    cdragon_data = _fetch_cdragon_json()
    jobs = _enumerate_jobs(cdragon_data)
    logger.info(f"sprite fetch: {len(jobs)} files to download")

    successes, failures = _download_all(jobs)

    manifest["champions"] = {j.api_name: str(sprite_for(j.api_name).name)
                             for j in jobs if j.kind == "champion" and j.api_name in successes}
    manifest["items"] = {j.api_name: str(sprite_for(j.api_name).name)
                         for j in jobs if j.kind == "item" and j.api_name in successes}
    manifest["traits"] = {j.api_name: str(sprite_for(j.api_name).name)
                          for j in jobs if j.kind == "trait" and j.api_name in successes}
    manifest["augments"] = {j.api_name: str(sprite_for(j.api_name).name)
                            for j in jobs if j.kind == "augment" and j.api_name in successes}
    manifest["failures"] = sorted(failures)
    manifest["complete"] = len(failures) == 0

    manifest_path().write_text(json.dumps(manifest, indent=2))
    logger.info(f"sprite fetch: {len(successes)} ok, {len(failures)} failed")
    return manifest


# --- Internals ---

class Job:
    __slots__ = ("kind", "api_name", "url")
    def __init__(self, kind: str, api_name: str, url: str):
        self.kind = kind
        self.api_name = api_name
        self.url = url


def _load_or_init_manifest() -> dict:
    mp = manifest_path()
    if mp.exists():
        try:
            return json.loads(mp.read_text())
        except Exception:
            logger.warning("manifest corrupt; reinitializing")
    return {"patch": CDRAGON_PATCH, "complete": False,
            "champions": {}, "items": {}, "traits": {}, "augments": {}}


def _fetch_cdragon_json() -> dict:
    url = f"{CDRAGON_BASE}/cdragon/tft/en_us.json"
    resp = httpx.get(url, timeout=TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.json()


def _enumerate_jobs(cdragon_data: dict) -> list[Job]:
    jobs: list[Job] = []
    # Champions — tileIcon is the compact HUD square (per SCHEMA_REPORT.md)
    for champ in cdragon_data.get("sets", {}).get("17", {}).get("champions", []):
        api = champ.get("apiName", "")
        tex = champ.get(CHAMP_ICON_FIELD, "")
        if api and tex:
            jobs.append(Job("champion", api, tex_to_png_url(tex)))

    # Items — Phase 0 confirmed: `from` is always null; use `composition`.
    # completed: composition has 2 entries (the two component apiNames)
    # components: no composition, not an augment or hero
    # augments: apiName contains _Augment_ or _Hero_
    all_items = cdragon_data.get("items", [])
    completed  = [i for i in all_items
                  if i.get("composition") and len(i.get("composition", [])) == 2]
    components = [i for i in all_items
                  if not i.get("composition")
                  and "_Augment_" not in i.get("apiName", "")
                  and "_Hero_" not in i.get("apiName", "")]
    augments   = [i for i in all_items if "_Augment_" in i.get("apiName", "")]

    for item in completed + components:
        api = item.get("apiName", "")
        tex = item.get(ITEM_ICON_FIELD, "")
        if api and tex:
            jobs.append(Job("item", api, tex_to_png_url(tex)))
    for item in augments:
        api = item.get("apiName", "")
        tex = item.get(ITEM_ICON_FIELD, "")
        if api and tex:
            jobs.append(Job("augment", api, tex_to_png_url(tex)))

    # Traits
    for trait in cdragon_data.get("sets", {}).get("17", {}).get("traits", []):
        api = trait.get("apiName", "")
        tex = trait.get(TRAIT_ICON_FIELD, "")
        if api and tex:
            jobs.append(Job("trait", api, tex_to_png_url(tex)))
    return jobs


def _download_all(jobs: list[Job]) -> tuple[set[str], set[str]]:
    successes: set[str] = set()
    failures: set[str] = set()
    with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as pool:
            futures = {pool.submit(_download_one, client, j): j for j in jobs}
            for f in as_completed(futures):
                j = futures[f]
                ok = f.result()
                (successes if ok else failures).add(j.api_name)
    return successes, failures


def _download_one(client: httpx.Client, job: Job) -> bool:
    target = sprite_for(job.api_name)
    if target.exists() and target.stat().st_size > 0:
        return True   # already downloaded
    try:
        resp = client.get(job.url)
        if resp.status_code != 200:
            logger.warning(f"{job.api_name}: HTTP {resp.status_code} from {job.url}")
            return False
        target.write_bytes(resp.content)
        return True
    except Exception as e:
        logger.exception(f"download failed for {job.api_name}: {e}")
        return False
```

## sprites/cache.py

```python
"""Runtime sprite cache. Lazy QPixmap loading with memory cache."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from loguru import logger

from .paths import sprite_dir, manifest_path, sprite_for


class SpriteCache:
    """App-wide pixmap cache, indexed by apiName. Singleton."""

    _instance: Optional["SpriteCache"] = None

    def __init__(self):
        self._pixmaps: dict[str, QPixmap] = {}
        self._manifest = self._load_manifest()
        self._missing: QPixmap | None = None

    @classmethod
    def instance(cls) -> "SpriteCache":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get(self, api_name: str, size: int = 20) -> QPixmap:
        """Return a QPixmap for the given apiName, scaled to `size`×`size`.

        Returns a placeholder pixmap if the sprite isn't cached (never None).
        Result is memoized by (api_name, size).
        """
        key = f"{api_name}@{size}"
        if key in self._pixmaps:
            return self._pixmaps[key]

        path = sprite_for(api_name)
        if not path.exists():
            logger.debug(f"sprite missing: {api_name}")
            pm = self._missing_pixmap(size)
        else:
            pm = QPixmap(str(path))
            if pm.isNull():
                logger.warning(f"sprite corrupt: {path}")
                pm = self._missing_pixmap(size)
            else:
                pm = pm.scaled(
                    size, size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

        self._pixmaps[key] = pm
        return pm

    def has(self, api_name: str) -> bool:
        return sprite_for(api_name).exists()

    def _load_manifest(self) -> dict:
        mp = manifest_path()
        if not mp.exists():
            return {}
        try:
            return json.loads(mp.read_text())
        except Exception:
            return {}

    def _missing_pixmap(self, size: int) -> QPixmap:
        """Gray square with a question mark, drawn from QPainter.

        Appears in the UI when a sprite is requested but isn't cached.
        Better than crashing or showing nothing.
        """
        if self._missing is None or self._missing.width() != size:
            from PyQt6.QtGui import QPainter, QColor, QFont, QPen
            pm = QPixmap(size, size)
            pm.fill(QColor(60, 55, 80))
            p = QPainter(pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            p.setPen(QPen(QColor(160, 150, 180)))
            f = QFont()
            f.setPointSize(max(8, size // 3))
            f.setBold(True)
            p.setFont(f)
            p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "?")
            p.end()
            self._missing = pm
        return self._missing
```

## sprites/__init__.py

```python
"""Public sprites API."""
from .fetcher import fetch_all_sprites
from .cache import SpriteCache
from .paths import sprite_dir, manifest_path

__all__ = ["fetch_all_sprites", "SpriteCache", "sprite_dir", "manifest_path"]
```

## Integration hook in assistant_overlay.py

On app startup, before showing the overlay:

```python
from engine.sprites import fetch_all_sprites, SpriteCache
from loguru import logger

def _ensure_sprites_ready():
    """Run at startup. Blocking on first launch (one-time ~30s).
    Subsequent launches are ~instant (no-op)."""
    try:
        manifest = fetch_all_sprites()
        if not manifest.get("complete"):
            failed = manifest.get("failures", [])
            logger.warning(f"{len(failed)} sprites failed to download; "
                           f"UI will show placeholders for those")
    except Exception:
        logger.exception("sprite fetch failed; UI will use placeholders only")

    # Pre-warm the cache with the singleton so first F9 isn't slower
    SpriteCache.instance()
```

Call `_ensure_sprites_ready()` in the app init after `setup_logging()` but
before showing any overlay. First launch will take 20-60 seconds depending
on connection. Show a simple splash "Downloading TFT sprites…" during
this — the splash is the one UI element built BEFORE the main overlay.

## Tests

```python
# engine/tests/test_sprites.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from engine.sprites.paths import tex_to_png_url, sprite_for, sprite_dir


def test_tex_to_png_transform():
    # Real example path from Phase 0 schema report
    tex = "ASSETS/Maps/TFT/Icons/Augments/Hexcore/Sniper_Nest_II.TFT_Set17.tex"
    url = tex_to_png_url(tex)
    assert url == "https://raw.communitydragon.org/latest/game/assets/maps/tft/icons/augments/hexcore/sniper_nest_ii.tft_set17.png"


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


# SpriteCache tests — require a QApplication, use pytest-qt or skip
@pytest.mark.skipif(True, reason="requires QApplication; run manually")
def test_cache_returns_placeholder_for_missing():
    from engine.sprites.cache import SpriteCache
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    cache = SpriteCache()
    pm = cache.get("TFT17_Nonexistent", size=20)
    assert not pm.isNull()
    assert pm.width() == 20
```

## Acceptance gate for Phase 1

Before moving to Phase 2:

1. `pytest engine/tests/test_sprites.py` — all deterministic tests pass
2. Manual: run `python -c "from engine.sprites import fetch_all_sprites; fetch_all_sprites()"` and confirm `~/.augie/sprites/` populates with ~250 PNG files
3. `~/.augie/sprites/manifest.json` exists, `"complete": true`, `"failures": []`
4. Pick 3 random champion apiNames, 3 items, 3 augments — verify each
   has a non-empty PNG file under 200KB in the sprite dir
5. Commit with: `Phase 1: sprite fetcher + cache subsystem`

If step 2 returns any failures list >5% of total, STOP and report. Don't
proceed to Phase 2 with a broken sprite set — the UI will be a mess.
