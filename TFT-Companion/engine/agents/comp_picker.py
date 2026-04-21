"""Agent 2 — CompPicker (Sonnet LLM, <5s).

Scores all archetypes by game-state fit (rule engine), passes top 5 to
Sonnet for reasoning, returns top 3 CompOption objects.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import anthropic
import yaml

from engine.agents.base import AgentBase, AgentResult
from engine.agents.schemas import CompOption, CompPickerResult

log = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_ARCHETYPES_PATH = Path(__file__).parent.parent / "knowledge" / "archetypes.yaml"
_ARCHETYPES_CACHE: dict | None = None


class CompPickerAgent(AgentBase):
    name = "comp_picker"
    timeout_ms = 5000  # Sonnet is slower than Haiku

    async def _run_impl(self, ctx: Any) -> CompPickerResult:
        archetypes = _load_archetypes()
        scored = _score_archetypes(ctx, archetypes)
        top5 = scored[:5]
        if not top5:
            return CompPickerResult(agent_name="comp_picker", used_fallback=True)
        return await _llm_rank(ctx, top5, archetypes)

    def _fallback(self, ctx: Any) -> AgentResult:
        archetypes = _load_archetypes()
        scored = _score_archetypes(ctx, archetypes)
        return _fallback_result(scored, archetypes)


# ── YAML loader ───────────────────────────────────────────────────────────────

def _load_archetypes(path: Path | None = None) -> dict:
    global _ARCHETYPES_CACHE
    if _ARCHETYPES_CACHE is not None and path is None:
        return _ARCHETYPES_CACHE
    target = path or _ARCHETYPES_PATH
    with target.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if path is None:
        _ARCHETYPES_CACHE = data
    return data


def reset_archetypes_cache() -> None:
    global _ARCHETYPES_CACHE
    _ARCHETYPES_CACHE = None


# ── Scoring ───────────────────────────────────────────────────────────────────

def _score_archetypes(ctx: Any, archetypes: dict) -> list[tuple]:
    """Return list of (score, arch_id, arch_data) sorted descending."""
    board_apis = {s.get("api_name", "") for s in (ctx.board_slots or [])}
    augments_lower = {a.lower() for a in (ctx.augments_picked or [])}

    scored = []
    for arch_id, arch in (archetypes.get("archetypes") or {}).items():
        score = _compute_fit(ctx, arch, board_apis, augments_lower)
        scored.append((score, arch_id, arch))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def _compute_fit(ctx: Any, arch: dict, board_apis: set, augments_lower: set) -> float:
    core_units: list[str] = arch.get("core_units", [])

    # Unit overlap: fraction of core units already on board
    unit_overlap = (
        len(board_apis & set(core_units)) / len(core_units)
        if core_units else 0.0
    )

    # Aug fit: bonus if any picked augment matches this comp's augment pool
    comp_augs: set[str] = set()
    for tier_augs in (arch.get("augments") or {}).values():
        for aug in (tier_augs or []):
            comp_augs.add(aug.lower())
    aug_fit = 1.0 if augments_lower & comp_augs else 0.0

    # Stage gate penalty: comp not ready yet
    stage_gate = arch.get("stage_gate", [1, 1])
    stage_penalty = 0.15 if tuple(ctx.stage) < tuple(stage_gate) else 0.0

    # Contest penalty: popular comps risk duplication
    contest_penalty = arch.get("contest_rate", 0.0) * 0.15

    score = unit_overlap * 0.55 + aug_fit * 0.25 - stage_penalty - contest_penalty
    return round(max(0.0, score), 4)


# ── LLM reasoning ─────────────────────────────────────────────────────────────

async def _llm_rank(ctx: Any, top5: list[tuple], archetypes: dict) -> CompPickerResult:
    client = anthropic.AsyncAnthropic()
    msg = await client.messages.create(
        model=_MODEL,
        max_tokens=800,
        messages=[{"role": "user", "content": _build_prompt(ctx, top5)}],
    )
    return _parse_llm_response(msg.content[0].text, top5, archetypes)


def _build_prompt(ctx: Any, top5: list[tuple]) -> str:
    board_apis = [s.get("api_name", "") for s in (ctx.board_slots or [])]
    options = "\n".join(
        f"  [{arch_id}] {arch.get('display_name', arch_id)} "
        f"(tier={arch.get('tier', '?')}, fit={score:.2f}, "
        f"carry={arch.get('primary_carry', '?')})"
        for score, arch_id, arch in top5
    )

    return f"""You are a TFT coach. Re-rank these comps and explain why.

Player state:
- HP: {ctx.hp} | Gold: {ctx.gold} | Level: {ctx.level}
- Stage: {ctx.stage[0]}-{ctx.stage[1]} | Streak: {ctx.streak}
- Board: {board_apis}
- Augments: {ctx.augments_picked}

Top comp candidates (pre-scored):
{options}

Return a JSON ARRAY of exactly 3 items, best first:
[
  {{
    "archetype_id": "...",
    "why_this_fits": "one sentence why this is best for this player RIGHT NOW",
    "why_not_the_others": "one sentence on the key tradeoff vs alternatives"
  }}
]

Return ONLY the JSON array, no markdown."""


def _parse_llm_response(raw: str, top5: list[tuple], archetypes: dict) -> CompPickerResult:
    try:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON array in response")
        data: list[dict] = json.loads(raw[start:end])
        if not data:
            raise ValueError("Empty JSON array")

        arch_data: dict = archetypes.get("archetypes") or {}
        options: list[CompOption] = []

        for item in data[:3]:
            arch_id = item.get("archetype_id", "")
            arch = arch_data.get(arch_id)
            if not arch:
                continue
            opt = _build_comp_option(arch_id, arch, top5)
            opt.why_this_fits = item.get("why_this_fits", "")
            opt.why_not_the_others = item.get("why_not_the_others", "")
            options.append(opt)

        if not options:
            raise ValueError("No valid archetype_ids in LLM response")

        return CompPickerResult(
            agent_name="comp_picker",
            top_comp=options[0],
            alternates=options[1:],
            stage_gate=str(top5[0][2].get("stage_gate", "")),
        )
    except Exception as exc:
        log.warning("CompPicker LLM parse failed: %s | raw=%.200s", exc, raw)
        return _fallback_result(top5, archetypes)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_comp_option(arch_id: str, arch: dict, scored: list[tuple]) -> CompOption:
    fit_score = next((s for s, aid, _ in scored if aid == arch_id), 0.0)
    return CompOption(
        archetype_id=arch_id,
        display_name=arch.get("display_name", arch_id),
        tier=arch.get("tier", "B"),
        fit_score=fit_score,
        primary_carry=arch.get("primary_carry", ""),
        secondary_carry=arch.get("secondary_carry"),
    )


def _fallback_result(scored: list[tuple], archetypes: dict) -> CompPickerResult:
    arch_data: dict = archetypes.get("archetypes") or {}
    options: list[CompOption] = []

    for score, arch_id, arch in scored[:3]:
        if not arch_data.get(arch_id):
            continue
        opt = _build_comp_option(arch_id, arch, scored)
        opt.why_this_fits = f"Rule engine: fit score {score:.2f}."
        opt.why_not_the_others = "LLM unavailable — ranked by rule engine."
        options.append(opt)

    if not options:
        return CompPickerResult(agent_name="comp_picker", used_fallback=True)

    return CompPickerResult(
        agent_name="comp_picker",
        used_fallback=True,
        top_comp=options[0],
        alternates=options[1:],
    )
