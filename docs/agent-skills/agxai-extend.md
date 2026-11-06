# The agxai-extend skill

The `agxai-extend` skill teaches a coding agent to extend agxai through its two
abstract base classes. Neither needs LangGraph:

- a `FrameworkInstrumentor` records each call of an agent framework as a run.
  Use it for Agno, CrewAI, AutoGen, Semantic Kernel, your own agent loop, or
  any framework agxai does not bundle.
- a `ProvenanceStore` keeps executions, events, and provenance links in your
  database: PostgreSQL, MySQL, SQLite, MongoDB, DynamoDB, Redis, or any other.

[:material-github: View on GitHub](https://github.com/smuniharish/agxai/tree/master/agxai-skills/skills/agxai-extend){ .md-button }
[:material-download: Install](index.md#agentic-installation){ .md-button }

## When the agent uses it

The agent loads the skill to write, test, or debug such an adapter. Examples
include failing `ProvenanceStoreContract` tests, runs that are not recorded,
and nested calls that start extra runs.

To instrument a LangGraph or LangChain application, configure disclosure, or
export to a tracing backend, it hands over to the [agxai skill](agxai.md).

## Workflows

=== "A framework instrumentor"

    1. Find the framework's top-level entry points, and any public step or
       tool callbacks, in the version the project pins.
    2. Copy `assets/instrumentor_template.py`. Wrap each async entry point in
       `capture` and each sync entry point in `capture_sync`.
    3. Forward every other attribute unchanged. Return results unchanged and
       let exceptions propagate.
    4. Translate the framework's callbacks into node and tool records.
    5. Adapt `assets/test_instrumentor.py` to a small real agent and run it
       until it passes.

=== "A storage backend"

    1. Copy `assets/store_template.py`. It keeps rows in a single table, and
       each operation has a comment naming the database call that replaces
       it.
    2. Point `assets/test_store_contract.py` at a fresh, disposable database.
    3. Run the contract, or `scripts/check_store.py`. Fix the first broken
       promise and rerun until every promise holds.
    4. Register the store with `runtime.register(ProvenanceStore, store)` and
       run one real call.

Before finishing, the agent checks that:

- the adapter returns results and raises exceptions unchanged;
- each top-level call records exactly one run;
- every contract test passes against the real database.

## What's inside

```text
agxai-extend/
├── SKILL.md                          # both workflows, checklist, gotchas
├── references/
│   ├── instrumentor.md               # boundaries, callbacks, streaming, threads
│   └── store.md                      # the six methods, table layout, query types
├── scripts/
│   └── check_store.py                # runs the store contract without pytest
├── assets/
│   ├── instrumentor_template.py      # a FrameworkInstrumentor to copy
│   ├── test_instrumentor.py          # the tests it must pass
│   ├── store_template.py             # a ProvenanceStore shaped like one table
│   └── test_store_contract.py        # the ProvenanceStoreContract subclass
└── evals/                            # test prompts, assertions, trigger queries
```

The templates run as they are: their tests pass against agxai alone, so the
agent starts from working code and changes one piece at a time.

## The store contract check

`scripts/check_store.py` loads a store factory, for example a class, and runs
every test in `ProvenanceStoreContract` against it, without pytest:

```bash
python scripts/check_store.py my_project.storage:make_store
```

```text
PASS  test_concurrent_writes_are_all_kept
PASS  test_delete_run_removes_only_that_run_and_is_idempotent
PASS  test_equal_ids_in_other_tenants_or_runs_never_replace_each_other
PASS  test_get_is_scoped_to_one_run_of_one_tenant
PASS  test_lineage_returns_every_upstream_link_nearest_first
PASS  test_parents_and_children_are_scoped_to_one_run
PASS  test_query_filters_by_run_and_record_type_including_subclasses
PASS  test_query_is_scoped_to_one_application_and_tenant
PASS  test_query_orders_by_timestamp_sequence_and_id_and_paginates
PASS  test_returned_records_are_independent_copies
PASS  test_write_is_an_idempotent_latest_wins_upsert
All 11 promises hold.
```

| Option | Effect |
| --- | --- |
| `--path DIR` | Import the factory's module from this directory instead of the current one |
| `--json` | Print one JSON object for the agent to parse |

It exits with `0` when every promise holds, `1` when one is broken, and `2`
when the factory can't be loaded.

## Learn more

- [Custom frameworks](../integrations/custom-frameworks.md): the
  `FrameworkInstrumentor` API.
- [Storage](../architecture/storage.md): the `ProvenanceStore` model and its
  guarantees.
- [PostgreSQL store](../examples/postgres-store.md): a complete production
  store.
