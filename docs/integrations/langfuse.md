# Langfuse

`LangfuseObservability` records each `agxai` event as a
[Langfuse](https://langfuse.com) observation, grouped into one trace per run.
It requires the Langfuse Python SDK v5.

```bash
pip install "agxai[langfuse]"
```

```python
from agxai import LangfuseObservability, ObservabilityProvider

runtime.register(ObservabilityProvider, LangfuseObservability())
```

Without a `client`, the adapter uses `langfuse.get_client()`, which reads
`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_BASE_URL` from the
environment. To reuse a configured client, pass `client=`.

## What appears in Langfuse

Each event becomes an event observation:

| Observation field | Value |
| --- | --- |
| Name | The event type, such as `node.execution` or `tool.execution` |
| Input | The canonical event JSON |
| Metadata | The `xai.*` correlation fields |
| Trace | One trace per run (see below) |

By default the trace ID is the run ID in Langfuse's 32-character hex form
(`run_id.hex`). To place the events in an existing Langfuse trace instead, pass
that trace's ID as the call's `trace_id`:

```python
await graph.ainvoke(payload, {"metadata": {"trace_id": langfuse_trace_id}})
```

A `trace_id` that is not a valid 32-character hex ID is kept as a correlation
attribute, and the run ID groups the events.

## Lifecycle

`await runtime.flush()` flushes the Langfuse client. `await runtime.close()` also shuts
it down if the adapter created it. A client you pass in is never shut down.

## Overhead

The Langfuse client batches exports, avoiding a network round trip for each
event. With Langfuse 5.2 on a development laptop, an event held the loop for
about 0.12 ms at the median and 0.4 ms at p95. Measure your own environment
with `scripts/benchmark_overhead.py`; see
[Testing](../development/testing.md#measuring-overhead).
