"""Agent 4 — TempoAgent (Haiku LLM, <2s).

Decides the single most important tempo action for this round.
Rule pre-filter handles deterministic cases; Haiku resolves ambiguous ones.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from engine.agents.base import AgentBase, AgentResult
from engine.agents.schemas import TempoAgentResult

log = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"

_TEMPLATES = [
    "Level to {N}",
    "Roll down for {unit}",
    "Hold — build interest",
    "Slam {item} on {unit}",
    "Pivot to {comp}",
    "All-in roll at level {N}",
    "Stabilize with {unit}",
]


class TempoAgentAgent(AgentBase):
    name = "tempo_agent"
    timeout_ms = 2000

    async def _run_impl(self, ctx: Any) -> TempoAgentResult:
        rule = _rule_filter(ctx)
        if rule is not None:
            return rule
        return await _llm_tempo(ctx)

    def _fallback(self, ctx: Any) -> AgentResult:
        rule = _rule_filter(ctx)
        if rule is not None:
            return rule
        return TempoAgentResult(
            agent_name="tempo_agent",
            used_fallback=True,
            verdict_template="Hold — build interest",
            verdict_slots={},
            verdict_display="→ Hold — build interest",
            subline="Fallback: hold econ this round.",
            action_priority="medium",
        )


def _rule_filter(ctx: Any) -> TempoAgentResult | None:
    """Return a deterministic verdict when one clearly applies; None otherwise."""
    stage_major = ctx.stage[0]

    # Early-game winning streak: protect gold
    if stage_major <= 2 and ctx.hp > 80 and ctx.streak > 2:
        return _make_result(
            "Hold — build interest", {},
            "→ Hold — build interest",
            f"Streak {ctx.streak} at {ctx.stage[0]}-{ctx.stage[1]}: protect gold.",
            "high",
        )

    # Rich and healthy late-game: fast level
    if stage_major >= 4 and ctx.gold > 50 and ctx.hp > 40 and ctx.level < 9:
        target = ctx.level + 1
        return _make_result(
            "Level to {N}", {"N": target},
            f"→ Level to {target}",
            f"Gold {ctx.gold} at stage {ctx.stage[0]}-{ctx.stage[1]}: fast level.",
            "high",
        )

    # Dying in late-game: roll to stabilize
    if stage_major >= 4 and ctx.hp < 40:
        unit = _top_unit_name(ctx)
        if unit:
            return _make_result(
                "Roll down for {unit}", {"unit": unit},
                f"→ Roll down for {unit}",
                f"HP {ctx.hp} — stabilize before next combat.",
                "critical",
            )
        return _make_result(
            "All-in roll at level {N}", {"N": ctx.level},
            f"→ All-in roll at level {ctx.level}",
            f"HP {ctx.hp} — all-in now.",
            "critical",
        )

    return None  # ambiguous — send to LLM


async def _llm_tempo(ctx: Any) -> TempoAgentResult:
    client = anthropic.AsyncAnthropic()
    msg = await client.messages.create(
        model=_MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": _build_prompt(ctx)}],
    )
    return _parse_llm_response(msg.content[0].text)


def _build_prompt(ctx: Any) -> str:
    board_names = [
        s.get("display_name") or s.get("api_name", "?")
        for s in (ctx.board_slots or [])
    ]
    board_str = ", ".join(board_names) if board_names else "empty"
    template_list = "\n".join(f'  - "{t}"' for t in _TEMPLATES)

    return f"""You are a TFT (Teamfight Tactics) coach. Choose the single best tempo action.

Game state:
- HP: {ctx.hp} | Gold: {ctx.gold} | Level: {ctx.level}
- Stage: {ctx.stage[0]}-{ctx.stage[1]} | Streak: {ctx.streak}
- Board strength: {ctx.board_strength:.0%}
- Board units: {board_str}

Valid action templates (pick exactly one):
{template_list}

Return ONLY valid JSON (no markdown):
{{"template": "...", "slots": {{}}, "subline": "one sentence why", "priority": "high"}}

Rules:
- priority must be one of: critical, high, medium, low
- slots must fill all {{placeholders}} in the chosen template
- If no placeholder, slots is {{}}"""


def _parse_llm_response(raw: str) -> TempoAgentResult:
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON in response")
        data = json.loads(raw[start:end])

        template = data.get("template", "Hold — build interest")
        slots = data.get("slots", {})
        priority = data.get("priority", "medium")
        subline = data.get("subline", "")

        if priority not in ("critical", "high", "medium", "low"):
            priority = "medium"

        return TempoAgentResult(
            agent_name="tempo_agent",
            verdict_template=template,
            verdict_slots=slots,
            verdict_display=_render_display(template, slots),
            subline=subline,
            action_priority=priority,
        )
    except Exception as exc:
        log.warning("TempoAgent parse failed: %s | raw=%.200s", exc, raw)
        return TempoAgentResult(
            agent_name="tempo_agent",
            used_fallback=True,
            verdict_template="Hold — build interest",
            verdict_slots={},
            verdict_display="→ Hold — build interest",
            subline="Parse error — defaulting to hold.",
            action_priority="medium",
        )


def _render_display(template: str, slots: dict) -> str:
    try:
        return f"→ {template.format(**slots)}"
    except (KeyError, ValueError):
        return f"→ {template}"


def _top_unit_name(ctx: Any) -> str | None:
    if not ctx.board_slots:
        return None
    top = max(ctx.board_slots, key=lambda s: s.get("cost", 1))
    return top.get("display_name") or top.get("api_name")


def _make_result(
    template: str,
    slots: dict,
    display: str,
    subline: str,
    priority: str,
) -> TempoAgentResult:
    return TempoAgentResult(
        agent_name="tempo_agent",
        verdict_template=template,
        verdict_slots=slots,
        verdict_display=display,
        subline=subline,
        action_priority=priority,
    )
