"""fetch_set_assets.py — Build the augie-v2 template library for one set/patch.

Usage:
    py tools/fetch_set_assets.py --set 17 --patch 17.1

Sources:
    - Champion portraits: ../assets/champions/ (already downloaded by v1)
    - Champion→cost mapping: ../assets/manifest.json
    - Items: Community Dragon (fetched if not cached)
    - Augments: Community Dragon (fetched if not cached)

Output:
    assets/templates/set_{N}/patch_{P}/
        champions/{1..5}_cost/{Name}.png
        items/completed/{ItemName}.png
        augments/{AugmentId}.png
        manifest.json  (hashes + dimensions)

Run again each patch — idempotent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.request
from pathlib import Path

_AUGIE_ROOT = Path(__file__).resolve().parent.parent
_V1_ASSETS = _AUGIE_ROOT.parent / "assets"
_V1_MANIFEST = _V1_ASSETS / "manifest.json"

# Pinned to patch — never use /latest/ (staleness lag at set boundaries).
# Import from knowledge to keep single source of truth; inline fallback
# for when this script is run standalone before knowledge is importable.
try:
    from knowledge import CDRAGON_PATCH, CDRAGON_BASE
except ImportError:
    CDRAGON_PATCH = "17.1"
    CDRAGON_BASE  = f"https://raw.communitydragon.org/{CDRAGON_PATCH}"

CDRAGON_JSON = f"{CDRAGON_BASE}/cdragon/tft/en_us.json"
CDRAGON_GAME = f"{CDRAGON_BASE}/game/"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()[:12]


def _img_size(path: Path) -> tuple[int, int]:
    try:
        import cv2  # type: ignore
        img = cv2.imread(str(path))
        if img is not None:
            return img.shape[1], img.shape[0]  # w, h
    except ImportError:
        pass
    return (0, 0)


def _asset_url(game_path: str) -> str:
    """Convert ASSETS/UX/TFT/.../Foo.tex → CDN URL (lowercased, .png)."""
    if not game_path:
        return ""
    p = game_path.lower()
    for ext in (".tex", ".dds", ".tga"):
        if p.endswith(ext):
            p = p[: -len(ext)] + ".png"
            break
    return CDRAGON_GAME + p


def _fetch_url(url: str, dest: Path) -> bool:
    """Download url to dest. Return True if written, False if skipped (already exists)."""
    if dest.exists():
        return False
    try:
        import requests  # type: ignore
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            return False
        dest.write_bytes(r.content)
        return True
    except Exception as e:
        print(f"  WARN: could not fetch {url}: {e}")
        return False


def build_champion_templates(template_root: Path, v1_manifest: dict) -> dict:
    """Copy champion PNGs from v1 assets into cost-tier folders."""
    results: dict[str, dict] = {}
    playable_costs = {1, 2, 3, 4, 5}

    for name, info in v1_manifest["champions"].items():
        cost = info.get("cost", 0)
        if cost not in playable_costs:
            continue
        src = _AUGIE_ROOT.parent / info["file"]
        if not src.exists():
            print(f"  WARN: missing source for {name}: {src}")
            continue
        folder = template_root / "champions" / f"{cost}_cost"
        safe_name = name.replace("'", "").replace(" ", "_").replace("&", "and")
        dest = folder / f"{safe_name}.png"
        if not dest.exists():
            shutil.copy2(src, dest)
        results[name] = {
            "file": str(dest.relative_to(_AUGIE_ROOT)),
            "cost": cost,
            "traits": info.get("traits", []),
            "sha256": _sha256(dest),
            "size_px": _img_size(dest),
        }
    return results


def build_item_templates(template_root: Path, cd_data: dict | None) -> dict:
    """Fetch item icons from Community Dragon using game asset paths."""
    items_dir = template_root / "items" / "completed"
    aug_dir = template_root / "augments"
    item_results: dict[str, dict] = {}
    aug_results: dict[str, dict] = {}

    if not cd_data:
        print("  (skipped — no CD JSON data)")
        return item_results

    ok = fail = 0
    for item in cd_data.get("items", []):
        api = item.get("apiName", "")
        name = item.get("name", "")
        icon = item.get("icon", "") or ""
        if not (api and name and icon):
            continue
        icon_low = icon.lower()
        is_augment = "augment" in icon_low or "hexcore" in icon_low
        target_dir = aug_dir if is_augment else items_dir
        dest = target_dir / f"{api}.png"
        url = _asset_url(icon)
        if _fetch_url(url, dest):
            ok += 1
        if dest.exists():
            entry = {
                "api_name": api,
                "file": str(dest.relative_to(_AUGIE_ROOT)),
                "sha256": _sha256(dest),
                "size_px": _img_size(dest),
            }
            if is_augment:
                aug_results[name] = entry
            else:
                item_results[name] = entry
        else:
            fail += 1

    print(f"  {len(item_results)} items, {len(aug_results)} augments (fetched or cached; {fail} failed)")
    return item_results


def build_star_templates(template_root: Path) -> dict:
    """Star crown templates — referenced from v1 assets if they exist, else placeholder."""
    stars_dir = template_root / "stars"
    results: dict[str, dict] = {}
    # Stars are small UI overlays — typically extracted from screenshots manually.
    # Placeholder entry for the manifest; populate in 3.5c when we calibrate.
    for star in [1, 2, 3]:
        key = f"{star}_star"
        dest = stars_dir / f"{key}.png"
        if dest.exists():
            results[key] = {
                "file": str(dest.relative_to(_AUGIE_ROOT)),
                "sha256": _sha256(dest),
                "size_px": _img_size(dest),
            }
        else:
            results[key] = {"file": str(dest), "sha256": None, "size_px": (0, 0),
                            "note": "TODO: capture from calibration screenshot in 3.5c"}
    return results


def write_manifest(template_root: Path, champs: dict, items: dict, stars: dict,
                   set_id: str, patch: str) -> None:
    manifest = {
        "set": set_id,
        "patch": patch,
        "champions": champs,
        "items": items,
        "augments": {},  # populated when augment icons are fetched
        "stars": stars,
        "note": "Augments: run with --fetch-augments once Community Dragon augment list is verified",
    }
    (template_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"  manifest written: {template_root / 'manifest.json'}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", default="17")
    parser.add_argument("--patch", default="17.1")
    parser.add_argument("--fetch-augments", action="store_true",
                        help="Also attempt to fetch augment icons (slow, requires network)")
    args = parser.parse_args()

    if not _V1_MANIFEST.exists():
        raise FileNotFoundError(f"v1 manifest not found at {_V1_MANIFEST}")

    v1_manifest = json.loads(_V1_MANIFEST.read_text(encoding="utf-8"))

    patch_safe = args.patch.replace(".", "_")
    template_root = _AUGIE_ROOT / "assets" / "templates" / f"set_{args.set}" / f"patch_{patch_safe}"
    template_root.mkdir(parents=True, exist_ok=True)
    for sub in ["champions/1_cost", "champions/2_cost", "champions/3_cost",
                "champions/4_cost", "champions/5_cost", "items/completed",
                "augments", "stars"]:
        (template_root / sub).mkdir(parents=True, exist_ok=True)

    print(f"Building template library for Set {args.set} patch {args.patch}...")

    print("  [1/4] Champion portraits...")
    champs = build_champion_templates(template_root, v1_manifest)
    print(f"  {len(champs)} champions organized by cost tier")

    print("  [1.5] Fetching Community Dragon JSON (for item/augment icons)...")
    cd_data: dict | None = None
    try:
        import requests  # type: ignore
        r = requests.get(CDRAGON_JSON, timeout=30)
        if r.status_code == 200:
            cd_data = r.json()
            print(f"  CD JSON OK — {len(cd_data.get('items', []))} items total")
        else:
            print(f"  WARN: CD JSON returned {r.status_code}")
    except Exception as e:
        print(f"  WARN: could not fetch CD JSON: {e}")

    print("  [2/4] Item + augment icons...")
    items = build_item_templates(template_root, cd_data)

    print("  [3/4] Star templates...")
    stars = build_star_templates(template_root)
    print(f"  {len(stars)} star templates (placeholders for uncaptured)")

    print("  [4/4] Writing manifest...")
    write_manifest(template_root, champs, items, stars, args.set, args.patch)

    # Smoke check
    expected_costs = {1: 14, 2: 13, 3: 13, 4: 13, 5: 9}  # 10 total 5-cost, Zed gated
    by_cost: dict[int, list] = {}
    for name, info in champs.items():
        c = info["cost"]
        by_cost.setdefault(c, []).append(name)
    for cost, expected in expected_costs.items():
        actual = len(by_cost.get(cost, []))
        status = "OK" if actual == expected else f"WARN (expected {expected})"
        print(f"  {cost}-cost: {actual} champions — {status}")

    print("\nDone. Run `py tools/fetch_set_assets.py --fetch-augments` to add augment icons.")


if __name__ == "__main__":
    main()
