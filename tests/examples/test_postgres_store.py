import json
from contextlib import asynccontextmanager

import pytest

from agxai import Execution, ProvenanceLink, ProvenanceStore
from agxai.core import ExecutionStartedEvent, XAIEvent
from agxai.storage import StoreFilter
from examples import postgres_store as postgres_module
from examples.postgres_store import PostgresProvenanceStore
from tests.helpers import context, execution


class FakeCursor:
    def __init__(self, rows: list[tuple]) -> None:
        self.rows = rows
        self.rowcount = len(rows)

    async def fetchall(self) -> list[tuple]:
        return self.rows

    async def fetchone(self) -> tuple | None:
        return self.rows[0] if self.rows else None


class FakePool:
    """Records every statement and answers SELECTs from rows or a responder function."""

    def __init__(self, rows: list[tuple] | None = None, responder=None) -> None:
        self.rows = rows or []
        self.responder = responder
        self.statements: list[tuple[str, tuple | None]] = []
        self.opened = 0
        self.closed = 0

    async def open(self) -> None:
        self.opened += 1

    async def close(self) -> None:
        self.closed += 1

    @asynccontextmanager
    async def connection(self):
        yield self

    async def execute(self, sql: str, params: tuple | None = None) -> FakeCursor:
        self.statements.append((" ".join(sql.split()), params))
        return FakeCursor(self.responder(params) if self.responder else self.rows)


def row(item) -> tuple[str, object]:
    return (type(item).__name__, item.model_dump(mode="json"))


async def test_open_creates_schema_and_indexes() -> None:
    pool = FakePool()
    store = PostgresProvenanceStore("unused", pool=pool)

    await store.open()

    ((sql, params),) = pool.statements
    assert pool.opened == 1
    assert params is None
    assert "CREATE TABLE IF NOT EXISTS agxai_records" in sql
    assert "PRIMARY KEY (application_id, tenant_id, run_id, record_type, record_id)" in sql
    assert sql == " ".join(PostgresProvenanceStore.SCHEMA.split())


async def test_open_can_skip_schema_creation_for_restricted_roles() -> None:
    pool = FakePool()

    await PostgresProvenanceStore("unused", pool=pool).open(create_schema=False)

    assert pool.opened == 1
    assert pool.statements == []


class UnreachablePool(FakePool):
    @asynccontextmanager
    async def connection(self):
        raise ConnectionError("database unreachable")
        yield self


async def test_failed_open_closes_only_an_owned_pool() -> None:
    injected = UnreachablePool()
    with pytest.raises(ConnectionError):
        await PostgresProvenanceStore("unused", pool=injected).open()
    assert injected.closed == 0

    owned = PostgresProvenanceStore("unused", pool=UnreachablePool())
    owned._owns_pool = True
    with pytest.raises(ConnectionError):
        await owned.open()
    assert owned._pool.closed == 1


async def test_write_upserts_with_isolation_columns_and_event_ids() -> None:
    pool = FakePool()
    store = PostgresProvenanceStore("unused", pool=pool)
    event = ExecutionStartedEvent(context=context(), sequence=0)

    await store.write(event)

    sql, params = pool.statements[0]
    assert (
        "ON CONFLICT (application_id, tenant_id, run_id, record_type, record_id) DO UPDATE" in sql
    )
    assert params is not None
    assert params[:5] == (
        "app",
        "tenant",
        event.context.run_id,
        "ExecutionStartedEvent",
        str(event.id),
    )
    assert json.loads(params[6])["id"] == str(event.id)


async def test_get_is_scoped_decodes_by_record_type_and_detects_ambiguity() -> None:
    record = execution()
    scope = record.context
    pool = FakePool([row(record)])
    store = PostgresProvenanceStore("unused", pool=pool)
    assert await store.get(str(record.id), context=scope) == record
    sql, params = pool.statements[0]
    assert "WHERE application_id = %s AND tenant_id = %s AND run_id = %s" in sql
    assert params == ("app", "tenant", scope.run_id, str(record.id))

    text_payload = PostgresProvenanceStore(
        "unused", pool=FakePool([("Execution", json.dumps(record.model_dump(mode="json")))])
    )
    assert await text_payload.get(str(record.id), context=scope) == record

    empty = PostgresProvenanceStore("unused", pool=FakePool())
    assert await empty.get("missing", context=scope) is None
    with pytest.raises(LookupError, match="ambiguous"):
        await PostgresProvenanceStore("unused", pool=FakePool([row(record)] * 2)).get(
            "x", context=scope
        )
    with pytest.raises(ValueError, match="unsupported record type"):
        await PostgresProvenanceStore("unused", pool=FakePool([("Unknown", {})])).get(
            "x", context=scope
        )


