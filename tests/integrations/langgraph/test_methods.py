import asyncio
import logging
from typing import Any

import pytest
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.graph import END, START, StateGraph

from agxai import (
    Execution,
    ExecutionStatus,
    ProvenanceStore,
    XAIConfig,
    XAIRuntime,
)
from agxai.core import ExecutionFailedEvent
from agxai.integrations.langgraph import InstrumentedGraph
from tests.helpers import FailingStore, State, executions, linear_graph


def increment(state: State) -> State:
    return {"count": state["count"] + 1}


def failing_on_one(state: State) -> State:
    if state["count"] == 1:
        raise ValueError("node failed")
    return increment(state)


def make_runtime() -> XAIRuntime:
    return XAIRuntime(application_id="app", tenant_id="tenant")


def recording_node(runtime: XAIRuntime):
    def node(state: State) -> State:
        runtime.run_sync(runtime.record_evidence("rule", summary=f"seen {state['count']}"))
        return increment(state)

    return node


def statuses(records: list[Execution]) -> list[ExecutionStatus]:
    return sorted(item.status for item in records)


def test_invoke_records_a_completed_run() -> None:
    runtime = make_runtime()

    assert runtime.instrument(linear_graph(("inc", increment))).invoke({"count": 1}) == {"count": 2}
    assert statuses(runtime.run_sync(executions(runtime))) == [ExecutionStatus.COMPLETED]


def test_invoke_records_a_failed_run_and_reraises() -> None:
    runtime = make_runtime()

    with pytest.raises(ValueError, match="node failed"):
        runtime.instrument(linear_graph(("boom", failing_on_one))).invoke({"count": 1})

    (record,) = runtime.run_sync(executions(runtime))
    assert record.status is ExecutionStatus.FAILED
    assert record.exceptions[0].exception_type == "ValueError"


def test_a_keyboard_interrupt_records_a_cancelled_run() -> None:
    class Interrupting(Runnable[Any, Any]):
        def invoke(self, input: Any, config: RunnableConfig | None = None, **kwargs: Any) -> Any:
            raise KeyboardInterrupt

    runtime = make_runtime()
    with pytest.raises(KeyboardInterrupt):
        runtime.instrument(Interrupting()).invoke({})

    assert statuses(runtime.run_sync(executions(runtime))) == [ExecutionStatus.CANCELLED]


async def test_current_run_is_available_inside_nodes_for_every_method() -> None:
    runtime = make_runtime()
    graph = runtime.instrument(linear_graph(("record", recording_node(runtime))))

    with runtime.collect_runs() as runs:
        await graph.ainvoke({"count": 1})
        await asyncio.to_thread(graph.invoke, {"count": 2})
        [chunk async for chunk in graph.astream({"count": 3})]
        await asyncio.to_thread(lambda: list(graph.stream({"count": 4})))
        await graph.abatch([{"count": 5}, {"count": 6}])
        await asyncio.to_thread(graph.batch, [{"count": 7}, {"count": 8}])

    assert sorted(str(run.evidence[0].summary) for run in runs) == [
        f"seen {n}" for n in range(1, 9)
    ]
    assert all(run.execution.status is ExecutionStatus.COMPLETED for run in runs)
    assert len({run.run_id for run in runs}) == 8


async def test_stream_yields_chunks_without_leaking_the_run_to_the_consumer() -> None:
    runtime = make_runtime()
    graph = runtime.instrument(linear_graph(("a", increment), ("b", increment)))
    seen_between_chunks = []

    chunks = []
    async for chunk in graph.astream({"count": 1}):
        seen_between_chunks.append((runtime.current_run, runtime._is_instrumenting()))
        chunks.append(chunk)
    sync_chunks = []
    for chunk in graph.stream({"count": 1}):
        seen_between_chunks.append((runtime.current_run, runtime._is_instrumenting()))
        sync_chunks.append(chunk)

    assert chunks == sync_chunks == [{"a": {"count": 2}}, {"b": {"count": 3}}]
    assert seen_between_chunks == [(None, False)] * 4
    assert statuses(await executions(runtime)) == [ExecutionStatus.COMPLETED] * 2


