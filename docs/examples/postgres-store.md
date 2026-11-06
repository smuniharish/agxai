# PostgreSQL store

`agxai` keeps records in memory by default. To keep them in a database,
subclass the `ProvenanceStore` base class. This example is a complete, tested
store for PostgreSQL that you can copy into your application: one JSONB table,
keyed and indexed for tenant and run isolation, written with idempotent upserts. Source:
[`examples/postgres_store.py`](https://github.com/smuniharish/agxai/blob/master/examples/postgres_store.py).

```bash
export XAI_POSTGRES_DSN=postgresql://user:password@localhost:5432/xai
uv run --group examples python examples/postgres_store.py
```

The example needs `psycopg[binary,pool]`, which the `examples` dependency group
installs. In your own project, add it to your dependencies.

## Subclassing `ProvenanceStore`

A store implements six methods and inherits the rest:

```python
class PostgresProvenanceStore(ProvenanceStore):
    async def write(self, item): ...  # insert or replace one record
    async def get(self, entity_id, *, context): ...  # one record by ID, in one run
    async def query(self, query): ...  # records of one application and tenant
    async def parents(self, entity_id, *, context): ...  # links into an entity, in one run
    async def children(self, entity_id, *, context): ...  # links out of an entity, in one run
    async def delete_run(self, context): ...  # erase one run, return the row count

    async def close(self): ...  # optional: the inherited close does nothing
```

`lineage` is inherited. It walks `parents` breadth-first, nearest first, and
visits each entity once, so every store gets the same lineage semantics. A
store can override it with a faster native query, such as a recursive SQL
query.

Writes are upserts on the record's application, tenant, run, type, and ID, so a
record in one tenant or run can never replace another's, even if their IDs are
equal:

```python
async def write(self, item: StoredItem) -> None:
    context = item.context
    async with self._pool.connection() as connection:
        await connection.execute(
            """
            INSERT INTO agxai_records
                (application_id, tenant_id, run_id, record_type, record_id,
                 timestamp, payload)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (application_id, tenant_id, run_id, record_type, record_id)
            DO UPDATE SET timestamp = EXCLUDED.timestamp, payload = EXCLUDED.payload
            """,
            (
                context.application_id,
                context.tenant_id,
                context.run_id,
                type(item).__name__,
                _record_id(item),
                item.timestamp,
                item.model_dump_json(),
            ),
        )
```

## Using it

```python
store = PostgresProvenanceStore(os.environ["XAI_POSTGRES_DSN"])
await store.open()  # opens the pool, creates the table and indexes if needed

runtime = XAIRuntime(application_id="payments", tenant_id="acme-bank", graph_id="fraud-review")
runtime.register(ProvenanceStore, store)
graph = runtime.instrument(builder.compile())
try:
    await graph.ainvoke({"transaction_id": "txn-8841"})
finally:
    await runtime.close()  # flushes providers and closes the store's pool
```

To share a connection pool with the rest of your application, pass it in with
`PostgresProvenanceStore(dsn, pool=pool)`. A pool you pass in stays yours, and
`close()` does not close it.

!!! warning "Use asynchronous graph calls"
    The store uses psycopg's asynchronous pool, which belongs to the event loop
    that opened it. Record through `ainvoke`, `astream`, or `abatch`.
    Synchronous calls (`invoke`, `stream`, `batch`) record from a separate
    event loop, where the pool cannot be used.

!!! note "Windows"
    psycopg's asynchronous mode needs a selector event loop on Windows:
    `asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)`.

## Output

Real output against PostgreSQL 16. The demo runs a one-node graph that records
evidence and a provenance link, then reads the run back from the database:

```text
Stored 6 records for run a0cc4663-17db-4959-a214-3e521e89ba86:
  Execution: 1
  ExecutionCompletedEvent: 1
  ExecutionStartedEvent: 1
  NodeExecutionEvent: 1
  ProvenanceLink: 1
  StateTransitionEvent: 1
Lineage of the fraud score: ['18fc9ad5-a5fb-4ec4-b9ea-cd8596feae35 DERIVED_FROM transactions://txn-8841']
```

Six records were stored: the `Execution`, its four events, and the provenance
link. Evidence is not among them, because evidence is delivered to
[plugins](../architecture/plugins.md), not to the store.

## Schema

`PostgresProvenanceStore.SCHEMA` is the DDL that `open()` runs:

```sql
CREATE TABLE IF NOT EXISTS agxai_records (
    application_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    run_id UUID NOT NULL,
    record_type TEXT NOT NULL,          -- Execution, ProvenanceLink, NodeExecutionEvent, ...
    record_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    PRIMARY KEY (application_id, tenant_id, run_id, record_type, record_id)
);
CREATE INDEX IF NOT EXISTS agxai_tenant_time_idx
    ON agxai_records (application_id, tenant_id, timestamp);
```

Every query filters on the application and tenant. `get`, provenance queries,
and `delete_run` also filter on the run and use the primary key's leading
columns; tenant-wide queries use `agxai_tenant_time_idx`.

## Operating it

- **Credentials.** The DSN is used to connect and is never written into
  records. Load it from your secret store.
- **Least privilege.** Creating the schema needs the `CREATE` privilege, even
  when the table already exists. Apply `PostgresProvenanceStore.SCHEMA` once
  with a privileged role, for example in a migration. Then run the application
  with a role limited to `SELECT`, `INSERT`, `UPDATE`, and `DELETE` (used only
  by `delete_run`) on `agxai_records`, and open the store with
  `await store.open(create_schema=False)`.
- **Erasure and retention.** Records are kept until you delete them. To erase
  one run, call `await store.delete_run(context)` with the run's
  `ExecutionContext`; it returns the number of rows deleted. To apply a
  retention period across runs, use SQL, for example
  `DELETE FROM agxai_records WHERE timestamp < now() - interval '400 days'`.

## Tests

The store's unit tests run against a fake connection pool. The live tests run
the [store conformance kit](../architecture/storage.md#testing-a-store) against
a real server, persist an instrumented graph run end to end, and run this
demo. Set
`XAI_TEST_POSTGRES_DSN` to a disposable database to run them; see
[Testing](../development/testing.md).
