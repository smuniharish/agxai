# Capabilities

The runtime resolves each capability through its `Registry`. Every capability
is an abstract base class: a provider subclasses it and implements its abstract
methods, and `runtime.register` raises `TypeError` for anything else. See
[Extensibility](../architecture/plugins.md) for the contracts each provider
must keep.

```python
from agxai import PolicyProvider, ProvenanceStore

runtime.register(ProvenanceStore, MyDatabaseStore())
runtime.register(PolicyProvider, MyPolicy())
```

## Storage

::: agxai.core.contracts.ProvenanceStore

::: agxai.core.contracts.StoreQuery

## Observability

::: agxai.core.contracts.ObservabilityProvider

## Policies

::: agxai.core.contracts.CapturePolicy

::: agxai.core.contracts.PolicyProvider

## Attribution and explanation

::: agxai.core.contracts.AttributionEngine

::: agxai.core.contracts.ExplanationEngine
