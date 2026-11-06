# Writing a FrameworkInstrumentor

Read this file when the framework's call boundary or callback model does not
map obviously onto `assets/instrumentor_template.py`.

## The contract

`FrameworkInstrumentor[Target, Instrumented]` is an ABC exported from `agxai`
and `agxai.integrations`. It needs no framework package.

- `__init__(runtime)` stores `self.runtime`.
- `instrument(target) -> Instrumented` is the only abstract method. Return an
  object called exactly like the target.
- `capture(config=None)` (async) and `capture_sync(config=None)` (sync) are
  context managers. Each starts a run and activates it, so `record_*` calls
  without `run=` find it. It finishes the run as completed, failed, or
  cancelled, and re-raises the exception. Inside an active run of the same
  runtime it yields that run instead, so nested calls join the outer run.
- `config` is a mapping with optional `metadata` and `configurable` sections.
  The `metadata` keys `trace_id`, `xai_application_id`, `xai_tenant_id`,
  `xai_graph_id`, and `xai_run_id` override the runtime's identity for one
  call.

## Choosing the boundary

| Framework shape | Wrap |
| --- | --- |
| A callable or `async def` agent | The callable, as in `examples/custom_framework.py`. |
| An object with entry methods, such as Agno's `Agent.run` / `arun` or CrewAI's `Crew.kickoff` / `kickoff_async` | Each entry method on a wrapper class; forward every other attribute. |
| A streaming entry point | The generator, keeping the `capture` block open until it is exhausted or closed. |
| A server or job runner | The request or job handler. |

Wrap only top-level entry points. A call made inside another wrapped call
joins the outer run automatically.

## Translating callbacks

If the framework exposes public step, tool, or event callbacks, translate them
into runtime calls inside the active run:

| Framework event | Runtime call |
| --- | --- |
| A step, task, or agent turn finished | `record_node(name, status=..., started_at=..., ended_at=...)` |
| A tool call finished | `record_tool(name, status=..., latency_ms=..., tool_call_id=...)` |
| A retrieval finished | `record_retrieval(retriever_id, documents=[...])` |
| State changed | `record_state_delta(node_id, before, after)`, which applies the capture settings |
| Memory was read or written | `record_memory(memory_id, operation)` |
| A human approved or interrupted | `record_human_interaction(...)` |

Use only callbacks documented for the framework version you test against. If
it has none, record at the boundary only, and let application code call
`record_evidence` and `record_decision`.

Callbacks that run in another thread lose the active run. Pass `run=` from
the `capture` block, or run them with `contextvars.copy_context().run(...)`.
Synchronous callbacks call coroutines through `self.runtime.run_sync(...)`.

## Shipping it

- Keep the instrumentor in the application, or publish it as its own package
  that depends on `agxai` and the framework; agxai bundles no adapters for
  other frameworks.
- Test it against the framework version you pin, starting from
  `assets/test_instrumentor.py`.
- Document which entry points are recorded and which are not.
