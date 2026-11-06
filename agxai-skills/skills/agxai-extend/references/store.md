# Writing a ProvenanceStore

Read this file when a store's design is unclear, or when a contract test fails
and its message alone does not explain why.

## What the store holds

The runtime writes three kinds of record to the store: the `Execution` of each
run, its canonical events (subclasses of `XAIEvent`), and `ProvenanceLink`
records. Evidence, decisions, and memory references are not written to the
store; they reach `XAIPlugin` instances. Persist those with a plugin, not by
widening the store.

## The six methods

| Method | Promise |
| --- | --- |
| `write(item)` | Idempotent upsert keyed by `(application_id, tenant_id, run_id, type(item).__name__, str(item.id))`; the latest write wins. |
| `get(entity_id, *, context)` | The record with that ID in the context's run, or `None`. Raise `LookupError` if records of two types in the run share the ID. |
| `query(query)` | Records of one application and tenant, optionally one run and one `item_type` including subclasses, ordered by `(timestamp, sequence, id)`, paginated by `limit` and `offset`. |
| `parents(entity_id, *, context)` | Links whose `target_id` is the entity, in one run, in the same order. |
| `children(entity_id, *, context)` | Links whose `source_id` is the entity, in one run, in the same order. |
| `delete_run(context)` | Delete the run's records in its application and tenant only; return how many; `0` when none. |

`lineage` is inherited: it walks `parents` breadth-first. Override it only for
a faster native query, such as a recursive CTE, and keep the contract green.
`close` is inherited as a no-op; override it to release connections the store
owns, and leave a pool passed in by the caller open.

## A layout that satisfies the contract

One table, or one collection, is enough:

```sql
CREATE TABLE agxai_records (
    application_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    run_id UUID NOT NULL,
    record_type TEXT NOT NULL,
    record_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    PRIMARY KEY (application_id, tenant_id, run_id, record_type, record_id)
);
CREATE INDEX ON agxai_records (application_id, tenant_id, timestamp);
```

- Serialize with `item.model_dump_json()` and rebuild with
  `Model.model_validate_json(payload)`, choosing `Model` by `record_type`.
  Build that map from `Execution`, `ProvenanceLink`, and
  `XAIEvent.__subclasses__()`, as `assets/store_template.py` does.
- Order with
  `ORDER BY timestamp, COALESCE((payload->>'sequence')::int, -1), payload->>'id'`.
  Records without a `sequence` sort as `-1`.
- Index the link endpoints (`source_id`, `target_id`, or JSON expressions on
  them) when lineage queries are frequent.

## Query types

`query` receives a `StoreQuery`. The runtime and the contract use
`StoreFilter`; reject anything else with `TypeError`. A store with extra query
features may define its own `StoreQuery` subclass and override
`ProvenanceStoreContract.make_query` in its tests.

## Verifying

- In the project's tests, subclass `agxai.testing.ProvenanceStoreContract`
  and implement `async make_store()` returning a new, empty store. Start from
  `assets/test_store_contract.py`.
- Without pytest, run `python scripts/check_store.py module:factory`, adding
  `--json` for machine-readable output.
- For a database, truncate in `make_store` and point the tests at a disposable
  database. Override `run_scenario` if the driver needs a specific event loop.
- Then register the store, `runtime.register(ProvenanceStore, store)`, and
  run one real call.

## Complete example

`examples/postgres_store.py` is a tested PostgreSQL store with a psycopg async
pool, JSONB, upserts, and an explicit `open()` that can skip DDL for
least-privilege roles:
<https://github.com/smuniharish/agxai/blob/master/examples/postgres_store.py>.
