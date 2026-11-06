# Benchmarks

agxai runs inside your agent's process, so its cost is the latency it adds to
each run and the memory its records take. This page shows both, measured on one
machine, and how to measure them on yours.

## Results

A five-node LangGraph graph, run 500 times per scenario after 20 untimed warmup
runs. `baseline` is the graph without agxai. Every other scenario instruments
it with the default in-memory store plus one observability provider. The
providers export to an in-memory span exporter, so no network time is included.

| Scenario | p50 ms | p95 ms | p99 ms | Peak memory |
| --- | ---: | ---: | ---: | ---: |
| `baseline` | 6.68 | 7.81 | 8.85 | 0.3 MiB |
| instrumented, no provider | 7.99 | 9.62 | 10.63 | 23.4 MiB |
| instrumented, OpenTelemetry | 11.02 | 14.93 | 18.91 | 46.7 MiB |
| instrumented, Langfuse | 20.57 | 29.16 | 59.31 | 53.3 MiB |

- **Recording costs about 1.3 ms per run at p50**, or about 0.26 ms per node,
  for capture, canonical events and the in-memory store.
- **Each provider adds its own cost.** OpenTelemetry adds about 3 ms per run at
  p50; Langfuse, whose SDK does more work per span, adds about 12.6 ms.
- **Peak memory is cumulative.** The in-memory store keeps every record from all
  520 runs, about 46 KiB per run. Use a database
  [`ProvenanceStore`](architecture/storage.md) in production, or call the
  store's `delete_run` when a run's records are no longer needed.

### Emit latency

How long each provider's `emit` holds the event loop per event, over 5,000
events:

| Provider | p50 ms | p95 ms | p99 ms |
| --- | ---: | ---: | ---: |
| No provider | 0.000 | 0.001 | 0.001 |
| OpenTelemetry | 0.016 | 0.026 | 0.110 |
| Langfuse | 0.093 | 0.180 | 0.393 |

## Environment

| | |
| --- | --- |
| CPU | Intel Core Ultra 7 265HX |
| OS | Windows 11 |
| Python | 3.15.2 |
| Packages | agxai 1.0.0, langgraph 1.2.20, opentelemetry-sdk 1.45.2, langfuse 5.2.0 |

Timings are taken with `tracemalloc` running, which slows every scenario,
including `baseline`, by a similar amount. Compare scenarios with each other,
not with numbers from another machine.

## Reproduce

```bash
uv sync --all-extras --all-groups
uv run python scripts/benchmark_overhead.py --runs 500 --events 5000
```

The script is
[`scripts/benchmark_overhead.py`](https://github.com/smuniharish/agxai/blob/master/scripts/benchmark_overhead.py).
`--warmup` sets the untimed runs (default 20).
