"""A `FrameworkInstrumentor` template for an agent framework agxai does not bundle.

Copy this file, then adapt the three marked places to your framework:

1. `AgentLike`: the entry points your framework's agent exposes.
2. `InstrumentedAgent`: wrap exactly those entry points, nothing else.
3. `AgentInstrumentor.step` and `tool_call`: call them from your framework's
   public step or tool callbacks, if it has any.

The wrapper must observe and never steer: it returns the agent's result
unchanged and re-raises its exceptions. ``test_instrumentor.py`` checks this.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from time import perf_counter
from typing import TYPE_CHECKING, Any, Protocol

from agxai import ExecutionStatus, FrameworkInstrumentor, ToolStatus

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping


class AgentLike(Protocol):
    """(1) The calls your framework's agent exposes."""

    async def arun(self, task: str) -> str: ...

    def run(self, task: str) -> str: ...


class InstrumentedAgent:
    """(2) Called exactly like the agent; each top-level call becomes one run."""

    def __init__(self, agent: AgentLike, instrumentor: AgentInstrumentor) -> None:
        self._agent = agent
        self._instrumentor = instrumentor

    async def arun(self, task: str, *, config: Mapping[str, Any] | None = None) -> str:
        async with self._instrumentor.capture(config):
            return await self._agent.arun(task)

    def run(self, task: str, *, config: Mapping[str, Any] | None = None) -> str:
        with self._instrumentor.capture_sync(config):
            return self._agent.run(task)

    def __getattr__(self, name: str) -> Any:
        # Everything that is not an entry point behaves exactly as on the agent.
        return getattr(self._agent, name)


class AgentInstrumentor(FrameworkInstrumentor[AgentLike, InstrumentedAgent]):
    """Records each agent call as a run, plus the steps and tools reported to it."""

    def instrument(self, target: AgentLike) -> InstrumentedAgent:
        return InstrumentedAgent(target, self)

    @asynccontextmanager
    async def step(self, name: str, **metadata: Any) -> AsyncIterator[None]:
        """(3) Record one framework step as a node, with its timing and outcome."""
        started_at = datetime.now(UTC)
        try:
            yield
        except BaseException:
            await self._node(name, ExecutionStatus.FAILED, started_at, metadata)
            raise
        await self._node(name, ExecutionStatus.COMPLETED, started_at, metadata)

    async def tool_call(
        self, tool_name: str, *, started: float, failed: bool = False, **metadata: Any
    ) -> None:
        """(3) Record a tool call reported by the framework; ``started`` is a perf_counter()."""
        await self.runtime.record_tool(
            tool_name,
            status=ToolStatus.FAILED if failed else ToolStatus.SUCCEEDED,
            latency_ms=(perf_counter() - started) * 1000,
            metadata=metadata,
        )

    async def _node(
        self,
        name: str,
        status: ExecutionStatus,
        started_at: datetime,
        metadata: Mapping[str, Any],
    ) -> None:
        await self.runtime.record_node(
            name,
            status=status,
            started_at=started_at,
            ended_at=datetime.now(UTC),
            metadata=metadata,
        )