async def test_streams_record_failures_and_early_exits() -> None:
    runtime = make_runtime()
    failing = runtime.instrument(linear_graph(("boom", failing_on_one)))
    two_steps = runtime.instrument(linear_graph(("a", increment), ("b", increment)))

    with pytest.raises(ValueError, match="node failed"):
        [chunk async for chunk in failing.astream({"count": 1})]
    with pytest.raises(ValueError, match="node failed"):
        list(failing.stream({"count": 1}))
    generator = two_steps.stream({"count": 1})
    next(generator)
    generator.close()
    agenerator = two_steps.astream({"count": 1})
    await anext(agenerator)
    await agenerator.aclose()

    assert statuses(await executions(runtime)) == [
        ExecutionStatus.CANCELLED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.FAILED,
        ExecutionStatus.FAILED,
    ]


async def test_cancelling_a_streaming_task_records_a_cancelled_run() -> None:
    started = asyncio.Event()

    async def slow(state: State) -> State:
        started.set()
        await asyncio.sleep(10)
        return state

    runtime = make_runtime()
    graph = runtime.instrument(linear_graph(("slow", slow)))

    async def consume() -> None:
        async for _ in graph.astream({"count": 1}):
            pass

    task = asyncio.ensure_future(consume())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert statuses(await executions(runtime)) == [ExecutionStatus.CANCELLED]


def test_batch_records_each_input_on_its_own_run() -> None:
    runtime = make_runtime()
    graph = runtime.instrument(linear_graph(("boom", failing_on_one)))

    assert graph.batch([]) == []
    assert graph.batch([{"count": 2}]) == [{"count": 3}]
    results = graph.batch([{"count": 1}, {"count": 5}], return_exceptions=True)
    with pytest.raises(ValueError, match="node failed"):
        graph.batch([{"count": 1}, {"count": 3}])

    assert isinstance(results[0], ValueError)
    assert results[1] == {"count": 6}
    recorded = statuses(runtime.run_sync(executions(runtime)))
    # Like Runnable.batch, inputs that have not started when another input raises are
    # cancelled, so the last batch records one or two runs; none is left RUNNING.
    assert recorded.count(ExecutionStatus.FAILED) == 2
    assert recorded.count(ExecutionStatus.COMPLETED) in (2, 3)
    assert set(recorded) == {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED}
    with pytest.raises(ValueError, match="same length"):
        graph.batch([{"count": 1}, {"count": 2}], [{}])


async def test_abatch_records_each_input_and_honors_return_exceptions() -> None:
    runtime = make_runtime()
    graph = runtime.instrument(linear_graph(("boom", failing_on_one)))

    assert await graph.abatch([]) == []
    results = await graph.abatch(
        [{"count": 1}, {"count": 5}], {"max_concurrency": 1}, return_exceptions=True
    )
    with pytest.raises(ValueError, match="node failed"):
        await graph.abatch([{"count": 1}])

    assert isinstance(results[0], ValueError)
    assert results[1] == {"count": 6}
    assert statuses(await executions(runtime)) == [
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.FAILED,
    ]


