# Persisting and exporting records

Read this file when records must outlive the process or reach a tracing backend. To write a `ProvenanceStore` for your own database, use the `agxai-extend` skill.

## Persist evidence and decisions with a plugin

Evidence, decisions, and memory references are not written to the store.
Persist them with a plugin:

```python
class DecisionArchive:
    async def record(self, artifact) -> None: ...  # Evidence, Decision, MemoryReference, ...
    async def flush(self) -> None: ...
    async def close(self) -> None: ...


runtime = XAIRuntime(plugins=(DecisionArchive(),))
```

## Send events to a tracing backend

One `ObservabilityProvider` receives every event. Install the extra first.

```python
from agxai import ObservabilityProvider, OpenTelemetryObservability

runtime.register(
    ObservabilityProvider,
    OpenTelemetryObservability(tracer_provider=provider, owns_provider=True),
)
```

| Backend | Extra | Provider |
| --- | --- | --- |
| LangSmith | `agxai[langsmith]` | `LangSmithObservability(project_name="...")` |
| Langfuse | `agxai[langfuse]` | `LangfuseObservability()` |
| OpenTelemetry | `agxai[otel]` | `OpenTelemetryObservability(tracer_provider=...)` |

Credentials come from each SDK's own environment variables. Call
`await runtime.close()` at shutdown so batched data is sent.
