# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.2] - 2026-11-06

### Breaking

Every extension point is now an abstract base class that providers must
subclass. A class that only has the right methods is rejected, so a missing
method fails when the provider is defined, not on the first call.

- `ObservabilityProvider`, `CapturePolicy`, `PolicyProvider`,
  `AttributionEngine`, `ExplanationEngine`, and `XAIPlugin` change from
  `typing.Protocol` to abstract base classes, like `ProvenanceStore` and
  `FrameworkInstrumentor` already were. Add the base class to existing
  providers, for example `class MyPolicy(PolicyProvider):`.
  `XAIRuntime.register`, `Registry.register`, and `PluginManager` raise
  `TypeError` for a provider that does not subclass its capability.
- `ObservabilityProvider` and `XAIPlugin` provide no-op `flush` and `close`,
  and `ExplanationEngine` defaults `requires_llm` to `False`, so subclasses
  implement only `emit`, `record`, or `explain`.
- `agxai.core.protocols` is renamed `agxai.core.contracts`. Imports from
  `agxai` and `agxai.core` are unchanged.
- `InterruptLike` is replaced by the `RunInterrupt` value type (`id`,
  `value`). `XAIRuntime.finish_run(interrupts=...)` takes `RunInterrupt`s;
  the LangGraph integration converts LangGraph interrupts itself.
- `Registry.get` no longer re-checks a provider on every lookup; registration
  already guarantees the type.

### Added

- Python 3.15 is tested and declared.

## [1.0.1] - 2026-11-06

agxai records what an AI agent did, the evidence it relied on, and the
decisions it made, and explains each decision to one audience at a time under
a disclosure policy. This release describes the complete public API.

### Runtime

- `XAIRuntime` scopes every record to an application, tenant, and graph, and
  is the single entry point: `instrument`; `record_evidence`,
  `record_decision`, `record_retrieval`, `record_tool`, `record_node`,
  `record_state_delta`, `record_memory`, `record_provenance`,
  `record_artifact`, `record_human_interaction`, and `record_checkpoint`;
  `start_run`, `finish_run`, `activate_run`, and `collect_runs`; `attribute`,
  `explain`, and `explain_decision`; and `run_sync`, `flush`, and `close`.
- `XAIConfig` sets the failure mode (`FAIL_OPEN`, `FAIL_CLOSED`, `STRICT`),
  state capture (`FULL`, `DELTA`, `SELECTIVE`, `CUSTOM`, `NONE`), concurrency,
  timeouts, and checkpoint capture. Under
  `FAIL_OPEN` instrumentation never breaks the application: errors are kept in
  `XAIRuntime.errors` and logged as `WARNING`s on the `agxai` logger, which has
  a `NullHandler`. Explanations fail closed in every mode.
- `Registry` and `XAIRuntime.register` replace any provider: storage,
  observability, capture policy, disclosure policy, attribution, and
  explanation engines.

### Records

- A versioned canonical model (`schema_version` `"2.0.0"`) of Pydantic
  records: `Execution`, `NodeExecution`, `ToolExecution`, `StateTransition`,
  `Evidence`, `Decision` with `DecisionFactor`, `RetrievedDocument`,
  `HumanInteraction`, memory references, `ProvenanceLink`, and typed events. Timestamps are
  timezone-aware, numbers finite, and unknown fields rejected.
- State capture records changed keys only by default. Credential-named keys
  (`api_key`, `token`, `Set-Cookie`, `accessToken`, and similar) are never
  recorded with their values.

### Frameworks

- The core is framework-neutral and depends only on Pydantic.
- `agxai[langgraph]` instruments LangGraph graphs and LangChain Runnables
  through `XAIRuntime.instrument()`. It records nodes, state changes, tools,
  retrievers, interrupts, `Command(resume=...)` answers, static breakpoints,
  and checkpoints on every sync, async, streaming, batch, and
  `astream_events` entry point. Resumed, retried, and replayed runs name the
  run they continue in `Execution.continuation_of`.
- `FrameworkInstrumentor` is the abstract base class for other frameworks,
  such as Agno, CrewAI, or a custom agent loop, with `capture()` and
  `capture_sync()` run scopes. `examples/custom_framework.py` is a
  dependency-free integration.

### Explanations and disclosure

- `explain` and `explain_decision` build an explanation for an `Audience`
  (developer, auditor, business, or end user) from recorded evidence
  and decisions, never from model chain-of-thought.
- A `PolicyProvider` decides per audience which sections are shown; withheld
  sections are announced, not silently dropped. `DefaultPolicyProvider` and
  `DefaultCapturePolicy` are the defaults.
- `RuleBasedAttribution`, `EvidenceAttribution`, and `HybridAttribution`
  weigh decision factors and evidence. `StructuredExplanationEngine` phrases
  explanations deterministically; `LLMExplanationEngine` (`agxai[llm-openai]`
  or any LangChain chat model) phrases them with a model, after the policy
  filtered them.

### Storage

- `ProvenanceStore` is the abstract base class for persistence: implement
  `write`, `get`, `query`, `children`, `parents`, and `delete_run`; `lineage`
  and `close` are inherited. Records are keyed by application, tenant, run,
  record type, and ID, so tenants and runs never overwrite each other.
  `delete_run` serves erasure requests and retention jobs.
- `InMemoryProvenanceStore` is the default.
  `examples/postgres_store.py` is a tested JSONB store to copy.
- `agxai.testing.ProvenanceStoreContract` checks any store against the full
  store contract under pytest or `unittest`.

### Observability

- One `ObservabilityProvider` receives every event: `LangSmithObservability`
  (`agxai[langsmith]`), `LangfuseObservability` (`agxai[langfuse]`),
  `OpenTelemetryObservability` (`agxai[otel]`), or `NoOpObservability`.
  `ObservabilityAdapter` and its helpers build new ones.
- `XAIPlugin` instances receive evidence, decisions, and semantic artifacts.

### Tooling

- Python 3.12 to 3.15, fully typed (`py.typed`), with 100% statement and
  branch coverage, property-based tests, a LangGraph feature matrix, and
  offline tests of the model-backed examples with a fake chat model. Live
  suites cover PostgreSQL, OpenTelemetry, Langfuse, and LLM endpoints.
- Fourteen runnable examples, and `scripts/benchmark_overhead.py` for latency
  and memory overhead.
- Agent Skills for coding agents: `agxai` to integrate the package and
  `agxai-extend` to write framework instrumentors and stores, each with
  evaluations.
- Documentation built with Zensical, with a generated API reference, rendered
  architecture diagrams, and a link check over the built site.

[1.0.2]: https://github.com/smuniharish/agxai/releases/tag/v1.0.2
[1.0.1]: https://github.com/smuniharish/agxai/releases/tag/v1.0.1
