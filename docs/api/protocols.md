# Capabilities

The runtime resolves each capability through its `Registry`. Storage is an
abstract base class; the other capabilities are protocols that a provider
satisfies structurally. See [Extensibility](../architecture/plugins.md) for the
contracts each provider must keep.

```python
from agxai import PolicyProvider, ProvenanceStore

runtime.register(ProvenanceStore, MyDatabaseStore())
runtime.register(PolicyProvider, MyPolicy())
```

## Storage

::: agxai.core.protocols.ProvenanceStore

::: agxai.core.protocols.StoreQuery

## Observability

::: agxai.core.protocols.ObservabilityProvider

## Policies

::: agxai.core.protocols.CapturePolicy

::: agxai.core.protocols.PolicyProvider

## Attribution and explanation

::: agxai.core.protocols.AttributionEngine

::: agxai.core.protocols.ExplanationEngine
