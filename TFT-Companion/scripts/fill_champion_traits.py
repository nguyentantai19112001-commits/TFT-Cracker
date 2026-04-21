"""fill_champion_traits.py — Populate champion traits in engine/knowledge/set_17.yaml.

Source:  TFT-Companion/data/set_data.json  (Community Dragon, Set 17)
Target:  TFT-Companion/engine/knowledge/set_17.yaml

Match key: JSON outer-dict display name == YAML champion `name:` field.
           Exact string match only. Case or whitespace differences are logged
           as conflicts and left untouched.

Uses ruamel.yaml to preserve YAML comments, ordering, and inline-block style.

Safeguards:
  - Does NOT overwrite existing non-empty traits lists.
  - Skips champions whose filtered trait list is empty (guards against
    artifact-only trait lists after filtering).
  - Prints warnings to stderr for: no JSON match, conflicts, empty-after-filter.
  - Exits 1 if source file missing or YAML unparseable.

No --force flag. The safeguards exist for a reason.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ruamel.yaml import YAML

# ---------------------------------------------------------------------------
# Paths (relative to this script's parent directory = TFT-Companion/)
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent.parent  # TFT-Companion/
SOURCE_JSON = _HERE / "data" / "set_data.json"
TARGET_YAML = _HERE / "engine" / "knowledge" / "set_17.yaml"

# ---------------------------------------------------------------------------
# Artifact traits: UI artifacts that are not real game traits.
# Filter these out before writing to YAML.
# ---------------------------------------------------------------------------
ARTIFACT_TRAITS: set[str] = {"Choose Trait"}


def main() -> int:
    # ── Load source JSON ────────────────────────────────────────────────────
    if not SOURCE_JSON.exists():
        print(f"CRITICAL: source file not found: {SOURCE_JSON}", file=sys.stderr)
        return 1

    with SOURCE_JSON.open(encoding="utf-8") as f:
        try:
            source = json.load(f)
        except json.JSONDecodeError as exc:
            print(f"CRITICAL: cannot parse {SOURCE_JSON}: {exc}", file=sys.stderr)
            return 1

    json_champions: dict = source.get("champions", {})

    # ── Load target YAML (ruamel preserves comments and formatting) ─────────
    if not TARGET_YAML.exists():
        print(f"CRITICAL: target YAML not found: {TARGET_YAML}", file=sys.stderr)
        return 1

    ryaml = YAML()
    ryaml.preserve_quotes = True
    ryaml.default_flow_style = None

    with TARGET_YAML.open(encoding="utf-8") as f:
        try:
            doc = ryaml.load(f)
        except Exception as exc:
            print(f"CRITICAL: cannot parse {TARGET_YAML}: {exc}", file=sys.stderr)
            return 1

    yaml_champions: list = doc.get("champions", [])

    # ── Counters ────────────────────────────────────────────────────────────
    n_populated = 0
    n_already_had = 0
    n_no_match = 0
    n_conflicts = 0
    n_empty_after_filter = 0
    total = len(yaml_champions)

    # ── Migration loop ──────────────────────────────────────────────────────
    for champ in yaml_champions:
        name: str = champ.get("name", "")

        # Guard: already has traits populated — do not overwrite.
        existing = champ.get("traits")
        if existing is not None and len(existing) > 0:
            n_already_had += 1
            continue

        # Find JSON entry by exact display-name match.
        if name not in json_champions:
            print(
                f"WARNING: no JSON match for YAML champion '{name}' — skipping",
                file=sys.stderr,
            )
            n_no_match += 1
            continue

        json_entry = json_champions[name]
        raw_traits: list[str] = json_entry.get("traits", [])

        # Filter artifact traits.
        traits = [t for t in raw_traits if t not in ARTIFACT_TRAITS]

        # Guard: empty after filtering — warn and skip (don't write []).
        if not traits:
            print(
                f"WARNING: '{name}' has no traits after filtering artifacts "
                f"(raw={raw_traits}) — skipping to avoid writing empty list",
                file=sys.stderr,
            )
            n_empty_after_filter += 1
            continue

        # Conflict check: existing non-empty traits differ from JSON.
        # (existing is None or [] at this point, so this guards future edits)
        if existing is not None and len(existing) > 0 and set(existing) != set(traits):
            print(
                f"CONFLICT: '{name}' YAML traits {existing!r} != JSON traits {traits!r} — skipping",
                file=sys.stderr,
            )
            n_conflicts += 1
            continue

        # Write traits list to the YAML dict node.
        champ["traits"] = traits
        n_populated += 1

    # ── Write updated YAML back ─────────────────────────────────────────────
    with TARGET_YAML.open("w", encoding="utf-8") as f:
        ryaml.dump(doc, f)

    # ── Summary ─────────────────────────────────────────────────────────────
    print(f"{n_populated}/{total} champions populated")
    print(f"{n_already_had}/{total} already had traits (skipped)")
    print(f"{n_no_match}/{total} had no JSON match")
    if n_empty_after_filter:
        print(f"{n_empty_after_filter}/{total} skipped — empty after artifact filter (see stderr)")
    if n_conflicts:
        print(f"{n_conflicts} conflicts (logged above)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
