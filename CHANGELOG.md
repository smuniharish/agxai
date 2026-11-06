# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- Framework-neutral `agxai` core with Pydantic as its only direct dependency.
- Optional `agxai[langgraph]` extra for LangGraph graphs and LangChain Runnables,
  exposed through `agxai.integrations.langgraph`.
- `FrameworkInstrumentor` ABC with sync/async run capture for developer-written
  integrations, plus a dependency-free custom-agent example.
- `XAIRuntime.activate_run` for context-scoped recording and `InterruptLike`
  for framework-neutral interrupt payloads.
- Framework-neutral guides, package paths, skills, tooling, and tests.
- Documentation, examples, and skills name the runtime instance `runtime`
  (`runtime = XAIRuntime()`, `runtime.instrument(...)`) instead of `xai`, so it
  is not mistaken for a module. Record keys such as `xai.run_id` are unchanged.
- Dependency floors raised to the latest releases, including `langfuse` 5
  (`agxai[langfuse]` now requires `langfuse>=5.2.0,<6`), `pydantic>=2.14.3`,
  `langchain-core>=1.7.6`, and `langgraph>=1.2.20`; the build backend is
  `uv_build>=0.13.7,<0.14`.
- The model-backed examples and the LLM explanation engine are tested offline
  with a scripted LangChain fake chat model; real-provider runs stay opt-in.
- `.env.example` lists only variables something reads, grouped by consumer.

### Breaking changes

- `ProvenanceStore.get` takes a keyword-only `context` and looks the ID up
  within that run only; it raises `LookupError` when records of different
  types share the ID in the run.
- `ProvenanceStore.delete_run(context)` is a new abstract method: it deletes
  every record of one run, returns how many were deleted, and is idempotent.
  Use it for erasure requests and retention jobs. Custom stores must
  implement it.
- Stores key records by application, tenant, run, record type, and ID. Before,
  a record whose ID repeated in another tenant or run replaced the first one;
  it is now a separate record. `InMemoryProvenanceStore` and the PostgreSQL
  example both changed.
- The PostgreSQL example stores records in a new table, `agxai_records`,
  whose primary key is `(application_id, tenant_id, run_id, record_type,
  record_id)`, replacing `langgraph_xai_records` and its `record_key` column.
  Call `await store.migrate_legacy_table()` once after `open()`: in one
  transaction it moves every old row under the new key and drops the old
  table, and it does nothing when there is no old table.

### Added

- `agxai.testing.ProvenanceStoreContract`, a conformance kit that checks any
  `ProvenanceStore` against every promise of the store contract under pytest
  or `unittest`. The in-memory store and the live PostgreSQL store run it.
- `fail_open` failures are logged as `WARNING`s with their traceback on the
  `agxai.runtime.runtime` logger. The `agxai` logger has a `NullHandler`, so
  nothing is printed unless the application configures logging.
- `scripts/benchmark_overhead.py` measures latency percentiles and peak memory
  of instrumented graphs and per-event emit latency for each provider.

### Fixed

- The PostgreSQL example's `query` now matches subclasses of `item_type`, so
  `StoreFilter(item_type=XAIEvent)` returns every event, as the in-memory store
  does.

## [1.0.0] - 2026-10-04

The first stable release. The public API, the canonical schema (`schema_version`
`"2.0.0"`), and the extension contracts now follow semantic versioning. Records
written by 0.1.0 (schema `"1.0.0"`) are not migrated.

### Breaking changes

#### Canonical schema 2.0.0

- `SCHEMA_VERSION` is `"2.0.0"`, and every model rejects other versions.
- Removed fields that automatic capture never filled and no API could set:
  - `ExecutionContext.span_id` and `parent_id`, so the `xai.span_id` and
    `xai.parent_id` correlation attributes are no longer emitted;
  - `Execution.parent_execution_id`;
  - `NodeExecution.node_name`, `input_reference`, `output_reference`, and
    `error_id`;
  - `ToolExecution.retry_count`, `error_id`, `downstream_consumers`, and
    `related_decisions`;
  - `StateTransition.influences` and `MemoryReference.influenced`;
  - `HumanInteraction.continuation_run_id`; use `Execution.continuation_of`;
  - `ExceptionEvent.retryable`, `attempt`, and `traceback_reference`;
  - `PolicyDecision.obligations` and `ExplanationContext.provenance`.
