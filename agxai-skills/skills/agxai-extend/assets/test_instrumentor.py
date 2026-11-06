"""Tests for an instrumentor built from ``instrumentor_template.py``.

Copy this file next to your instrumentor and replace `ScriptedAgent` with a
small agent of your real framework. The tests check the promises every
instrumentor must keep: one run per top-level call, results and exceptions
unchanged, nested calls joined, and no instrumentation errors. They run with
plain pytest; no async plugin is needed.
"""

from __future__ import annotations

import asyncio
from time import perf_counter

import pytest
from instrumentor_template import AgentInstrumentor, InstrumentedAgent

from agxai import ExecutionStatus, ToolStatus, XAIRuntime


class ScriptedAgent:
    """A stand-in agent that reports one step and one tool call to the instrumentor."""

    def __init__(self, instrumentor: AgentInstrumentor, *, fail: bool = False) -> None:
        self.instrumentor = instrumentor
        self.fail = fail
        self.name = "scripted"

    async def arun(self, task: str) -> str:
        async with self.instrumentor.step("plan", task=task):
            started = perf_counter()
            if self.fail:
                raise RuntimeError("agent failed")
            await self.instrumentor.tool_call("search", started=started)
        await self.instrumentor.runtime.record_decision("ANSWER", candidate_actions=["ANSWER"])
        return f"done: {task}"

    def run(self, task: str) -> str:
        return self.instrumentor.runtime.run_sync(self.arun(task))


def build(*, fail: bool = False) -> tuple[XAIRuntime, InstrumentedAgent]:
    runtime = XAIRuntime(application_id="extend-test", graph_id="scripted-agent")
    instrumentor = AgentInstrumentor(runtime)
    return runtime, instrumentor.instrument(ScriptedAgent(instrumentor, fail=fail))


def test_an_async_call_returns_the_result_and_records_one_completed_run() -> None:
    async def scenario() -> None:
        runtime, agent = build()
        with runtime.collect_runs() as runs:
            assert await agent.arun("refund") == "done: refund"
        (run,) = runs
        assert run.execution.status is ExecutionStatus.COMPLETED
        assert [node.node_id for node in run.execution.nodes] == ["plan"]
        assert [tool.status for tool in run.execution.tools] == [ToolStatus.SUCCEEDED]
        assert [decision.selected_action for decision in run.decisions] == ["ANSWER"]
        assert not runtime.errors
        await runtime.close()

    asyncio.run(scenario())


def test_a_sync_call_records_one_completed_run() -> None:
    runtime, agent = build()
    with runtime.collect_runs() as runs:
        assert agent.run("refund") == "done: refund"
    (run,) = runs
    assert run.execution.status is ExecutionStatus.COMPLETED
    assert not runtime.errors
    runtime.run_sync(runtime.close())


def test_an_agent_error_is_re_raised_and_the_run_and_step_fail() -> None:
    async def scenario() -> None:
        runtime, agent = build(fail=True)
        with runtime.collect_runs() as runs, pytest.raises(RuntimeError, match="agent failed"):
            await agent.arun("refund")
        (run,) = runs
        assert run.execution.status is ExecutionStatus.FAILED
        assert [node.status for node in run.execution.nodes] == [ExecutionStatus.FAILED]
        await runtime.close()

    asyncio.run(scenario())


def test_a_nested_call_joins_the_outer_run() -> None:
    async def scenario() -> None:
        runtime, agent = build()
        instrumentor = AgentInstrumentor(runtime)
        with runtime.collect_runs() as runs:
            async with instrumentor.capture():
                await agent.arun("first")
                await agent.arun("second")
        assert len(runs) == 1
        assert len(runs[0].decisions) == 2
        await runtime.close()

    asyncio.run(scenario())


def test_other_attributes_pass_through_to_the_agent() -> None:
    _, agent = build()
    assert agent.name == "scripted"
