"""Live tests for the example PostgreSQL store against a real PostgreSQL server.

Set ``XAI_TEST_POSTGRES_DSN`` to a disposable database, for example::

    podman run -d --name xai-postgres -e POSTGRES_PASSWORD=xai -e POSTGRES_DB=xai \\
        -p 55432:5432 postgres:18-alpine
    export XAI_TEST_POSTGRES_DSN="postgresql://postgres:xai@localhost:55432/xai"

psycopg's async pool needs a selector event loop on Windows, so each test runs
its coroutine on an explicitly chosen loop instead of changing the global policy.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import TYPE_CHECKING

import pytest

from agxai import Execution, ExecutionStatus, ProvenanceLink, ProvenanceStore, XAIRuntime
from agxai.core import ExecutionStartedEvent, NodeExecutionEvent, StateTransitionEvent
from agxai.storage import StoreFilter
from agxai.testing import ProvenanceStoreContract
from examples import postgres_store
from examples.postgres_store import PostgresProvenanceStore
from tests.helpers import context, execution, linear_graph

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Sequence
    from typing import Any

pytestmark = pytest.mark.postgres
DSN = os.getenv("XAI_TEST_POSTGRES_DSN")
requires_postgres = pytest.mark.skipif(not DSN, reason="XAI_TEST_POSTGRES_DSN is not configured")


def run(test: Callable[[str], Coroutine[Any, Any, None]]) -> None:
    pytest.importorskip("psycopg_pool")
    assert DSN is not None
    factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(test(DSN), loop_factory=factory)


async def fresh_store(dsn: str) -> PostgresProvenanceStore:
    store = PostgresProvenanceStore(dsn)
    await store.open()
    async with store._pool.connection() as connection:
        await connection.execute("TRUNCATE TABLE agxai_records")
    return store


@requires_postgres
class TestPostgresStoreContract(ProvenanceStoreContract):
    """Runs the full store conformance kit against a real PostgreSQL server."""

    async def make_store(self) -> PostgresProvenanceStore:
        assert DSN is not None
        return await fresh_store(DSN)

    def run_scenario(self, scenario: Coroutine[Any, Any, None]) -> None:
        pytest.importorskip("psycopg_pool")
        factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
        asyncio.run(scenario, loop_factory=factory)


@requires_postgres
def test_instrumented_graph_runs_are_persisted_end_to_end() -> None:
    async def scenario(dsn: str) -> None:
        store = await fresh_store(dsn)
        runtime = XAIRuntime(application_id="app", tenant_id="tenant", graph_id="live")
        runtime.register(ProvenanceStore, store)
        graph = runtime.instrument(
            linear_graph(
                ("score", lambda state: {"count": 1}), ("answer", lambda state: {"answer": "ok"})
            )
        )
        try:
            with runtime.collect_runs() as runs:
                await graph.ainvoke({"question": "q"})
            (run_,) = runs
            records = [
                item
                async for item in store.query(
                    StoreFilter(
                        application_id="app", tenant_id="tenant", run_id=run_.run_id, limit=50
                    )
                )
            ]
            executions = [item for item in records if isinstance(item, Execution)]
            assert [item.status for item in executions] == [ExecutionStatus.COMPLETED]
            assert len(executions[0].nodes) == 2
            assert sum(isinstance(item, NodeExecutionEvent) for item in records) == 2
            assert sum(isinstance(item, StateTransitionEvent) for item in records) == 2
            sequences = [item.sequence for item in records if hasattr(item, "sequence")]
            assert sequences == sorted(sequences)
            assert runtime.errors == ()
        finally:
            await runtime.close()

    run(scenario)


@requires_postgres
def test_the_example_demo_persists_a_run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert DSN is not None
    monkeypatch.setenv("XAI_POSTGRES_DSN", DSN)

    run(lambda dsn: postgres_store.main())

    output = capsys.readouterr().out
    assert "Stored 6 records for run" in output
    assert "ProvenanceLink: 1" in output
    assert "DERIVED_FROM transactions://txn-8841" in output


LEGACY_SCHEMA = """
CREATE TABLE langgraph_xai_records (
    record_key TEXT PRIMARY KEY,
    record_type TEXT NOT NULL,
    application_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    run_id UUID NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL
);
CREATE INDEX langgraph_xai_scope_idx
    ON langgraph_xai_records (application_id, tenant_id, run_id, timestamp);
CREATE INDEX langgraph_xai_entity_idx
    ON langgraph_xai_records ((split_part(record_key, ':', 2)));
"""


async def legacy_store(
    dsn: str, *items: Any, payloads: Sequence[str] = ()
) -> PostgresProvenanceStore:
    """Return an empty store next to a `langgraph-xai` table holding ``items``."""
    store = await fresh_store(dsn)
    async with store._pool.connection() as connection:
        await connection.execute("DROP TABLE IF EXISTS langgraph_xai_records")
        await connection.execute(LEGACY_SCHEMA)
        for item, payload in zip(items, [*payloads, *[None] * len(items)], strict=False):
            scope = item.context
            await connection.execute(
                "INSERT INTO langgraph_xai_records VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)",
                (
                    f"{type(item).__name__}:{item.id}",
                    type(item).__name__,
                    scope.application_id,
                    scope.tenant_id,
                    scope.run_id,
                    item.timestamp,
                    payload or item.model_dump_json(),
                ),
            )
    return store


async def legacy_table_exists(store: PostgresProvenanceStore) -> bool:
    async with store._pool.connection() as connection:
        found = await (
            await connection.execute("SELECT to_regclass('langgraph_xai_records') IS NOT NULL")
        ).fetchone()
    assert found is not None
    return found[0]


@requires_postgres
def test_migration_moves_every_legacy_row_and_drops_the_legacy_table() -> None:
    async def scenario(dsn: str) -> None:
        first, second = context("tenant-a"), context("tenant-b")
        records = [
            execution(first),
            ExecutionStartedEvent(context=first, sequence=0),
            ProvenanceLink(context=first, source_id="input", target_id="score", relation="r"),
            execution(second),
        ]
        store = await legacy_store(dsn, *records)
        try:
            assert await store.migrate_legacy_table() == 4
            assert not await legacy_table_exists(store)
            for ctx in (first, second):
                for record in records:
                    if record.context == ctx:
                        assert await store.get(str(record.id), context=ctx) == record
            lineage = await store.lineage("score", context=first)
            assert [link.source_id for link in lineage] == ["input"]
            assert await store.migrate_legacy_table() == 0
        finally:
            await store.close()

    run(scenario)


@requires_postgres
def test_a_failed_migration_leaves_both_tables_unchanged() -> None:
    async def scenario(dsn: str) -> None:
        good, bad = execution(context()), execution(context())
        store = await legacy_store(dsn, good, bad, payloads=["", '{"no": "id"}'])
        try:
            with pytest.raises(Exception, match="record_id"):
                await store.migrate_legacy_table()
            assert await legacy_table_exists(store)
            assert await store.get(str(good.id), context=good.context) is None
        finally:
            async with store._pool.connection() as connection:
                await connection.execute("DROP TABLE IF EXISTS langgraph_xai_records")
            await store.close()

    run(scenario)
