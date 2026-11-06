---
name: agxai-extend
description: >-
  Use this skill when extending agxai to a new agent framework or a new storage
  backend. That includes writing a FrameworkInstrumentor subclass for Agno,
  CrewAI, AutoGen, Semantic Kernel, a custom agent loop, or any framework agxai
  does not bundle, and writing a ProvenanceStore subclass for PostgreSQL,
  MySQL, SQLite, MongoDB, DynamoDB, Redis, or another database. Also use it to
  debug or test such an adapter: failing ProvenanceStoreContract tests, runs
  that are not recorded, or nested calls that start extra runs. Do not use it
  to instrument a LangGraph or LangChain application, configure disclosure
  policies, or export to LangSmith, Langfuse, or OpenTelemetry; the agxai
  skill covers those.
license: Apache-2.0
compatibility: >-
  Python 3.12 or newer with agxai 1.x installed (pip install agxai). No agent
  framework is required by the templates; the scripts run offline.
metadata:
  version: "1.0.2"
  documentation: "https://agxai.readthedocs.io/en/latest/integrations/custom-frameworks/"
---

# Extending agxai

agxai's core has two extension points. Both are abstract base classes, and
neither needs LangGraph:

- `FrameworkInstrumentor` records each call of a framework as a run.
- `ProvenanceStore` keeps executions, events, and provenance links in your
  database.

Pick the workflow that matches the task. If the task needs both, write the
store first: the instrumentor's tests can then use it.

## Workflow: a framework instrumentor

1. Find the framework's top-level entry points (for example `run` and `arun`,
   or `kickoff` and `kickoff_async`), and any public step or tool callbacks,
   in the version the project pins. Do not invent callbacks.
2. Copy `assets/instrumentor_template.py` into the project. Point `Agent` at
   the framework's agent class and adapt `InstrumentedAgent` to its entry
   points. Wrap each async
   entry in `async with self.capture(config):` and each sync entry in
   `with self.capture_sync(config):`.
3. Forward every other attribute unchanged. Return results unchanged and let
   exceptions propagate.
4. If the framework has callbacks, translate them with `step`, `tool_call`,
   or the `record_*` methods. Read [references/instrumentor.md](references/instrumentor.md)
   for the event-to-call mapping, streaming, and thread rules.
5. Copy `assets/test_instrumentor.py`, replace `ScriptedAgent` with a small
   real agent, and run it until it passes.

## Workflow: a storage backend

1. Copy `assets/store_template.py`. Replace each `self._rows` operation with
   the database call its comment names. Keep the key, the ordering, and the
   subclass-aware `item_type` filter.
2. Copy `assets/test_store_contract.py` and make `make_store` return a new,
   empty store on a disposable database.
3. Run the contract tests, or `python scripts/check_store.py module:factory`
   from the project root. Fix the first failing promise, then rerun. Repeat
   until every promise holds. Read [references/store.md](references/store.md)
   when a failure is unclear or for the reference table layout.
4. Register the store with `runtime.register(ProvenanceStore, store)` and run
   one real call.

## Checklist before you finish

- [ ] The adapter returns the framework's results and raises its exceptions unchanged.
- [ ] Each top-level call records exactly one run; nested calls join it.
- [ ] Every `ProvenanceStoreContract` test passes against the real database.
- [ ] The project's own tests pass.

## Gotchas

- **Observe, never steer.** Never change inputs, outputs, control flow, or
  retries to make recording work.
- `XAIRuntime.instrument()` is the LangGraph shortcut, not a generic
  dispatcher. Call your own `MyInstrumentor(runtime).instrument(agent)`.
- `capture` reuses an already active run of the same runtime. Use one runtime
  per application, or nested calls start unrelated runs.
- A callback on another thread has no active run. Pass `run=` or copy the
  context.
- The store key is application, tenant, run, record type, and ID. The same ID
  in another tenant or run is a different record, and a rewrite of the same
  key replaces it.
- `query` must match subclasses: `item_type=XAIEvent` selects every event.
- `delete_run` returns `0` for an unknown run; it must not raise.
- Return new objects from reads. Callers may mutate them.
- Evidence and decisions never reach the store. Persist them with an
  `XAIPlugin` subclass if needed.
- psycopg's async mode on Windows needs
  `asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)`.

## Files

- `assets/instrumentor_template.py` and `assets/test_instrumentor.py`: the
  instrumentor to copy, and the tests it must pass.
- `assets/store_template.py` and `assets/test_store_contract.py`: a store
  shaped like one table, and the contract it must pass.
- `scripts/check_store.py`: runs the contract against any store factory
  without pytest. Run `--help` for options; `--json` prints one object.
  Exit codes are 0 (all pass), 1 (a promise broken), and 2 (factory not
  loadable).
- [references/instrumentor.md](references/instrumentor.md): boundaries,
  callbacks, streaming, threads, shipping.
- [references/store.md](references/store.md): the six methods, table
  layout, ordering, custom query types.
