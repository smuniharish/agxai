# Runtime

The runtime coordinates capture, storage, attribution, policy, and explanation
for one application. See [Runtime architecture](../architecture/runtime.md) for
how runs, context propagation, concurrency, and failures work.

```python
from agxai import XAIRuntime

runtime = XAIRuntime(application_id="payments", tenant_id="acme-bank", graph_id="fraud-review")
graph = runtime.instrument(compiled_graph)
```

## XAIRuntime

::: agxai.runtime.runtime.XAIRuntime

## Run

::: agxai.runtime.runtime.Run

## XAIInstrumentationError

::: agxai.runtime.runtime.XAIInstrumentationError

## Registry

::: agxai.runtime.registry.Registry

The optional graph proxy and framework extension ABC are documented under
[Framework integrations](integrations.md).

## Run ID metadata key

::: agxai.runtime.runtime.RUN_ID_METADATA_KEY