- Events have a single identity, `id`. `XAIEvent.event_id` and the unused
  `XAIEvent.payload` were removed. The `xai.event_id` correlation attribute,
  observability deduplication, LangSmith child run IDs, and store keys all use
  the event's `id`.
- Removed enum values `ExecutionStatus.PENDING` and `PARTIAL`,
  `ToolStatus.RUNNING`, and `PolicyAction.RETAIN` and `PROCESS`.
- Timestamps must be timezone-aware, and numbers must be finite.

#### Runtime and instrumentation

- Removed the `agxai.instrument()` function; use
  `XAIRuntime.instrument()`.
- `XAICallbackHandler` and `AsyncXAICallbackHandler` are no longer public.
  `XAIRuntime.instrument()` attaches them for you.
- Removed internal plumbing from the public API: `XAIRuntime.enter`, `exit`,
  and `is_instrumenting`, the `XAIRuntime.max_concurrency` and `timeout`
  attributes (read them from `XAIRuntime.config`), and `Run.lock`,
  `Run.sequence`, and `Run.next_sequence()`.
- `record_human_interaction` no longer accepts `continuation_run_id`. Resumed
  runs are linked automatically; `start_run(continuation_of=...)` links a
  manually managed run.
- `finish_run(interrupts=...)` accepts interrupt objects with `id` and `value`, and
  `run_sync` accepts only coroutines.
- `explain` and `explain_decision` raise `XAIInstrumentationError` in every
  failure mode when the exposure policy, attribution, or engine fails, instead
  of returning an unfiltered explanation.
- An event dropped by the capture policy is no longer added to the run's
  `Execution`, and an event whose capture policy fails is dropped.
- `HybridAttribution` normalizes decision factors and evidence separately
  before weighting, so `rule_weight` and `evidence_weight` are the shares each
  source receives. Attribution scores differ from 0.1.0.
- The withheld-attribution note now reads "Contributing factors are withheld
  by policy.", and withholding `contributing_factors` also removes factor
  values from `reasons`.

#### Storage

- `ProvenanceStore` is an abstract base class instead of a protocol. Custom
  stores subclass it and implement `write`, `get`, `query`, `parents`, and
  `children`; `lineage` and `close` are inherited.
- `PostgresProvenanceStore` and the `postgres` extra were removed. The store is
  now a tested example, `examples/postgres_store.py`, to copy into your
  application.

#### Observability

- Adapters call the SDK clients directly and are typed against them:
  `langsmith.Client`, `langfuse.Langfuse`, and the OpenTelemetry SDK
  `TracerProvider`. `OpenTelemetryObservability(owns_provider=True)` requires
  `tracer_provider`.
- Removed the `maybe_await` and `callable_or_error` helpers.
  `optional_import(module, extra)` takes the name of the extra to install.

#### Removed aliases and settings

- `Config`; `Event`, `EventUnion`, `ExecutionRecord`, `Attribution`,
  `Relation`, `StateCaptured`, `ExecutionStarted`, `ExecutionCompleted`,
  `ExecutionFailed`, and `VERSION` in `agxai.core.models`; `Storage`,
  `Observability`, `AttributionProvider`, `ExplanationProvider`, `Policy`, and
  `Capture` in `agxai.core.protocols`; `LangSmithProvider`,
  `LangfuseProvider`, `NoOpProvider`, `OTelObservability`, and
  `OpenTelemetryProvider` in `agxai.observability`. Use the canonical
  names.
- `XAIConfig.event_queue_size`, the private `agxai._internal` package,
  and the `docs` extra (documentation tooling is a development dependency
  group).

#### Dependencies

