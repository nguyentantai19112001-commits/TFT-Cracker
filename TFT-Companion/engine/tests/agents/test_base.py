"""Tests for engine/agents/base.py — AgentBase, AgentResult, AgentError."""
from __future__ import annotations

import asyncio
import pytest

from engine.agents.base import AgentBase, AgentError, AgentResult
from engine.agents.schemas import CoachResult, SituationalFrameResult


# ── AgentResult ───────────────────────────────────────────────────────────────

def test_agent_result_defaults():
    r = AgentResult()
    assert r.agent_name == ""
    assert r.used_fallback is False
    assert r.error is None


def test_agent_result_empty_factory():
    r = AgentResult.empty("test_agent")
    assert r.agent_name == "test_agent"
    assert r.used_fallback is True
    assert r.error == "no result"


def test_agent_result_subclass_instantiation():
    r = SituationalFrameResult()
    assert r.agent_name == "situational_frame"
    assert isinstance(r, AgentResult)


def test_agent_result_is_pydantic():
    r = AgentResult(agent_name="x", used_fallback=True, error="boom")
    d = r.model_dump()
    assert d["agent_name"] == "x"
    assert d["error"] == "boom"


# ── AgentError ────────────────────────────────────────────────────────────────

def test_agent_error_is_exception():
    with pytest.raises(AgentError, match="failed"):
        raise AgentError("agent failed")


# ── AgentBase ─────────────────────────────────────────────────────────────────

class _AlwaysSucceedsAgent(AgentBase):
    name = "success_agent"

    async def _run_impl(self, ctx):
        return AgentResult(agent_name=self.name)


class _AlwaysFailsAgent(AgentBase):
    name = "fail_agent"

    async def _run_impl(self, ctx):
        raise ValueError("intentional failure")


class _FailsWithFallbackAgent(AgentBase):
    name = "fallback_agent"

    async def _run_impl(self, ctx):
        raise RuntimeError("trigger fallback")

    def _fallback(self, ctx):
        return AgentResult(agent_name=self.name, used_fallback=True)


class _TimeoutAgent(AgentBase):
    name = "timeout_agent"
    timeout_ms = 50

    async def _run_impl(self, ctx):
        await asyncio.sleep(10)
        return AgentResult(agent_name=self.name)

    def _fallback(self, ctx):
        return AgentResult(agent_name=self.name, used_fallback=True, error="timeout")


def test_agent_run_success():
    result = asyncio.run(_AlwaysSucceedsAgent().run(ctx=None))
    assert result.agent_name == "success_agent"
    assert result.used_fallback is False


def test_agent_run_raises_when_no_fallback():
    with pytest.raises(AgentError):
        asyncio.run(_AlwaysFailsAgent().run(ctx=None))


def test_agent_run_uses_fallback_on_error():
    result = asyncio.run(_FailsWithFallbackAgent().run(ctx=None))
    assert result.used_fallback is True
    assert result.agent_name == "fallback_agent"


def test_agent_timeout_triggers_fallback():
    result = asyncio.run(_TimeoutAgent().run(ctx=None))
    assert result.used_fallback is True
    assert result.error == "timeout"


# ── CoachResult ───────────────────────────────────────────────────────────────

def test_coach_result_all_fields_default():
    cr = CoachResult()
    assert cr.frame.agent_name == "situational_frame"
    assert cr.comp.agent_name == "comp_picker"
    assert cr.bis.agent_name == "bis_engine"
    assert cr.tempo.agent_name == "tempo_agent"
    assert cr.econ.agent_name == "micro_econ"
    assert cr.item_econ.agent_name == "item_economy"
    assert cr.holders.agent_name == "holder_matrix"
    assert cr.augments.agent_name == "augment_quality"


def test_coach_result_serializes():
    cr = CoachResult()
    d = cr.model_dump()
    assert "frame" in d
    assert "augments" in d
