"""Download Set-N champion tile icons, item icons, and trait icons from
Community Dragon for template matching.

Usage:
    py assets/fetch_images.py                # current set (auto-detect)
    py assets/fetch_images.py --set 17       # specific set

Output:
    assets/champions/<ApiName>.png
    assets/items/<ApiName>.png
    assets/traits/<ApiName>.png
    assets/manifest.json   (name → {api_name, cost, traits, file})

Community Dragon asset path convention:
    game asset path  :  ASSETS/UX/TFT/.../Name.tex
    CDN url          :  https://raw.communitydragon.org/latest/game/assets/ux/tft/.../name.png
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

CD_JSON = "https://raw.communitydragon.org/latest/cdragon/tft/en_us.json"
CD_GAME = "https://raw.communitydragon.org/latest/game/"
ROOT = Path(__file__).parent
MANIFEST_PATH = ROOT / "manifest.json"


def asset_url(game_path: str) -> str:
    """ASSETS/UX/.../Foo.tex  →  CDN url (lowercased, .png)."""
    if not game_path:
        return ""
    p = game_path.lower()
    for ext in (".tex", ".dds", ".tga"):
        if p.endswith(ext):
            p = p[: -len(ext)] + ".png"
            break
    return CD_GAME + p


def pick_champ_icon(champ: dict) -> str:
    """Prefer the shop/HUD tile; fall back to square, then splash."""
    return champ.get("tileIcon") or champ.get("squareIcon") or champ.get("icon") or ""


def download(url: str, out: Path, session: requests.Session) -> bool:
    if out.exists() and out.stat().st_size > 0:
        return True
    try:
        r = session.get(url, timeout=30)
        if r.status_code != 200:
            return False
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(r.content)
        return True
    except requests.RequestException:
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", dest="set_id", default=None)
    parser.add_argument("--skip-items", action="store_true")
    parser.add_argument("--skip-augments", action="store_true")
    args = parser.parse_args()

    print(f"Fetching {CD_JSON} ...")
    data = requests.get(CD_JSON, timeout=30).json()

    sets = data.get("sets", {})
    if args.set_id:
        set_id = args.set_id
    else:
        numeric = [k for k in sets if k.replace(".", "").isdigit()]
        set_id = max(numeric, key=lambda k: float(k))
    print(f"Using set: {set_id}")
    set_data = sets[set_id]

    session = requests.Session()
    manifest: dict = {"set": set_id, "champions": {}, "items": {}, "traits": {}, "augments": {}}

    # Champions
    champ_dir = ROOT / "champions"
    print(f"\n[champions] → {champ_dir}")
    ok = fail = 0
    for champ in set_data.get("champions", []):
        api = champ.get("apiName")
        name = champ.get("name")
        if not api or not name:
            continue
        icon = pick_champ_icon(champ)
        if not icon:
            fail += 1
            continue
        out = champ_dir / f"{api}.png"
        if download(asset_url(icon), out, session):
            manifest["champions"][name] = {
                "api_name": api,
                "cost": champ.get("cost"),
                "traits": champ.get("traits", []),
                "file": str(out.relative_to(ROOT.parent)).replace("\\", "/"),
            }
            ok += 1
        else:
            fail += 1
    print(f"  ok={ok} fail={fail}")

    # Traits (smaller set, always fetch)
    trait_dir = ROOT / "traits"
    print(f"\n[traits] → {trait_dir}")
    ok = fail = 0
    for trait in set_data.get("traits", []):
        api = trait.get("apiName")
        name = trait.get("name")
        icon = trait.get("icon")
        if not (api and name and icon):
            fail += 1
            continue
        out = trait_dir / f"{api}.png"
        if download(asset_url(icon), out, session):
            manifest["traits"][name] = {
                "api_name": api,
                "file": str(out.relative_to(ROOT.parent)).replace("\\", "/"),
            }
            ok += 1
        else:
            fail += 1
    print(f"  ok={ok} fail={fail}")

    # Items + augments (global, not per-set)
    # Items array contains both completed items and augments; separate by icon path.
    if not args.skip_items:
        item_dir = ROOT / "items"
        aug_dir = ROOT / "augments"
        print(f"\n[items + augments] → {item_dir}, {aug_dir}")
        ok = fail = 0
        for item in data.get("items", []):
            api = item.get("apiName")
            name = item.get("name")
            icon = item.get("icon", "") or ""
            if not (api and name and icon):
                continue
            icon_low = icon.lower()
            is_augment = "augment" in icon_low or "hexcore" in icon_low
            if is_augment and args.skip_augments:
                continue
            target_dir = aug_dir if is_augment else item_dir
            target_bucket = "augments" if is_augment else "items"
            out = target_dir / f"{api}.png"
            if download(asset_url(icon), out, session):
                manifest[target_bucket][name] = {
                    "api_name": api,
                    "file": str(out.relative_to(ROOT.parent)).replace("\\", "/"),
                }
                ok += 1
            else:
                fail += 1
        print(f"  ok={ok} fail={fail}")

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nManifest → {MANIFEST_PATH}")
    print(f"  champions={len(manifest['champions'])}  traits={len(manifest['traits'])}  "
          f"items={len(manifest['items'])}  augments={len(manifest['augments'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
