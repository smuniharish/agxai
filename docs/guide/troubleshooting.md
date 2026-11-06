# Troubleshooting

Start with `runtime.errors`. In the default fail-open mode, every instrumentation
failure is kept there (the last 100), even though the graph keeps running.

```python
for error in runtime.errors:
    print(repr(error))
```

## Missing optional framework

`XAIRuntime.instrument()` is a LangGraph/LangChain convenience. If it raises
an `ImportError`, install `pip install "agxai[langgraph]"`. The core works
without it. For Agno, CrewAI, or another framework, call your
[`FrameworkInstrumentor` subclass](../integrations/custom-frameworks.md)
instead; no adapters for those frameworks are bundled.

## `RuntimeError: no active run`

The full message is
`no active run: call this inside an instrumented call or pass run=`. A
`record_*` method was called where no run is active:

- The graph was called directly instead of through `runtime.instrument(graph)`.
- The call happened after the instrumented call returned. Keep the run with
  `collect_runs()` and pass `run=`; see
  [Explain a decision after the run](how-to/explain-after-run.md).
- The code runs in a thread you started yourself, which does not inherit the
  context. Use `contextvars.copy_context().run(...)` or pass `run=`.
- The code runs outside an instrumented call. Use a capture context or
  `start_run()`, `activate_run()`, and `finish_run()`.

## Nothing, or not everything, is recorded

- **Unrecorded call.** LangGraph's experimental v3 streaming protocol
  (`stream_events` and `astream_events(version="v3")`) and LangChain's
  deprecated `astream_log` cannot be recorded; `runtime.errors` holds a
  `NotImplementedError` for each such call. Use `stream`, `astream`, or
  `astream_events` with `version="v2"`. Runnables built from the instrumented
  graph, such as `graph.with_retry()`, are not instrumented.
- **No checkpoints or `continuation_of`.** They need a graph compiled with a
  checkpointer, a `thread_id` in the call's config, and
  `capture_checkpoints=True` (the default). A call with new input starts a new
  run; only a call whose input is `None` or a `Command` continues one.
- **State capture settings.** `CaptureMode.NONE` records no state changes.
  `SELECTIVE` records only changed keys listed in `capture_fields`, and nothing
  if that is empty.
- **Capture policy.** An event your `CapturePolicy` denies, or whose policy
  raised an error, is not recorded anywhere.
- **Failures.** Look in `runtime.errors` for store or exporter errors.

## A value shows `"[not captured]"`

Its key looks like a credential, for example `token`, `api_key`,
`authorization`, or `session_token`. This is intended. If the value is not a
credential, rename the key: a count stored under `token` is recorded once it is
stored under `token_count`.

## Evidence and decisions are not in the store

Evidence, decisions, and memory references are delivered to
[plugins](../architecture/plugins.md#plugins), not to the store. Register a
plugin that persists them.

## Explanations raise `XAIInstrumentationError`

Explanations fail closed in every mode. The message names the step:

| Message | Fix |
| --- | --- |
| `LLM explanation engine is registered but disabled in XAIConfig` | Set `XAIConfig(llm_explanation_enabled=True)`, or register the structured engine. |
| `exposure policy evaluation failed; see XAIRuntime.errors` | Your `PolicyProvider` raised or timed out. The cause is in `runtime.errors[-1]`. |
| `attribution failed; see XAIRuntime.errors` | Your `AttributionEngine` raised, or a rule returned a non-finite score. |
| `explanation failed; see XAIRuntime.errors` | The engine raised, or an LLM reply was invalid or timed out. Raise `operation_timeout_seconds` for slow models. |

`ValueError: decision does not belong to the given run` means
`explain_decision` received a decision from a different run. Pass the run the
decision was recorded in.

## Timeouts in `runtime.errors`

`TimeoutError` entries mean an operation exceeded
`operation_timeout_seconds`. `timed out waiting for an instrumentation slot`
means `max_concurrency` operations were already in flight. Check the backend's
latency, then raise the timeout or the concurrency limit.

## Nothing appears in LangSmith, Langfuse, or OpenTelemetry

- Call `await runtime.flush()` before short scripts exit, and `await runtime.close()`
  at shutdown, so batched data is sent.
- `OptionalDependencyError` names the extra to install, for example
  `pip install 'agxai[otel]'`.
- For OpenTelemetry, check that the tracer provider has an exporter and that
  `OTEL_EXPORTER_OTLP_ENDPOINT` points to your collector.

## Custom store errors

- `TypeError: ... does not implement ProvenanceStore` means the store does not
  subclass `ProvenanceStore`. Since stores are an abstract base class,
  inheriting from it is required.
- `TypeError: Can't instantiate abstract class` means one of the six abstract
  methods is missing: `write`, `get`, `query`, `parents`, `children`, or
  `delete_run`.
- Run [`ProvenanceStoreContract`](../architecture/storage.md#testing-a-store)
  against the store; each failing check names the broken promise.
- With an asynchronous database driver, such as the PostgreSQL example, use
  asynchronous graph calls. On Windows, psycopg's asynchronous mode needs
  `asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)`.
