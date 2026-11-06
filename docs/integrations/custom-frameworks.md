# Custom frameworks: Agno, CrewAI, and others

The core runtime has no agent-framework dependency:

```bash
pip install agxai
```

`agxai` ships an optional LangGraph/LangChain integration. Agno, CrewAI, and
other frameworks can be connected by developers through the
`FrameworkInstrumentor` abstract base class. These are extension possibilities,
not claims of bundled or certified adapters.

## Implement the call boundary

Subclass `FrameworkInstrumentor[Target, Instrumented]` and implement
`instrument(target)`. Preserve the framework's inputs, outputs, errors, and
sync/async contract. For an async callable:

```python
from collections.abc import Awaitable, Callable

from agxai import FrameworkInstrumentor

type Agent = Callable[[float], Awaitable[str]]


class AgentInstrumentor(FrameworkInstrumentor[Agent, Agent]):
    def instrument(self, target: Agent) -> Agent:
        async def call(amount: float) -> str:
            async with self.capture():
                return await target(amount)

        return call
```

Construct your adapter with a runtime, then call
`AgentInstrumentor(runtime).instrument(agent)`. For a synchronous callable, use
`with self.capture_sync():` instead. For streaming APIs, keep the capture
context open for the entire iteration, including early closure; do not close
the run when merely returning an iterator.

The helpers start and activate a run, so `runtime.current_run` and the `record_*`
methods work inside the wrapped call. They finish the run as completed,
failed, or cancelled and re-raise application exceptions. They restore the
previous context on exit. Nested calls using the same runtime reuse the
outer run rather than duplicating it; independent concurrent calls get separate
runs. `runtime.collect_runs()` captures these runs just as it does for LangGraph.
Instrumentation failures follow the runtime's configured failure mode.

`XAIRuntime.instrument()` is specifically the lazy LangGraph convenience;
custom instrumentors are called explicitly and are not auto-discovered or
registered in the capability registry.

## Map framework events to canonical records

Wrap the top-level agent or crew invocation, then use the framework's public
hooks or callbacks to record only facts you actually observe:

| Observed activity | Runtime method |
| --- | --- |
| Agent step or task | `record_node` |
| State before and after a step | `record_state_delta` |
| Tool call | `record_tool` |
| Retrieved documents | `record_retrieval` |
| Evidence the application used | `record_evidence` |
| Decision the application made | `record_decision` |
| Artifact lineage | `record_provenance` |
| Approval or review | `record_human_interaction` |

For Agno, wrap the agent entry point your application invokes and translate
its public lifecycle hooks. For CrewAI, wrap the crew/task invocation and
translate public task/tool callbacks. Install those frameworks separately and
test against their supported versions. The framework-free example does not
rely on unverified SDK signatures.

If a framework executes callbacks in another thread or process, propagate
the run explicitly with `run=`; Python context variables do not automatically
cross every framework boundary. The `graph_id` field is retained as a stable
identifier for the workflow, crew, or agent being explained.

For explicit lifecycle management, use `start_run`, `activate_run`, and
`finish_run`. `finish_run(interrupts=...)` accepts any object satisfying
`agxai.core.InterruptLike` (`id` and `value` properties); no LangGraph type is
required. Adapters implementing resumable calls must also map their
framework's pause/resume and checkpoint semantics, not infer them from output.

## Validate your integration

Test output and exception preservation, sync and async calls, nested and
concurrent calls, cancellation, and context cleanup. Verify that every supported
entry point produces exactly the expected runs and artifacts. Add framework
dependencies only to your integration's extra or application, never to the
agxai core.

Run the [complete dependency-free example](../examples/custom-framework.md),
then see the [API reference](../api/integrations.md). Storage and telemetry
remain independent extension points: `ProvenanceStore` and
`ObservabilityAdapter` are ABCs; other capability contracts are structural
protocols, as described in [Extensibility](../architecture/plugins.md).
