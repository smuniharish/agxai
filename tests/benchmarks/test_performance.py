"""Generous performance budgets that catch order-of-magnitude regressions."""

import asyncio
import importlib.util
import sys
import time
from pathlib import Path

import pytest

from agxai import ProvenanceLink, XAIRuntime
from agxai.storage import InMemoryProvenanceStore
from tests.helpers import State, context, linear_graph

pytestmark = pytest.mark.benchmark


async def test_1000_concurrent_store_writes_stay_within_budget() -> None:
    store = InMemoryProvenanceStore()
    ctx = context()
    links = [
        ProvenanceLink(context=ctx, source_id=f"source-{i}", target_id="decision", relation="r")
        for i in range(1000)
    ]

    started = time.perf_counter()
    await asyncio.gather(*(store.write(link) for link in links))
    lineage = await store.lineage("decision", context=ctx)

    assert len(lineage) == 1000
    assert time.perf_counter() - started < 2.0


def _graph():
    def step(key: str):
        return lambda state: {key: state.get(key, "") + "."}

    return linear_graph(*((f"n{i}", step("note")) for i in range(5)), state=State)


async def test_instrumented_async_runs_stay_within_budget() -> None:
    runtime = XAIRuntime()
    graph = runtime.instrument(_graph())

    started = time.perf_counter()
    for _ in range(100):
        await graph.ainvoke({"question": "q"})

    assert time.perf_counter() - started < 10.0
    assert runtime.errors == ()


def _overhead_script():
    path = Path(__file__).parents[2] / "scripts" / "benchmark_overhead.py"
    spec = importlib.util.spec_from_file_location("benchmark_overhead", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


async def test_overhead_script_reports_bounded_latency_for_every_provider(capsys) -> None:
    script = _overhead_script()

    results = {result.name: result for result in await script.main(runs=30, events=300, warmup=5)}

    assert set(results) == {
        "baseline",
        "instrumented+noop",
        "instrumented+otel",
        "instrumented+langfuse",
        "emit:noop",
        "emit:otel",
        "emit:langfuse",
    }
    for name in ("noop", "otel", "langfuse"):
        assert results[f"instrumented+{name}"].p95_ms < results["baseline"].p95_ms + 250
        assert results[f"emit:{name}"].p95_ms < 25
    assert results["baseline"].peak_kib is not None
    assert "p95 ms" in capsys.readouterr().out


def test_instrumented_sync_runs_reuse_the_thread_loop_within_budget() -> None:
    runtime = XAIRuntime()
    graph = runtime.instrument(_graph())

    started = time.perf_counter()
    for _ in range(100):
        graph.invoke({"question": "q"})

    assert time.perf_counter() - started < 10.0
    assert runtime.errors == ()
