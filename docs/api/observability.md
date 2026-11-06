# Observability

Adapters that forward canonical events to tracing backends. Each adapter
belongs to an extra: `langsmith`, `langfuse`, or `otel`. See
[Integrations](../integrations/index.md) for setup and
[Observability architecture](../architecture/observability.md) for the
guarantees they share.

```python
from agxai import ObservabilityProvider, OpenTelemetryObservability

runtime.register(ObservabilityProvider, OpenTelemetryObservability(tracer_provider=provider))
```

## Adapters

::: agxai.observability.langsmith.LangSmithObservability

::: agxai.observability.langfuse.LangfuseObservability

::: agxai.observability.otel.OpenTelemetryObservability

::: agxai.observability.noop.NoOpObservability

## Building an adapter

::: agxai.observability.base.ObservabilityAdapter

::: agxai.observability.base.correlation_fields

::: agxai.observability.base.event_payload

::: agxai.observability.langfuse.langfuse_trace_context

## Errors

::: agxai.observability.errors.ObservabilityAdapterError

::: agxai.observability.errors.AdapterClosedError

::: agxai.observability.errors.OptionalDependencyError
