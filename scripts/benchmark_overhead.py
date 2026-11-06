"""Measure agxai's instrumentation overhead: latency percentiles and peak memory.

Two measurements:

- **Graph overhead.** Each scenario runs the same five-node LangGraph graph
  many times and reports p50/p95/p99 wall time per ``ainvoke`` and the peak
  traced memory. ``baseline`` is the uninstrumented graph; every other scenario
  instruments it with the default in-memory store plus one observability
  provider.
- **Emit latency.** Each adapter's ``emit`` is awaited for distinct events and
  timed, which is the time the adapter holds the event loop per event.

Providers never leave the process: OpenTelemetry and Langfuse export through
their real batch processors into an in-memory span exporter. Numbers are
machine-dependent; compare scenarios against ``baseline`` on the same machine.

Run with:

    uv run --no-sync python scripts/benchmark_overhead.py --runs 500 --events 5000
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import statistics
import time
import tracemalloc
from dataclasses import dataclass
from functools import partial
from itertools import pairwise
from typing import TYPE_CHECKING, Any

from langfuse import Langfuse
from langgraph.graph import END, START, StateGraph
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from agxai import (
    LangfuseObservability,
    NoOpObservability,
    ObservabilityProvider,
    OpenTelemetryObservability,
    XAIRuntime,
)
from agxai.core import ExecutionContext, ExecutionStartedEvent

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterator, Sequence

NODES = 5


@dataclass(slots=True)
class State:
    note: str = ""


@dataclass(frozen=True, slots=True)
class Result:
    name: str
    p50_ms: float
    p95_ms: float
    p99_ms: float
    peak_kib: float | None = None


def _graph() -> Any:
    builder = StateGraph(State)
    names = [f"n{index}" for index in range(NODES)]
    for name in names:
        builder.add_node(name, lambda state: {"note": state.note + "."})
    builder.add_edge(START, names[0])
    for first, second in pairwise(names):
        builder.add_edge(first, second)
    builder.add_edge(names[-1], END)
    return builder.compile()


def _otel() -> tuple[OpenTelemetryObservability, Callable[[], None]]:
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(InMemorySpanExporter()))
    adapter = OpenTelemetryObservability(tracer_provider=provider, owns_provider=True)
    return adapter, provider.shutdown


def _langfuse() -> tuple[LangfuseObservability, Callable[[], None]]:
    client = Langfuse(
        public_key="pk-lf-benchmark",
        secret_key="sk-lf-benchmark",  # noqa: S106 - never sent anywhere
        host="http://127.0.0.1:9",
        span_exporter=InMemorySpanExporter(),
        tracer_provider=TracerProvider(),
    )
    return LangfuseObservability(client), client.shutdown


def _providers() -> dict[str, Callable[[], tuple[Any, Callable[[], None]]]]:
    return {
        "noop": lambda: (NoOpObservability(), lambda: None),
        "otel": _otel,
        "langfuse": _langfuse,
    }


def _summary(name: str, samples: Sequence[float], peak: int | None = None) -> Result:
    cuts = statistics.quantiles(samples, n=100, method="inclusive")
    return Result(
        name,
        p50_ms=cuts[49] * 1_000,
        p95_ms=cuts[94] * 1_000,
        p99_ms=cuts[98] * 1_000,
        peak_kib=None if peak is None else peak / 1024,
    )


async def _timed(call: Callable[[], Awaitable[Any]], runs: int, warmup: int) -> list[float]:
    for _ in range(warmup):
        await call()
    samples = []
    for _ in range(runs):
        started = time.perf_counter()
        await call()
        samples.append(time.perf_counter() - started)
    return samples


async def _traced(name: str, call: Callable[[], Awaitable[Any]], runs: int, warmup: int) -> Result:
    gc.collect()
    tracemalloc.start()
    try:
        samples = await _timed(call, runs, warmup)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return _summary(name, samples, peak)


async def graph_overhead(runs: int, warmup: int) -> list[Result]:
    """Time ``ainvoke`` of the same graph uninstrumented and under each provider."""
    plain = _graph()
    results = [await _traced("baseline", lambda: plain.ainvoke({}), runs, warmup)]
    for name, build in _providers().items():
        adapter, shutdown = build()
        runtime = XAIRuntime()
        runtime.register(ObservabilityProvider, adapter)
        graph = runtime.instrument(_graph())
        try:
            results.append(
                await _traced(f"instrumented+{name}", partial(graph.ainvoke, {}), runs, warmup)
            )
            if runtime.errors:
                raise RuntimeError(f"{name} recorded errors: {runtime.errors!r}")
        finally:
            await runtime.close()
            shutdown()
    return results


async def _emit_next(adapter: Any, pending: Iterator[ExecutionStartedEvent]) -> None:
    await adapter.emit(next(pending))


async def emit_latency(events: int, warmup: int) -> list[Result]:
    """Time each adapter's ``emit`` per event: how long it holds the event loop."""
    context = ExecutionContext(application_id="bench", tenant_id="bench", graph_id="bench")
    results = []
    for name, build in _providers().items():
        adapter, shutdown = build()
        pending = [
            ExecutionStartedEvent(context=context, sequence=0) for _ in range(events + warmup)
        ]
        emit = partial(_emit_next, adapter, iter(pending))
        try:
            samples = await _timed(emit, events, warmup)
            results.append(_summary(f"emit:{name}", samples))
        finally:
            await adapter.close()
            shutdown()
    return results


def _table(results: Sequence[Result]) -> str:
    lines = [f"{'scenario':<24} {'p50 ms':>9} {'p95 ms':>9} {'p99 ms':>9} {'peak KiB':>10}"]
    for result in results:
        peak = "-" if result.peak_kib is None else f"{result.peak_kib:,.0f}"
        lines.append(
            f"{result.name:<24} {result.p50_ms:>9.3f} {result.p95_ms:>9.3f} "
            f"{result.p99_ms:>9.3f} {peak:>10}"
        )
    return "\n".join(lines)


async def main(runs: int = 300, events: int = 3000, warmup: int = 20) -> list[Result]:
    """Run both measurements, print one table, and return the results."""
    results = [*await graph_overhead(runs, warmup), *await emit_latency(events, warmup)]
    print(_table(results))
    return results


def _parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--runs", type=int, default=300, help="graph runs per scenario")
    parser.add_argument("--events", type=int, default=3000, help="events per emit scenario")
    parser.add_argument("--warmup", type=int, default=20, help="untimed iterations first")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = _parse()
    asyncio.run(main(arguments.runs, arguments.events, arguments.warmup))
