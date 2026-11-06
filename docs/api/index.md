# API reference

Generated from the docstrings of the public API. The classes you use day to day
are importable from the top-level `agxai` package; optional framework classes
are imported from their integration modules. Each entry below
shows the module where the class is defined.

| Page | Contents |
| --- | --- |
| [Runtime](runtime.md) | `XAIRuntime`, `Run`, `XAIInstrumentationError`, `Registry`, `RUN_ID_METADATA_KEY` |
| [Framework integrations](integrations.md) | `FrameworkInstrumentor`, optional `LangGraphInstrumentor` and `InstrumentedGraph`, `RunInterrupt` |
| [Configuration](config.md) | `XAIConfig` |
| [Canonical models](models.md) | Execution records, decision records, explanation records, events, and enumerations |
| [Capabilities](contracts.md) | The capability abstract base classes, from `ProvenanceStore` to `ExplanationEngine` |
| [Storage](storage.md) | `InMemoryProvenanceStore`, `StoreFilter` |
| [Observability](observability.md) | LangSmith, Langfuse, OpenTelemetry, and no-op adapters, the adapter base class, helpers, and errors |
| [Explanation engines](explanation.md) | `StructuredExplanationEngine`, `LLMExplanationEngine`, `ExplanationDraft` |
| [Attribution engines](attribution.md) | `HybridAttribution`, `RuleBasedAttribution`, `EvidenceAttribution` |
| [Policies](policy.md) | `DefaultCapturePolicy`, `DefaultPolicyProvider`, and the redaction helpers |
| [Plugins](plugins.md) | `XAIPlugin`, `PluginManager` |
| [Testing](testing.md) | `ProvenanceStoreContract`, the conformance tests for custom stores |

## Stability

- The public API is everything listed in this reference. Names that start with
  an underscore are private and may change at any time.
- Serialized records are versioned contracts, identified by their
  `schema_version`. See [Canonical model](../architecture/canonical-model.md#compatibility).
- Breaking changes happen only in major releases, and each one is listed in
  the [changelog](https://github.com/smuniharish/agxai/blob/master/CHANGELOG.md).
