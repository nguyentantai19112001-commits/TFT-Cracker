# TASK_03_TEMPLATE_FALLBACK.md — Deterministic fallback when LLM fails

> The tool must never hang on an LLM timeout or provider hiccup. If the
> advisor call fails, produce a deterministic verdict from the same
> structured state the LLM would have received.

---

## Goal

When `advisor.advise_stream()` times out (>2.5s for first token) or errors,
fall through to a deterministic template renderer that produces an
adequate verdict string from the top-1 recommender action + top-1 comp
candidate. UI never shows empty, never hangs, never crashes.

## Prereq checks

```bash
pytest -q                          # 112/112
git status                         # clean
```

## Files you may edit

- `advisor.py` (add fallback path)
- `templates.py` (new — deterministic verdict formatter)
- `tests/test_advisor_fallback.py` (new)
- `STATE.md`

**Do NOT edit:** recommender, comp_planner, schemas, overlay.

## The fallback renderer

```python
# templates.py
"""Deterministic verdict templates — used when LLM advisor fails.

Renders a plain-English verdict string from the top-ranked ActionCandidate
and top CompCandidate without any LLM call. Output quality is lower than
the LLM version but it's fast (<1ms), deterministic, and never fails.
"""
from __future__ import annotations
from schemas import (
    ActionCandidate, ActionType, CompCandidate, GameState, Fire, AdvisorVerdict,
)


def render_deterministic_verdict(
    state: GameState,
    top_action: ActionCandidate,
    top_comp: CompCandidate | None,
    fires: list[Fire],
) -> AdvisorVerdict:
    """Produce a reasonable verdict with zero LLM involvement."""
    one_liner = _render_one_liner(top_action, state)
    reasoning = _render_reasoning(top_action, top_comp, fires)
    tempo = _infer_tempo(state)

    return AdvisorVerdict(
        one_liner=one_liner,
        confidence="MEDIUM",   # deterministic fallback is never HIGH
        tempo_read=tempo,
        primary_action=top_action.action_type,
        chosen_candidate=top_action,
        reasoning=reasoning,
        considerations=[],
        warnings=["advisor LLM unavailable — using fallback verdict"],
        data_quality_note="deterministic fallback; no LLM call",
    )


def _render_one_liner(action: ActionCandidate, state: GameState) -> str:
    t = action.action_type
    p = action.params
    if t == ActionType.BUY:
        champ = p.get("champion", "unit")
        return f"Buy {champ} from shop."
    if t == ActionType.SELL:
        return f"Sell the {p.get('unit_name', 'flagged unit')} to free bench space."
    if t == ActionType.ROLL_TO:
        floor = p.get("gold_floor", 0)
        return f"Roll to {floor}g — looking for upgrades."
    if t == ActionType.LEVEL_UP:
        return f"Buy XP to reach level {state.level + 1}."
    if t == ActionType.HOLD_ECON:
        return f"Hold at {state.gold}g for interest."
    if t == ActionType.SLAM_ITEM:
        comps = p.get("components", ["?", "?"])
        carrier = p.get("carrier", "main carry")
        return f"Slam {comps[0]} + {comps[1]} on {carrier}."
    if t == ActionType.PIVOT_COMP:
        return f"Pivot to {p.get('archetype_id', 'alternative comp')}."
    return "Hold position, re-press F9 after shop refresh."


def _render_reasoning(
    action: ActionCandidate, top_comp: CompCandidate | None, fires: list[Fire],
) -> str:
    parts = [f"Top score: {action.total_score:.1f}"]
    if top_comp:
        parts.append(f"Target comp: {top_comp.archetype.display_name} "
                     f"(P(reach)={top_comp.p_reach:.0%})")
    crit_fires = [f for f in fires if f.severity >= 0.7]
    if crit_fires:
        parts.append(f"Active alerts: {', '.join(f.rule_id for f in crit_fires[:3])}")
    if action.reasoning_tags:
        parts.append(f"Tags: {', '.join(action.reasoning_tags[:4])}")
    return " | ".join(parts)


def _infer_tempo(state: GameState) -> str:
    """Rough tempo read from stage + level without LLM."""
    expected = _expected_level_for_stage(state.stage)
    if state.hp < 25:
        return "CRITICAL"
    if state.level < expected - 1:
        return "BEHIND"
    if state.level > expected + 1:
        return "AHEAD"
    return "ON_PACE"


def _expected_level_for_stage(stage: str) -> int:
    """Expected level for standard pace. Mirrors stage-key heuristics elsewhere."""
    mapping = {
        "2-1": 4, "2-5": 4, "3-1": 5, "3-2": 6, "3-5": 6,
        "4-1": 7, "4-2": 8, "4-5": 8, "5-1": 8, "5-5": 9, "6-1": 9,
    }
    return mapping.get(stage, 6)
```

## Advisor integration

In `advisor.py`, wrap the existing streaming call with a timeout + fallback:

```python
# advisor.py (conceptual — adapt to actual structure)
import asyncio
import time
from templates import render_deterministic_verdict

ADVISOR_FIRST_TOKEN_TIMEOUT_S = 2.5
ADVISOR_TOTAL_TIMEOUT_S = 8.0


def advise_stream(state, fires, actions, comps, client, capture_id=None):
    """Streaming advisor with deterministic fallback.

    Yields:
      ("one_liner", str)
      ("reasoning", str)
      ("final", {"verdict": AdvisorVerdict, "__meta__": {...}})

    On LLM failure (timeout, exception, empty stream), yields the same
    event shape but populated from the deterministic template renderer.
    """
    try:
        yield from _advise_stream_llm(state, fires, actions, comps, client, capture_id)
    except (TimeoutError, Exception) as e:
        # Structured log, then fall through
        import logging
        logging.warning("advisor LLM failed, using deterministic fallback: %s", e)

        top_action = actions[0] if actions else None
        top_comp = comps[0] if comps else None

        if top_action is None:
            # No candidates at all — emit a safe no-op
            verdict = AdvisorVerdict(
                one_liner="Take a moment — press F9 again for advice.",
                confidence="LOW",
                tempo_read="ON_PACE",
                primary_action=ActionType.HOLD_ECON,
                chosen_candidate=None,  # downstream must handle None
                reasoning="Recommender returned no candidates.",
                warnings=["no actions available"],
            )
        else:
            verdict = render_deterministic_verdict(state, top_action, top_comp, fires)

        yield ("one_liner", verdict.one_liner)
        yield ("reasoning", verdict.reasoning)
        yield ("final", {
            "verdict": verdict,
            "__meta__": {"source": "deterministic_fallback", "error": str(e)},
        })
```

**Important:** the existing `_advise_stream_llm` implementation is whatever
advisor.py already does today. This task wraps it, it doesn't rewrite it.

If the advisor code structure makes wrapping awkward (e.g. it's a generator
that's already partially yielded before erroring), handle partial-yield
recovery: if we yielded `one_liner` successfully but then the LLM hangs on
`reasoning`, still run the fallback for `reasoning` + `final` only, don't
re-emit `one_liner`.

## Tests

```python
# tests/test_advisor_fallback.py
import pytest
from unittest.mock import patch, MagicMock
from advisor import advise_stream
from templates import render_deterministic_verdict
from schemas import GameState, ActionCandidate, ActionScores, ActionType


def _fixture_state():
    return GameState(stage="3-2", gold=30, hp=70, level=6,
                     xp_current=5, xp_needed=36, streak=0, set_id="17")


def _fixture_action():
    return ActionCandidate(
        action_type=ActionType.ROLL_TO,
        params={"gold_floor": 20},
        scores=ActionScores(tempo=1, econ=-1, hp_risk=0, board_strength=1, pivot_value=0),
        total_score=1.0,
        human_summary="Roll to 20g",
    )


def test_deterministic_verdict_roll():
    v = render_deterministic_verdict(_fixture_state(), _fixture_action(), None, [])
    assert "20" in v.one_liner
    assert v.primary_action == ActionType.ROLL_TO
    assert v.confidence == "MEDIUM"


def test_deterministic_verdict_never_empty():
    """Every ActionType must produce a non-empty one_liner."""
    from schemas import ActionCandidate, ActionScores
    for at in ActionType:
        action = ActionCandidate(
            action_type=at, params={},
            scores=ActionScores(tempo=0, econ=0, hp_risk=0, board_strength=0, pivot_value=0),
            total_score=0.0, human_summary="test",
        )
        v = render_deterministic_verdict(_fixture_state(), action, None, [])
        assert v.one_liner, f"ActionType {at} produced empty one_liner"


def test_advisor_timeout_falls_through(monkeypatch):
    """When LLM raises TimeoutError, fallback path runs and emits events."""
    from advisor import _advise_stream_llm

    def always_timeout(*args, **kwargs):
        raise TimeoutError("simulated first-token timeout")

    monkeypatch.setattr("advisor._advise_stream_llm", always_timeout)

    events = list(advise_stream(
        state=_fixture_state(), fires=[], actions=[_fixture_action()], comps=[],
        client=None, capture_id=None,
    ))

    event_types = [e[0] for e in events]
    assert "one_liner" in event_types
    assert "final" in event_types
    final_event = next(e for e in events if e[0] == "final")
    assert final_event[1]["__meta__"]["source"] == "deterministic_fallback"


def test_advisor_exception_falls_through(monkeypatch):
    """Any LLM exception (not just timeout) triggers fallback."""
    def always_500(*args, **kwargs):
        raise RuntimeError("simulated API 500")

    monkeypatch.setattr("advisor._advise_stream_llm", always_500)

    events = list(advise_stream(
        state=_fixture_state(), fires=[], actions=[_fixture_action()], comps=[],
        client=None, capture_id=None,
    ))
    assert any(e[0] == "final" for e in events)


def test_advisor_empty_candidates_produces_safe_message():
    """If recommender returns no actions, fallback still produces something."""
    # This edge case is rare but must not crash
    def always_fail(*args, **kwargs):
        raise RuntimeError()

    with patch("advisor._advise_stream_llm", side_effect=always_fail):
        events = list(advise_stream(
            state=_fixture_state(), fires=[], actions=[], comps=[],
            client=None, capture_id=None,
        ))
    final = next(e for e in events if e[0] == "final")
    assert "no actions" in final[1]["verdict"].warnings[0].lower() or \
           final[1]["verdict"].confidence == "LOW"
```

## Acceptance gate

1. `pytest -q` shows 117/117 passing (112 + 5 new).
2. Manual test: simulate advisor failure by temporarily raising in
   `_advise_stream_llm`, confirm UI shows fallback verdict within 3 seconds.
3. Happy path unchanged: existing advisor tests from Phase 6 still pass.
4. No new top-level deps introduced.

## Commit message

```
Task 3: deterministic fallback when advisor LLM fails

- templates.py renders a plain verdict from top ActionCandidate without any LLM
- advisor.advise_stream wraps LLM call in try/except, falls through on failure
- 5 new tests covering timeout, exception, and empty-candidate paths

Tests: 112 → 117 passing. Overlay can never hang on LLM issues.
```
