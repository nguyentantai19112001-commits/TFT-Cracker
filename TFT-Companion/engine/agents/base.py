"""AgentBase — common base class for all 8 Augie v3 agents."""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable

from pydantic import BaseModel

log = logging.getLogger(__name__)


class AgentError(Exception):
    """Raised when an agent fails and no fallback is available."""


class AgentResult(BaseModel):
    """Minimal result wrapper — every concrete result model extends this."""
    agent_name: str = ""
    used_fallback: bool = False
    error: str | None = None

    @classmethod
    def empty(cls, agent_name: str = "") -> "AgentResult":
        return cls(agent_name=agent_name, used_fallback=True, error="no result")


class AgentBase(ABC):
    """Base class for all agents. Handles timeout + fallback boilerplate."""

    name: str = "unnamed"
    timeout_ms: int = 2000

    async def run(self, ctx: Any) -> AgentResult:
        """Run the agent with timeout protection. Falls back on failure."""
        try:
            return await asyncio.wait_for(
                self._run_impl(ctx), timeout=self.timeout_ms / 1000
            )
        except (asyncio.TimeoutError, Exception) as exc:
            log.warning("%s failed: %s — using fallback", self.name, exc)
            fb = self._fallback(ctx)
            if fb is None:
                raise AgentError(f"{self.name} failed and has no fallback") from exc
            return fb

    @abstractmethod
    async def _run_impl(self, ctx: Any) -> AgentResult:
        """Agent-specific implementation. Must return an AgentResult subclass."""

    def _fallback(self, ctx: Any) -> AgentResult | None:
        """Rule-based fallback. Override in LLM agents. Returns None if no fallback."""
        return None
