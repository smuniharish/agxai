# Failure modes and manual runs

Read this file when choosing how instrumentation failures behave, or when recording work that does not run through an instrumented call.

## Choose a failure mode

```python
from agxai import FailureMode, XAIConfig, XAIRuntime

runtime = XAIRuntime(XAIConfig(failure_mode=FailureMode.FAIL_CLOSED))
```

| Mode | When an instrumentation operation fails |
| --- | --- |
| `FAIL_OPEN` (default) | The error goes to `runtime.errors` and the graph continues. |
| `FAIL_CLOSED` | `XAIInstrumentationError` is raised, also from inside the graph call. |
| `STRICT` | Like `FAIL_CLOSED`, and records may not be dropped: evidence and decisions need a plugin, and executions need a store or observability provider. |

Explanations fail closed in every mode. A slow backend is bounded by
`operation_timeout_seconds`.

## Record work outside a graph

For code that does not run through an instrumented graph, manage the run
yourself and pass it to every call:

```python
run = await runtime.start_run({"metadata": {"trace_id": "job-42"}})
try:
    evidence = await runtime.record_evidence("rule", summary="Limit exceeded.", run=run)
    decision = await runtime.record_decision("REJECT", evidence_ids=[evidence.id], run=run)
except BaseException as error:
    await runtime.finish_run(run, error)
    raise
await runtime.finish_run(run)
explanation = await runtime.explain_decision(decision, run=run)
```

Never combine a manual run with an instrumented call for the same work.
