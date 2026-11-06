---
name: agxai
description: >-
  Use this skill when adding agxai to a Python AI agent, or when working with
  agxai already in a project: recording why an agent decided something,
  explaining decisions to developers, auditors, business users, or end users,
  provenance and attribution, audit trails, disclosure policies that withhold
  fields per audience, human-in-the-loop interrupts, and exporting records to
  LangSmith, Langfuse, OpenTelemetry, or a database. Covers LangGraph and
  LangChain apps and plain Python agents. Also use it when explanations are
  missing, leak data, or fail, or when runs are not recorded. Do not use it to
  build a new framework adapter or storage backend (use agxai-extend), to set
  up generic tracing with no explanations, or to capture a model's
  chain-of-thought.
license: Apache-2.0
compatibility: >-
  Python 3.12 or newer. Installs agxai 1.x from PyPI; LangGraph and LangChain
  support needs agxai[langgraph]. scripts/verify_setup.py runs offline in the
  project's Python environment.
metadata:
  version: "1.0.1"
  documentation: "https://agxai.readthedocs.io"
---

# agxai

agxai records what an AI agent ran, the evidence it relied on, and the
decisions it made, then explains each decision to one audience at a time
through a disclosure policy. Its optional LangGraph/LangChain integration
captures nodes, state changes, tools, retrievers, interrupts, and checkpoints
automatically. Application code records evidence and decisions explicitly.

## Workflow

Copy this checklist and keep it current:

```text
- [ ] 1. verify_setup.py passes
- [ ] 2. One runtime per application and tenant boundary
- [ ] 3. The called graph or agent is instrumented
- [ ] 4. Evidence and decisions recorded where the code decides
- [ ] 5. Decisions explained, per audience, under a tested policy
- [ ] 6. Project tests and verify_setup.py pass again
```

1. From the project's Python environment, run this skill's setup check:
   `python scripts/verify_setup.py`. Fix every `FAIL` line first. It checks
   the core offline, and graph capture when LangGraph is installed; add
   `--langgraph` to require it, or `--json` for one JSON object.
2. Install only what is used: `pip install agxai`, plus `"agxai[langgraph]"`
   for LangGraph or LangChain. Create one `XAIRuntime` per application and
   tenant boundary:

   ```python
   from agxai import XAIRuntime

   runtime = XAIRuntime(application_id="payments", tenant_id="acme-bank", graph_id="fraud-review")
   graph = runtime.instrument(builder.compile())  # called exactly like the graph
   ```

   For a framework other than LangGraph, use or write a
   `FrameworkInstrumentor`; the `agxai-extend` skill covers writing one.
3. Inside nodes, tools, or middleware, record why. The `record_*` methods are
   coroutines; a sync node wraps them in `runtime.run_sync(...)`.

   ```python
   evidence = await runtime.record_evidence(
       EvidenceType.TOOL_RESULT, summary="Fraud model scored the transaction 0.91.", confidence=0.97
   )
   await runtime.record_decision(
       "HUMAN_REVIEW",
       decision_type=DecisionType.ROUTING,
       candidate_actions=["AUTO_APPROVE", "HUMAN_REVIEW"],
       evidence_ids=[evidence.id],
       factors=[DecisionFactor(name="fraud_risk_score", value=0.91, evidence_ids=[evidence.id])],
   )
   ```

4. Keep the run and explain after the call returns:

   ```python
   with runtime.collect_runs() as runs:
       result = await graph.ainvoke({"amount": 9200.0})
   (run,) = runs
   explanation = await runtime.explain_decision(run.decisions[-1], audience=Audience.AUDITOR, run=run)
   ```

5. If audiences may see different things, register a `PolicyProvider` and
   copy `assets/test_disclosure_policy.py` into the project's tests.
6. Run the project's tests, then `python scripts/verify_setup.py` again. If
   anything fails, read `runtime.errors`, fix, and repeat. Do not report the
   task done until this second run passes.

## Read more only when needed

| Task | Read |
| --- | --- |
| LangGraph graphs, sync nodes, prebuilt agents, middleware, trace IDs | [references/langgraph.md](references/langgraph.md) |
| `interrupt`, `Command(resume=...)`, breakpoints, approvals | [references/human-in-the-loop.md](references/human-in-the-loop.md) |
| Per-audience explanations, LLM-phrased explanations | [references/disclosure.md](references/disclosure.md) |
| Plugins, LangSmith, Langfuse, OpenTelemetry | [references/exporting.md](references/exporting.md) |
| `FAIL_OPEN` / `FAIL_CLOSED` / `STRICT`, runs outside any graph | [references/failure-modes.md](references/failure-modes.md) |
| Exact signatures, settings, records, enumerations | [references/api.md](references/api.md) |
| An error, a missing run, or an unexpected explanation | [references/troubleshooting.md](references/troubleshooting.md) |

## Rules

- **Observe, never steer.** Do not change graph inputs, outputs, state, or
  control flow to make recording work.
- **Record decisions explicitly** with `record_decision` where the code
  decides. Never infer them from a trace, and never ask a model for its
  chain-of-thought.
- **Keep the policy boundary.** Never weaken a disclosure policy, redaction,
  or capture setting to make a test or an export pass.
- **Keep secrets out of records.** Redaction matches key names such as
  `api_key` or `token`, not values. Reference people and documents by ID.

## Gotchas

- `RuntimeError: no active run` means a `record_*` call ran outside an
  instrumented call. Record inside the graph, or pass `run=`.
- Only the wrapper returned by `runtime.instrument(...)` records. Methods that
  build a new runnable, such as `with_retry()` or `bind(...)`, drop the
  instrumentation; `with_config(...)` keeps it.
- `invoke`, `stream`, `batch`, `batch_as_completed`, `astream_events` v1 and
  v2, `transform`, and their async forms are recorded. `stream_events`,
  `astream_events(version="v3")`, and `astream_log` are not.
- Do not build `Execution` or event models by hand for instrumented calls. Use
  `start_run` and `finish_run` only for work outside any instrumented call.
- The store holds executions, events, and links. Evidence and decisions live
  on `run.evidence` and `run.decisions` and reach plugins, not the store.
- `FAIL_OPEN`, the default, never breaks the graph and keeps the last 100
  errors in `runtime.errors`. Explanations fail closed in every mode and raise
  `XAIInstrumentationError`.
- With a checkpointer and a `thread_id`, checkpoints are recorded
  automatically. Do not also call `record_checkpoint`.
- Call `await runtime.close()` at shutdown, or batched exports are lost.
