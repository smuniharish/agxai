# Storage

A provenance store keeps the records that describe what happened: executions,
events, and provenance links. `agxai` ships one store,
`InMemoryProvenanceStore`, which every runtime uses by default. Any other
backend is a subclass of the `ProvenanceStore` abstract base class.

```python
from agxai import ProvenanceStore
```

## The base class

`ProvenanceStore` declares six abstract methods and implements two:

| Method | Kind | Behavior |
| --- | --- | --- |
| `write(item)` | abstract | Insert or replace an `Execution`, `ProvenanceLink`, or event. The latest write wins. |
| `get(entity_id, context=...)` | abstract | One record by its `id` within one run, or `None`. Raises `LookupError` when records of different types share the ID in that run. |
| `query(query)` | abstract | Records matching a `StoreFilter`, or your own `StoreQuery` subclass, in a stable order |
| `parents(entity_id, context=...)` | abstract | Links whose target is the entity, within one run |
| `children(entity_id, context=...)` | abstract | Links whose source is the entity, within one run |
| `delete_run(context)` | abstract | Delete every record of one run and return how many were deleted; `0` when nothing matches |
| `lineage(entity_id, context=..., max_depth=100)` | inherited | Every upstream link, breadth-first and nearest first, visiting each entity once. Override it only for a faster native query. |
| `close()` | inherited | Does nothing. Override it to release connections. |

Every store must keep three promises:

- **Idempotent writes.** An `Execution` is written when its run starts, when it
  finishes, and again when a record is added after it finished. The store must
  upsert by application, tenant, run, record type, and ID, so the same ID in
  another tenant or run is a different record and never replaces this one.
- **Isolation.** `query` returns records of one application and tenant only,
  and `get`, `parents`, `children`, and `delete_run` act on one run only.
- **Stable order.** Results come back in the same order every time, by
  timestamp, then event sequence, then ID.

`delete_run` is how a deployment honors erasure requests and retention
windows: call it with the context of a finished run, for example the
`context` of an `Execution` returned by `query`. Deleting is idempotent, so a
retention job can safely retry.

Because the lineage walk lives in the base class, every store returns lineage
with the same semantics.

## The default in-memory store

`InMemoryProvenanceStore` needs no setup. It is built for correctness under
concurrency, not just for demos:

- **Thread-safe.** One lock guards all indexes, so synchronous and
  asynchronous calls can share it.
- **Indexed.** Records are indexed by ID, by application and tenant, by run,
  and provenance links by source and target, so `get`, scoped queries,
  `delete_run`, and lineage walks never scan every record.
- **Copy-safe.** Records are stored as their JSON data and validated again on
  read. Mutating a returned record never changes the stored one.
- **Deterministic.** Query results are sorted by timestamp, event sequence,
  and ID.

It keeps records until `delete_run` removes them or the process exits, which
suits development, tests, and explaining runs within the same process.

## Using a database

Subclass `ProvenanceStore`, implement the six abstract methods, and register
an instance:

```python
runtime.register(ProvenanceStore, MyDatabaseStore(...))
```

The [PostgreSQL store example](../examples/postgres-store.md) is a complete,
tested implementation to start from. It uses one JSONB table with indexes for
tenant and run isolation and idempotent upserts, and inherits `lineage`.
Records other than executions, events, and provenance links, such as evidence
and decisions, are delivered to [plugins](plugins.md), so a database-backed
deployment usually adds a plugin that writes them to the same database.

## Testing a store

`agxai.testing.ProvenanceStoreContract` checks any store against the promises
above: latest-wins upserts, IDs that repeat across tenants and runs, scoped
`get`, copy safety, tenant and run isolation, type filters that include
subclasses, ordering and pagination, lineage through cycles, `delete_run`
isolation and idempotency, and concurrent writes. Subclass it in a test module
and return a fresh, empty store from `make_store`:

```python
from agxai.testing import ProvenanceStoreContract


class TestMyDatabaseStore(ProvenanceStoreContract):
    async def make_store(self):
        return await MyDatabaseStore.open(TEST_DSN)
```

pytest collects the inherited `test_*` methods directly; for `unittest`, also
inherit `unittest.TestCase`. The kit needs neither pytest nor an async plugin.
Each check runs its scenario with `asyncio.run`; override
`run_scenario` when your driver needs a particular event loop, and
`make_query` when your store expects its own `StoreQuery` subclass.
