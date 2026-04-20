"""Fetch current-set TFT champion/item/trait data from Community Dragon.

Community Dragon mirrors Riot's game files and stays current with patches.
Run this whenever a new set or patch drops.

Usage:
    py fetch_community_dragon.py                 # current/highest set
    py fetch_community_dragon.py --set 17        # specific set

Output: data/set_data.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

CD_URL = "https://raw.communitydragon.org/latest/cdragon/tft/en_us.json"
OUT_PATH = Path(__file__).parent / "set_data.json"


def detect_current_set(data: dict) -> str:
    sets = data.get("sets", {})
    if not sets:
        raise RuntimeError("No 'sets' key in Community Dragon response")
    try:
        numeric_keys = [k for k in sets.keys() if k.replace(".", "").isdigit()]
        return max(numeric_keys, key=lambda k: float(k))
    except (ValueError, TypeError):
        return next(iter(sets.keys()))


def extract(data: dict, set_id: str) -> dict:
    sets = data.get("sets", {})
    if set_id not in sets:
        raise RuntimeError(
            f"Set {set_id} not found. Available: {sorted(sets.keys())}"
        )

    set_data = sets[set_id]

    champions: dict[str, dict] = {}
    for champ in set_data.get("champions", []):
        name = champ.get("name") or champ.get("apiName", "")
        if not name:
            continue
        champions[name] = {
            "cost": champ.get("cost"),
            "traits": champ.get("traits", []),
            "api_name": champ.get("apiName"),
        }

    traits: dict[str, dict] = {}
    for trait in set_data.get("traits", []):
        name = trait.get("name") or trait.get("apiName", "")
        if not name:
            continue
        traits[name] = {
            "description": trait.get("desc"),
            "effects": trait.get("effects", []),
            "api_name": trait.get("apiName"),
        }

    items: dict[str, dict] = {}
    for item in data.get("items", []):
        name = item.get("name") or item.get("apiName", "")
        if not name:
            continue
        items[name] = {
            "description": item.get("desc"),
            "composition": item.get("composition", []),
            "api_name": item.get("apiName"),
            "from": item.get("from", []),
        }

    return {
        "set": set_id,
        "set_name": set_data.get("name"),
        "patch": data.get("patch") or data.get("version"),
        "champions": champions,
        "traits": traits,
        "items": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", dest="set_id", default=None,
                        help="Override set ID (default: current)")
    args = parser.parse_args()

    print(f"Fetching {CD_URL} ...")
    resp = requests.get(CD_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    set_id = args.set_id or detect_current_set(data)
    print(f"Using set: {set_id}")

    extracted = extract(data, set_id)
    print(f"  {len(extracted['champions'])} champions")
    print(f"  {len(extracted['traits'])} traits")
    print(f"  {len(extracted['items'])} items")

    OUT_PATH.write_text(json.dumps(extracted, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