- Requires `langchain-core>=1.6.6`, `langgraph>=1.2.12`, and
  `pydantic>=2.13.5`. The extras require `langsmith>=0.14.4`,
  `langfuse>=4.16.0`, `opentelemetry-api` and `opentelemetry-sdk>=1.45.0`, and
  `langchain-openai>=1.6.7`.

### Added

- **Automatic checkpoints.** For a graph compiled with a checkpointer and
  called with a `thread_id`, every run records the checkpoint it ended at, and
  a resumed run records the checkpoint it continued from. Turn it off with
  `XAIConfig.capture_checkpoints=False`.
- **Resume links.** `Execution.continuation_of` names the run a resumed,
  retried, or replayed call continued from, across processes when the
  checkpointer is durable. The run ID is stored in checkpoint metadata under
  `RUN_ID_METADATA_KEY` (`"agxai_run_id"`).
- Static breakpoints (`interrupt_before` and `interrupt_after`) record the run
  as `interrupted` with the pending nodes.
- `astream_events`, `batch_as_completed`, `abatch_as_completed`, `transform`,
  and `atransform` are recorded like the other entry points. Calls that cannot
  be recorded, LangGraph's experimental v3 streaming protocol (`stream_events`
  and `astream_events(version="v3")`) and LangChain's deprecated
  `astream_log`, reach the graph unchanged and are handled by the failure
  mode: kept in `XAIRuntime.errors` under `FAIL_OPEN`, and refused with
  `XAIInstrumentationError` under `FAIL_CLOSED` and `STRICT`.
- `XAIRuntime.collect_runs()` returns the runs started inside a `with` block,
  and `XAIRuntime.explain_decision()` explains a recorded decision with the
  evidence it references.
- `XAIRuntime.record_checkpoint()` links a checkpoint by hand, and
  `XAIRuntime.record_node()` records a node execution explicitly.
- `start_run(continuation_of=...)` and `finish_run(pending_nodes=...)` for
  runs managed by hand.
- `record_evidence` accepts `source` and `quality`; `record_decision` accepts
  `provenance_ids`, `policy_references`, and `uncertainty`.
- `Run.run_id`, `Run.evidence`, and `Run.decisions`.
- The answer passed to `Command(resume=...)` is recorded on the run's `resume`
  interaction.
- A non-empty `PolicyDecision.allowed_fields` acts as an allowlist of
  explanation sections.
- `ObservabilityAdapter`, `correlation_fields`, `event_payload`, and
  `langfuse_trace_context` for building adapters. The LangSmith, Langfuse, and
  OpenTelemetry adapters accept `deduplication_window`,
  `OpenTelemetryObservability` accepts
  `tracer_provider` and `owns_provider`, and `LangSmithObservability` accepts
  `max_open_traces`.
- Top-level exports for `AttributionResult`, `CapturePolicy`,
  `MemoryOperation`, `NodeExecution`, `PolicyAction`, `PolicyDecision`,
  `RUN_ID_METADATA_KEY`, `SourceReference`, `StateTransition`,
  `ToolExecution`, and `__version__`. `agxai.policy` exports
  `REDACTED` and `is_sensitive_key`, and `agxai.storage` exports
  `ProvenanceStore` and `StoreQuery`.
- An Agent Skill in the open Agent Skills format, with references, a setup
  check, and a test template, so coding agents integrate the package
  correctly.
- Thirteen runnable examples, including a fraud review with a full
  explanation, retrieval and tools, human-in-the-loop with automatic
  checkpoints, the PostgreSQL store, and a disclosure matrix that checks every
  policy, audience, and engine. The test suite runs every example except the
  MCP browser agent, which needs Node.js and a browser.
- Property-based tests with Hypothesis, a LangGraph feature matrix (every entry
  point, output version, and stream mode; `Send`; the functional API; node
  caching; subgraphs; static breakpoints), 100% statement and branch coverage,
  and live test suites for PostgreSQL, OpenTelemetry, Langfuse, and LLM
  endpoints.