async def test_delete_run_deletes_one_scoped_run_and_reports_the_row_count() -> None:
    scope = context()
    pool = FakePool([("row",)] * 3)
    store = PostgresProvenanceStore("unused", pool=pool)

    assert await store.delete_run(scope) == 3

    ((sql, params),) = pool.statements
    assert sql.startswith("DELETE FROM agxai_records WHERE application_id = %s")
    assert params == ("app", "tenant", scope.run_id)


async def test_query_passes_filters_and_orders_like_the_memory_store() -> None:
    first = ExecutionStartedEvent(context=context(), sequence=0)
    pool = FakePool([row(first)])
    store = PostgresProvenanceStore("unused", pool=pool)
    query = StoreFilter(
        application_id="app",
        tenant_id="tenant",
        run_id=first.context.run_id,
        item_type=ExecutionStartedEvent,
        limit=5,
        offset=2,
    )

    items = [item async for item in store.query(query)]

    sql, params = pool.statements[0]
    assert items == [first]
    assert "ORDER BY timestamp, COALESCE((payload->>'sequence')::int, -1), payload->>'id'" in sql
    assert params == (
        "app",
        "tenant",
        str(first.context.run_id),
        str(first.context.run_id),
        ["ExecutionStartedEvent"],
        ["ExecutionStartedEvent"],
        5,
        2,
    )
    with pytest.raises(TypeError, match="StoreFilter"):
        [item async for item in store.query(object())]  # pyrefly: ignore[bad-argument-type]


async def test_link_queries_and_lineage() -> None:
    ctx = context()
    upstream = ProvenanceLink(source_id="a", target_id="b", relation="r", context=ctx)
    pool = FakePool([(upstream.model_dump(mode="json"),)])
    store = PostgresProvenanceStore("unused", pool=pool)

    assert await store.parents("b", context=ctx) == (upstream,)
    assert await store.children("a", context=ctx) == (upstream,)

    payload = json.dumps(upstream.model_dump(mode="json"))
    pool.responder = lambda params: [(payload,)] if params[4] == "b" else []
    assert await store.lineage("b", context=ctx, max_depth=3) == (upstream,)
    assert [(params or ())[3:] for _, params in pool.statements] == [
        ("target_id", "b"),
        ("source_id", "a"),
        ("target_id", "b"),
        ("target_id", "a"),
    ]
    with pytest.raises(ValueError, match="max_depth"):
        await store.lineage("b", context=ctx, max_depth=0)


async def test_only_owned_pools_are_closed() -> None:
    injected = FakePool()
    await PostgresProvenanceStore("unused", pool=injected).close()
    assert injected.closed == 0

    owned = PostgresProvenanceStore("postgresql://localhost/unused")
    await owned.close()
    assert owned._owns_pool


def test_missing_driver_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(name: str) -> object:
        raise ImportError(name)

    monkeypatch.setattr(postgres_module, "import_module", missing)

    with pytest.raises(ImportError, match=r"psycopg\[binary,pool\]"):
        PostgresProvenanceStore("postgresql://localhost/unused")


def test_item_type_filters_match_stored_subclasses() -> None:
    assert postgres_module._record_types(None) is None
    assert postgres_module._record_types(Execution) == ["Execution"]
    event_types = postgres_module._record_types(XAIEvent)
    assert event_types is not None
    assert {"ExecutionStartedEvent", "InterruptEvent"} <= set(event_types)
    assert "Execution" not in event_types


def test_every_stored_record_type_can_be_decoded() -> None:
    assert {"Execution", "ProvenanceLink", "ExecutionStartedEvent", "InterruptEvent"} <= set(
        postgres_module._MODELS
    )
    assert Execution.__name__ in postgres_module._MODELS


def test_the_store_is_a_provenance_store_that_inherits_lineage() -> None:
    assert issubclass(PostgresProvenanceStore, ProvenanceStore)
    assert PostgresProvenanceStore.lineage is ProvenanceStore.lineage
