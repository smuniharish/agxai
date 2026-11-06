---
name: agxai
description: Integrate, configure, test, and debug agxai, the framework-agnostic explainability layer for AI agents. Use for LangGraph/LangChain instrumentation, extending Agno, CrewAI, or custom frameworks through the FrameworkInstrumentor ABC, execution records, evidence and decisions, provenance, attribution, disclosure policies, interrupts, and exporting events to LangSmith, Langfuse, OpenTelemetry, or a database. Also use when explanations are missing or failing or runs are not recorded. Do not use to collect model chain-of-thought or replace a tracing tool.
license: Apache-2.0
compatibility: Python 3.12 or newer. Installs agxai 1.x from PyPI; LangGraph/LangChain support requires agxai[langgraph]. scripts/verify_setup.py runs offline in the project's Python environment.
metadata:
  version: "1.0.0"
  documentation: "https://agxai.readthedocs.io"
---

# agxai

`agxai` provides a framework-neutral runtime for versioned execution records.
Its optional LangGraph/LangChain integration captures nodes, state changes,
tools, retrievers, interrupts, and checkpoints automatically. Developers can
extend other frameworks through `FrameworkInstrumentor`. Application code records the evidence
it relied on and the decisions it made. Explanations are built from those
records for one audience at a time and filtered by a disclosure policy.

Use this skill to add the existing package to an application. It is not an
agent framework, a tracing backend, or a way to record model reasoning.

## Before you change anything

1. From the project's Python environment, run the setup check in this skill's
   directory:

   ```bash
   python scripts/verify_setup.py
   ```

   It checks the core offline. When LangGraph is installed it also checks graph
   capture. Use `--langgraph` to require that optional integration and fail with
   an installation hint if missing. Fix every `FAIL` line first.
2. Find the compiled graphs or agents to instrument, any existing
   `XAIRuntime`, and the tests that cover them.
3. Pick the matching recipe in [references/RECIPES.md](references/RECIPES.md).
   Look up exact signatures in [references/API.md](references/API.md).

## Core workflow

1. Install only the integrations you use. The core is `pip install agxai`.
   The LangGraph/LangChain workflow below needs:

   ```bash
   pip install "agxai[langgraph]"
   ```

2. Create one runtime per application and tenant boundary, and instrument the
   compiled graph. The wrapper is called exactly like the graph.

   ```python
   from agxai import XAIRuntime

   runtime = XAIRuntime(application_id="payments", tenant_id="acme-bank", graph_id="fraud-review")
   graph = runtime.instrument(builder.compile())
   ```

3. Inside nodes, tools, or middleware, record why. The `record_*` methods are
   coroutines; a synchronous node wraps them in `runtime.run_sync(...)`.

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

4. Keep the run and explain the decision after the call returns:

   ```python
   with runtime.collect_runs() as runs:
       result = await graph.ainvoke({"amount": 9200.0})
   (run,) = runs
   explanation = await runtime.explain_decision(run.decisions[-1], audience=Audience.AUDITOR, run=run)
   ```

5. If different audiences may see different things, register a
   `PolicyProvider` and test it with
   [assets/test_disclosure_policy.py](assets/test_disclosure_policy.py).
6. Run the project's tests, then `python scripts/verify_setup.py` again.

## Extend another framework

Subclass `FrameworkInstrumentor[Target, Instrumented]` and implement
`instrument(target)`. Use `async with self.capture():` around an async call,
or `with self.capture_sync():` for sync calls, and translate public framework
hooks to the runtime's `record_*` methods. No framework packages are required
by the ABC. Agno/CrewAI integrations must be written and tested by the developer;
they are not bundled adapters. `XAIRuntime.instrument()` remains the LangGraph
shortcut, not a generic dispatcher.

See the custom-framework recipe in
[references/RECIPES.md](references/RECIPES.md) and the
[integration guide](https://agxai.readthedocs.io/en/latest/integrations/custom-frameworks/).

## Rules

- **Observe, never steer.** Do not change graph inputs, outputs, state, or
  control flow to make recording work.
- **Record decisions explicitly.** Call `record_decision` where the
  application decides. Never infer a decision from a trace, and never ask a
  model for its chain-of-thought.
- **Let instrumentation create execution records.** Do not build `Execution`,
  `NodeExecution`, or event models by hand for instrumented calls. Use
  `start_run` and `finish_run` only for work outside any instrumented graph.
- **Instrument the runnable you call.** Methods that build a new runnable,
  such as `graph.with_retry()` or `graph.bind(...)`, return an uninstrumented
  runnable. `with_config(...)` keeps the instrumentation.
- **Use the recorded entry points.** `invoke`, `stream`, `batch`,
  `batch_as_completed`, `astream_events` (v1 and v2), `transform`, and their
  async forms are recorded. LangGraph's experimental v3 streaming
  (`stream_events`, `astream_events(version="v3")`) and LangChain's deprecated
  `astream_log` are not.
- **Keep the policy boundary.** Never weaken a disclosure policy, redaction,
  or capture settings to make a test or an export pass.
- **Keep secrets out of records.** Redaction works on key names such as
  `api_key` or `token`, not on values. Reference people and documents by ID.
- **Choose the failure mode on purpose.** `FAIL_OPEN`, the default, never
  breaks the graph and keeps errors in `runtime.errors`. `FAIL_CLOSED` and
  `STRICT` raise `XAIInstrumentationError`. Explanations fail closed in every
  mode.

## Human-in-the-loop

Compile the graph with a LangGraph checkpointer and call it with a
`thread_id`. Interrupts, `Command(resume=...)` answers, static breakpoints,
and checkpoints are then recorded automatically. A resumed, retried, or
replayed run names the run it continues in `Execution.continuation_of`.
Record approvals made outside the graph with `record_human_interaction`, even
after the run finished. Do not also call `record_checkpoint` for these graphs,
which would record each checkpoint twice; it is for runs you manage yourself
or for `XAIConfig(capture_checkpoints=False)`.

## Where records go

- `Execution`, events, and provenance links go to the `ProvenanceStore`, by
  default `InMemoryProvenanceStore`. To persist them, subclass
  `ProvenanceStore`.
- Evidence, decisions, and memory references are kept on `run.evidence` and
  `run.decisions` and delivered to `XAIPlugin` instances, not to the store.
- Events can also go to one `ObservabilityProvider`: LangSmith, Langfuse, or
  OpenTelemetry.

## When something is wrong

Check `runtime.errors` first, then follow
[references/TROUBLESHOOTING.md](references/TROUBLESHOOTING.md). Common causes:

- `RuntimeError: no active run`: a `record_*` call ran outside an instrumented
  call. Pass `run=` or record inside the graph.
- No run was recorded: the call went to the uninstrumented graph, or used an
  entry point that is not recorded.
- An explanation raises `XAIInstrumentationError`: the policy, attribution, or
  engine failed; the cause is in `runtime.errors`.

## References

- [references/API.md](references/API.md): public imports, methods, settings,
  and records.
- [references/RECIPES.md](references/RECIPES.md): complete patterns for common
  integration tasks.
- [references/TROUBLESHOOTING.md](references/TROUBLESHOOTING.md): symptoms,
  causes, and fixes.
- Documentation: <https://agxai.readthedocs.io>