- A rewritten documentation site with rendered architecture diagrams that open
  full size when clicked, real output on every example page, and a generated
  API reference.
- Continuous integration for lint, types, tests on Python 3.12 to 3.14 with
  warnings as errors, the lowest supported dependency versions, the built
  package, the Agent Skill, the documentation, and the diagrams; a release
  workflow that publishes to PyPI with trusted publishing; and Dependabot.

### Changed

- The package is marked `Development Status :: 5 - Production/Stable`.
- State capture records only changed keys by default. Credential-named keys
  are never recorded with their values: `FULL` capture shows them as
  `"[not captured]"`, and other modes omit them.
- Redaction recognizes more credential names (`Set-Cookie`, `x-api-key`,
  `accessToken`, `basic_auth`, `jwt`, and more) without matching ordinary keys
  such as `max_tokens`, and converts dates, UUIDs, decimals, paths, bytes,
  sets, models, and dataclasses to JSON-safe values.
- Attribution confidence is the mean evidence strength, and `None` for
  rule-based attribution.
- Lower overhead. A five-node graph adds about 2 ms per call, down from about
  10 ms. Synchronous calls reuse one event loop per thread, and calls made from
  a thread that already runs an event loop, such as a Jupyter notebook, reuse
  one background loop per thread. The default capture policy and the no-op
  observability provider are skipped instead of called for every event.
- Concurrency slots are granted first come, first served across threads and
  event loops, and a waiting operation is woken as soon as a slot frees up.
- The LLM explanation prompt names the sections withheld by policy, so the
  model no longer claims that withheld facts are missing.
- A missing optional SDK raises `OptionalDependencyError` with the extra to
  install.
- LLM-backed examples default to `gpt-4o-mini`; set `OPENAI_MODEL` to change
  it.

### Fixed

- Interrupts were missed, and the run recorded as `completed`, with
  `version="v2"` output, several stream modes, `subgraphs=True`, or
  `stream_mode="messages"`. Interrupts are now taken from LangGraph itself and
  deduplicated by ID.
- `astream_events`, `batch_as_completed`, `abatch_as_completed`, `transform`,
  `atransform`, `stream_events`, and `astream_log` ran the graph without
  recording a run or reporting the gap.
- State transitions recorded unchanged keys as `None`, mishandled `Command`
  and list outputs, and treated internal runnables as nodes.
- `FAIL_CLOSED` errors raised inside a graph were swallowed by LangChain's
  callback manager.
- Retriever names, tool-call IDs, and Pydantic state values were captured
  incorrectly.
- LangSmith root runs were never ended, Langfuse emits failed for trace IDs
  that were not hexadecimal, and OpenTelemetry spans carried a Python repr
  instead of JSON.
- Records added after a run finished, such as approvals made outside the
  graph, were missing from the stored `Execution`.
- Factor values, source metadata, and retrieved-document metadata supplied by
  the caller were not redacted.
- Cancelled or closed streams recorded an empty exception message.
- The concurrency limit was not shared across threads and event loops, the
  observability deduplication set grew without bound, and batch calls did not
  set the current run.

## [0.1.0] - 2026-09-19

### Added

- Initial public release of `agxai`.
- Canonical explainability models: `Execution`, `ProvenanceLink`, `Evidence`,
  `Decision`, `Attribution`, `Explanation`, and policy primitives.
- `XAIRuntime` with a provider registry, run lifecycle management
  (`start_run` / `finish_run`), and `instrument()` for wrapping compiled
  LangGraph graphs.
- Storage backends: in-memory (`InMemoryProvenanceStore`) and PostgreSQL
  (`PostgresProvenanceStore`).
- Observability integrations: LangSmith, Langfuse, and OpenTelemetry.
- Attribution engines (rule-based, heuristic, hybrid) and explanation
  engines (template-based and LLM-based).
- Policy-aware disclosure via `PolicyProvider` with audience-scoped exposure
  rules.
- Documentation site (MkDocs Material) covering concepts, guides, API
  reference, and integrations.