async def test_cancelling_abatch_cancels_every_run() -> None:
    async def slow(state: State) -> State:
        await asyncio.sleep(10)
        return state

    runtime = make_runtime()
    task = asyncio.ensure_future(
        runtime.instrument(linear_graph(("slow", slow))).abatch([{"count": 1}, {"count": 2}])
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert statuses(await executions(runtime)) == [ExecutionStatus.CANCELLED] * 2


async def test_sync_fan_out_records_nodes_from_worker_threads() -> None:
    builder = StateGraph(State)
    builder.add_node("left", lambda state: {"answer": "left"})
    builder.add_node("right", lambda state: {"note": "right"})
    builder.add_edge(START, "left")
    builder.add_edge(START, "right")
    builder.add_edge("left", END)
    builder.add_edge("right", END)
    runtime = make_runtime()

    with runtime.collect_runs() as runs:
        await asyncio.to_thread(runtime.instrument(builder.compile()).invoke, {"question": "q"})

    execution = runs[0].execution
    assert sorted(node.node_id for node in execution.nodes) == ["left", "right"]
    assert sorted(item.node_id for item in execution.state_transitions) == ["left", "right"]
    assert runtime.errors == ()


async def test_nested_calls_of_the_same_runtime_pass_through() -> None:
    runtime = make_runtime()
    inner = runtime.instrument(linear_graph(("inc", increment)))

    async def outer_node(state: State) -> State:
        once = await inner.ainvoke(state)
        twice = inner.invoke(once)
        streamed = [chunk async for chunk in inner.astream(twice)]
        listed = list(inner.stream(twice))
        batched = inner.batch([twice])
        abatched = await inner.abatch([twice])
        assert streamed == listed
        assert batched == abatched
        return abatched[0]

    result = await runtime.instrument(linear_graph(("outer", outer_node))).ainvoke({"count": 1})

    assert result == {"count": 4}
    assert len(await executions(runtime)) == 1


def test_proxy_preserves_the_wrapped_graph_api() -> None:
    runtime = make_runtime()
    compiled = linear_graph(("inc", increment))
    graph = runtime.instrument(compiled)
    configured = graph.with_config({"run_name": "custom"})

    assert isinstance(configured, InstrumentedGraph)
    assert configured is not graph
    assert configured.runtime is runtime
    assert configured.invoke({"count": 1}) == {"count": 2}
    assert graph.get_graph().nodes.keys() == compiled.get_graph().nodes.keys()
    assert graph.__wrapped__ is compiled


def test_instrument_reuses_its_own_wrapper_and_rewraps_another_runtimes() -> None:
    compiled = linear_graph(("inc", increment))
    first, second = XAIRuntime(), XAIRuntime()
    wrapped = first.instrument(compiled)

    assert first.instrument(wrapped) is wrapped
    rewrapped = second.instrument(wrapped)
    assert rewrapped is not wrapped
    assert rewrapped.runtime is second
    assert rewrapped.__wrapped__ is compiled


class PlainIterables(Runnable[Any, int]):
    """A Runnable whose streams are plain iterators without close methods."""

    def invoke(self, input: Any, config: RunnableConfig | None = None, **kwargs: Any) -> int:
        return 0

    def stream(self, input: Any, config: RunnableConfig | None = None, **kwargs: Any):
        return iter([1, 2])

    def astream(self, input: Any, config: RunnableConfig | None = None, **kwargs: Any):
        class Chunks:
            def __init__(self) -> None:
                self.items = [1, 2]

            def __aiter__(self):
                return self

            async def __anext__(self):
                if not self.items:
                    raise StopAsyncIteration
                return self.items.pop(0)

        return Chunks()


async def test_streams_accept_iterators_without_close_methods() -> None:
    runtime = make_runtime()
    graph = runtime.instrument(PlainIterables())

    assert [chunk async for chunk in graph.astream({})] == [1, 2]
    assert list(graph.stream({})) == [1, 2]
    assert statuses(await executions(runtime)) == [ExecutionStatus.COMPLETED] * 2


async def test_failures_while_recording_a_failed_run_are_logged_not_raised(caplog) -> None:
    runtime = XAIRuntime(config=XAIConfig(failure_mode="fail_closed"))
    runtime.register(ProvenanceStore, FailingStore(only=(ExecutionFailedEvent,)))
    graph = runtime.instrument(linear_graph(("boom", failing_on_one)))

    with caplog.at_level(logging.ERROR), pytest.raises(ValueError, match="node failed"):
        await graph.ainvoke({"count": 1})
    with caplog.at_level(logging.ERROR), pytest.raises(ValueError, match="node failed"):
        await asyncio.to_thread(graph.invoke, {"count": 1})

    assert caplog.text.count("Failed to record the outcome of a failed graph run") == 2
