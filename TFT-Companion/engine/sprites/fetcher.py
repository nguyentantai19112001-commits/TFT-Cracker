"""One-shot sprite downloader. Run at first app launch."""
from __future__ import annotations
import json
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger

from .paths import (
    CDRAGON_BASE, CDRAGON_PATCH, sprite_dir, manifest_path,
    sprite_for, tex_to_png_url,
)

# Field names verified in Phase 0 SCHEMA_REPORT.md — do not change without re-verifying.
CHAMP_ICON_FIELD  = "tileIcon"   # compact HUD square; best for UI grid
ITEM_ICON_FIELD   = "icon"
TRAIT_ICON_FIELD  = "icon"

TIMEOUT_SECONDS = 15
MAX_CONCURRENT  = 5   # polite ceiling; CDragon has no stated rate limit


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
    manifest["items"]     = {j.api_name: str(sprite_for(j.api_name).name)
                             for j in jobs if j.kind == "item"     and j.api_name in successes}
    manifest["traits"]    = {j.api_name: str(sprite_for(j.api_name).name)
                             for j in jobs if j.kind == "trait"    and j.api_name in successes}
    manifest["augments"]  = {j.api_name: str(sprite_for(j.api_name).name)
                             for j in jobs if j.kind == "augment"  and j.api_name in successes}
    manifest["failures"]  = sorted(failures)
    manifest["complete"]  = len(failures) == 0

    manifest_path().write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info(f"sprite fetch: {len(successes)} ok, {len(failures)} failed")
    return manifest


# --------------------------------------------------------------------------
# Internals
# --------------------------------------------------------------------------

class _Job:
    __slots__ = ("kind", "api_name", "url")

    def __init__(self, kind: str, api_name: str, url: str) -> None:
        self.kind     = kind
        self.api_name = api_name
        self.url      = url


def _load_or_init_manifest() -> dict:
    mp = manifest_path()
    if mp.exists():
        try:
            return json.loads(mp.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("sprite manifest corrupt; reinitializing")
    return {
        "patch": CDRAGON_PATCH,
        "complete": False,
        "champions": {}, "items": {}, "traits": {}, "augments": {},
    }


def _fetch_cdragon_json() -> dict:
    url = f"{CDRAGON_BASE}/cdragon/tft/en_us.json"
    resp = httpx.get(url, timeout=TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.json()


def _enumerate_jobs(cdragon_data: dict) -> list[_Job]:
    jobs: list[_Job] = []

    # Champions — tileIcon is the compact HUD square (SCHEMA_REPORT.md)
    for champ in cdragon_data.get("sets", {}).get("17", {}).get("champions", []):
        api = champ.get("apiName", "")
        tex = champ.get(CHAMP_ICON_FIELD, "")
        if api and tex:
            jobs.append(_Job("champion", api, tex_to_png_url(tex)))

    # Items — Phase 0 confirmed: `from` is always null; classify via `composition`.
    # completed:  composition has exactly 2 entries (the two component apiNames)
    # components: no composition, not an augment or hero mechanic
    # augments:   apiName contains _Augment_ or _Hero_
    all_items  = cdragon_data.get("items", [])
    completed  = [i for i in all_items
                  if i.get("composition") and len(i.get("composition", [])) == 2]
    components = [i for i in all_items
                  if not i.get("composition")
                  and "_Augment_" not in i.get("apiName", "")
                  and "_Hero_"    not in i.get("apiName", "")]
    augments   = [i for i in all_items if "_Augment_" in i.get("apiName", "")]

    for item in completed + components:
        api = item.get("apiName", "")
        tex = item.get(ITEM_ICON_FIELD, "")
        if api and tex:
            jobs.append(_Job("item", api, tex_to_png_url(tex)))

    for item in augments:
        api = item.get("apiName", "")
        tex = item.get(ITEM_ICON_FIELD, "")
        if api and tex:
            jobs.append(_Job("augment", api, tex_to_png_url(tex)))

    # Traits
    for trait in cdragon_data.get("sets", {}).get("17", {}).get("traits", []):
        api = trait.get("apiName", "")
        tex = trait.get(TRAIT_ICON_FIELD, "")
        if api and tex:
            jobs.append(_Job("trait", api, tex_to_png_url(tex)))

    return jobs


def _download_all(jobs: list[_Job]) -> tuple[set[str], set[str]]:
    successes: set[str] = set()
    failures:  set[str] = set()
    with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as pool:
            futures = {pool.submit(_download_one, client, j): j for j in jobs}
            for f in as_completed(futures):
                j  = futures[f]
                ok = f.result()
                (successes if ok else failures).add(j.api_name)
    return successes, failures


def _download_one(client: httpx.Client, job: _Job) -> bool:
    target = sprite_for(job.api_name)
    if target.exists() and target.stat().st_size > 0:
        return True  # already cached
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
