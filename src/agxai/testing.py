"""Conformance tests for `ProvenanceStore` implementations.

Subclass `ProvenanceStoreContract` in a test module, implement `make_store`,
and your test runner collects one test per promise in the store contract:

```python
from agxai.testing import ProvenanceStoreContract


class TestMyStore(ProvenanceStoreContract):
    async def make_store(self):
        store = MyStore(dsn)
        await store.open()
        await store.truncate()  # every test starts from an empty store
        return store
```

The tests are plain synchronous methods that raise `AssertionError` with a
descriptive message, so they run under pytest, or under unittest when the
subclass also inherits ``unittest.TestCase``. Neither pytest nor an async
plugin is required.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from .core.models import (
    Execution,
    ExecutionCompletedEvent,
    ExecutionContext,
    ExecutionStartedEvent,
    ExecutionStatus,
    ProvenanceLink,
    XAIEvent,
)
from .storage.memory import StoreFilter

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Coroutine

    from .core.contracts import ProvenanceStore, StoreQuery
    from .core.models import CanonicalEvent

    type StoredItem = Execution | ProvenanceLink | CanonicalEvent

__all__ = ["ProvenanceStoreContract"]

_APPLICATION = "contract-app"
_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


def _context(tenant: str = "tenant-a", run_id: UUID | None = None) -> ExecutionContext:
    return ExecutionContext(
        application_id=_APPLICATION,
        tenant_id=tenant,
        graph_id="contract-graph",
        run_id=run_id or uuid4(),
    )


def _link(source: str, target: str, context: ExecutionContext, **fields: Any) -> ProvenanceLink:
    return ProvenanceLink(
        source_id=source, target_id=target, relation="DERIVED_FROM", context=context, **fields
    )


def _execution(context: ExecutionContext, status: ExecutionStatus) -> Execution:
    return Execution(context=context, status=status, started_at=_EPOCH)


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class ProvenanceStoreContract(ABC):
    """Tests every promise a `ProvenanceStore` makes to the runtime.

    Each test calls `make_store` for a new, empty store, runs one scenario on
    it, and closes it. Override `run_scenario` to run scenarios on a specific
    event loop, and `make_query` if the store needs its own `StoreQuery` type
    instead of `StoreFilter`.
    """

    @abstractmethod
    async def make_store(self) -> ProvenanceStore:
        """Return a new, empty, ready-to-use store."""

    def run_scenario(self, scenario: Coroutine[Any, Any, None]) -> None:
        """Run one scenario to completion; the default is ``asyncio.run``."""
        asyncio.run(scenario)

    def make_query(
        self,
        application_id: str,
        tenant_id: str,
        *,
        run_id: UUID | None = None,
        item_type: type[StoredItem] | type[XAIEvent] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> StoreQuery:
        """Return the store's query for one application and tenant."""
        return StoreFilter(
            application_id=application_id,
            tenant_id=tenant_id,
            run_id=run_id,
            item_type=item_type,
            limit=limit,
            offset=offset,
        )

    def test_write_is_an_idempotent_latest_wins_upsert(self) -> None:
        """Rewriting a record replaces it, and only the latest version is kept."""

        async def scenario(store: ProvenanceStore) -> None:
            context = _context()
            running = _execution(context, ExecutionStatus.RUNNING)
            await store.write(running)
            await store.write(running)
            completed = running.model_copy(update={"status": ExecutionStatus.COMPLETED})
            await store.write(completed)

            stored = await self._all(store, context.tenant_id, run_id=context.run_id)
            _check(stored == [completed], f"expected only the latest write, got {stored!r}")
            fetched = await store.get(str(running.id), context=context)
            _check(fetched == completed, f"get returned {fetched!r} after a rewrite")

        self._run(scenario)

    def test_equal_ids_in_other_tenants_or_runs_never_replace_each_other(self) -> None:
        """The same record ID in another tenant or run is a separate record."""

        async def scenario(store: ProvenanceStore) -> None:
            first = _context("tenant-a")
            shared = uuid4()
            originals = [
                _link("source", "target", first, id=shared, metadata={"owner": "a-1"}),
                _link(
                    "source", "target", _context("tenant-a"), id=shared, metadata={"owner": "a-2"}
                ),
                _link(
                    "source",
                    "target",
                    _context("tenant-b", first.run_id),
                    id=shared,
                    metadata={"owner": "b-1"},
                ),
            ]
            for item in originals:
                await store.write(item)

            for item in originals:
                fetched = await store.get(str(shared), context=item.context)
                _check(fetched == item, f"a record with a shared ID was replaced: {fetched!r}")

        self._run(scenario)

    def test_get_is_scoped_to_one_run_of_one_tenant(self) -> None:
        """`get` finds a record only within its own run, application, and tenant."""

        async def scenario(store: ProvenanceStore) -> None:
            context = _context()
            event = ExecutionStartedEvent(context=context, sequence=0)
            await store.write(event)
            entity_id = str(event.id)

            _check(await store.get(entity_id, context=context) == event, "get missed the record")
            elsewhere = (
                _context("tenant-b", context.run_id),
                _context("tenant-a"),
                context.model_copy(update={"application_id": "other-app"}),
            )
            for other in elsewhere:
                leaked = await store.get(entity_id, context=other)
                _check(leaked is None, f"get leaked a record across scopes: {other!r}")
            _check(await store.get(str(uuid4()), context=context) is None, "unknown ID found")

        self._run(scenario)

    def test_returned_records_are_independent_copies(self) -> None:
        """Mutating a returned record never changes the stored one."""

        async def scenario(store: ProvenanceStore) -> None:
            context = _context()
            record = _execution(context, ExecutionStatus.COMPLETED)
            await store.write(record)

            fetched = await store.get(str(record.id), context=context)
            _check(isinstance(fetched, Execution), f"expected an Execution, got {fetched!r}")
            fetched.metadata["mutated"] = True  # pyrefly: ignore[missing-attribute]
            again = await store.get(str(record.id), context=context)
            _check(again == record, "mutating a returned record changed the stored record")

        self._run(scenario)

    def test_query_is_scoped_to_one_application_and_tenant(self) -> None:
        """`query` never returns another application's or tenant's records."""

        async def scenario(store: ProvenanceStore) -> None:
            mine = _link("a", "b", _context("tenant-a"))
            await store.write(mine)
            await store.write(_link("a", "b", _context("tenant-b")))
            await store.write(
                _link("a", "b", _context("tenant-a").model_copy(update={"application_id": "x"}))
            )

            found = await self._all(store, "tenant-a")
            _check(found == [mine], f"query crossed an application or tenant: {found!r}")
            _check(await self._all(store, "nobody") == [], "query found records of no tenant")

        self._run(scenario)

    def test_query_filters_by_run_and_record_type_including_subclasses(self) -> None:
        """`query` filters by run, and by record type including its subclasses."""

        async def scenario(store: ProvenanceStore) -> None:
            context, other = _context(), _context()
            started = ExecutionStartedEvent(context=context, sequence=0, timestamp=_EPOCH)
            completed = ExecutionCompletedEvent(
                context=context, sequence=1, timestamp=_EPOCH + timedelta(seconds=1)
            )
            execution = _execution(context, ExecutionStatus.COMPLETED)
            for item in (completed, execution, started, _link("a", "b", other)):
                await store.write(item)

            in_run = await self._all(store, context.tenant_id, run_id=context.run_id)
            _check(len(in_run) == 3, f"run filter returned {in_run!r}")
            events = await self._all(
                store, context.tenant_id, run_id=context.run_id, item_type=XAIEvent
            )
            _check(events == [started, completed], f"base-type filter returned {events!r}")
            executions = await self._all(store, context.tenant_id, item_type=Execution)
            _check(executions == [execution], f"type filter returned {executions!r}")

        self._run(scenario)

    def test_query_orders_by_timestamp_sequence_and_id_and_paginates(self) -> None:
        """`query` orders by timestamp, sequence, then ID, and paginates without gaps."""

        async def scenario(store: ProvenanceStore) -> None:
            context = _context()
            late = ExecutionCompletedEvent(
                context=context, sequence=0, timestamp=_EPOCH + timedelta(seconds=5)
            )
            same_time = [
                ExecutionStartedEvent(context=context, sequence=index, timestamp=_EPOCH)
                for index in range(5)
            ]
            for item in (late, *reversed(same_time)):
                await store.write(item)

            ordered = await self._all(store, context.tenant_id)
            _check(ordered == [*same_time, late], f"records are out of order: {ordered!r}")
            page = await self._all(store, context.tenant_id, limit=2, offset=1)
            _check(page == same_time[1:3], f"limit/offset returned {page!r}")
            repeat = await self._all(store, context.tenant_id)
            _check(repeat == ordered, "the same query returned a different order")

        self._run(scenario)

    def test_parents_and_children_are_scoped_to_one_run(self) -> None:
        """`parents` and `children` return links of one run only."""

        async def scenario(store: ProvenanceStore) -> None:
            first, second = _context(), _context()
            mine = _link("a", "b", first)
            await store.write(mine)
            await store.write(_link("a", "b", second))
            await store.write(_link("a", "b", _context("tenant-b", first.run_id)))

            parents = await store.parents("b", context=first)
            children = await store.children("a", context=first)
            _check(list(parents) == [mine], f"parents crossed a run or tenant: {parents!r}")
            _check(list(children) == [mine], f"children crossed a run or tenant: {children!r}")
            _check(list(await store.parents("a", context=first)) == [], "a source had parents")

        self._run(scenario)

    def test_lineage_returns_every_upstream_link_nearest_first(self) -> None:
        """The inherited `lineage` walks every upstream link nearest first, through cycles."""

        async def scenario(store: ProvenanceStore) -> None:
            context = _context()
            chain = [
                _link("source", "input", context, timestamp=_EPOCH),
                _link("input", "score", context, timestamp=_EPOCH + timedelta(seconds=1)),
                _link("score", "decision", context, timestamp=_EPOCH + timedelta(seconds=2)),
                _link("decision", "input", context, timestamp=_EPOCH + timedelta(seconds=3)),
            ]
            for item in chain:
                await store.write(item)

            lineage = await store.lineage("decision", context=context)
            sources = [str(item.source_id) for item in lineage]
            _check(sources == ["score", "input", "source", "decision"], f"lineage: {sources}")
            nearest = await store.lineage("decision", context=context, max_depth=1)
            _check([str(item.source_id) for item in nearest] == ["score"], "max_depth ignored")

        self._run(scenario)

    def test_delete_run_removes_only_that_run_and_is_idempotent(self) -> None:
        """`delete_run` erases one run, counts what it deleted, and is safe to repeat."""

        async def scenario(store: ProvenanceStore) -> None:
            doomed = _context("tenant-a")
            kept = [_context("tenant-a"), _context("tenant-b", doomed.run_id)]
            for context in (doomed, *kept):
                await store.write(_execution(context, ExecutionStatus.COMPLETED))
                await store.write(ExecutionStartedEvent(context=context, sequence=0))
                await store.write(_link("a", "b", context))

            deleted = await store.delete_run(doomed)
            _check(deleted == 3, f"delete_run reported {deleted} deletions, expected 3")
            left = await self._all(store, "tenant-a", run_id=doomed.run_id)
            _check(left == [], f"delete_run left records behind: {left!r}")
            _check(list(await store.parents("b", context=doomed)) == [], "a link survived")
            for context in kept:
                survivors = await self._all(store, context.tenant_id, run_id=context.run_id)
                _check(len(survivors) == 3, f"delete_run touched another scope: {survivors!r}")
            again = await store.delete_run(doomed)
            _check(again == 0, f"a repeated delete_run reported {again} deletions")

        self._run(scenario)

    def test_concurrent_writes_are_all_kept(self) -> None:
        """Concurrent writes are all stored."""

        async def scenario(store: ProvenanceStore) -> None:
            context = _context()
            links = [_link(f"source-{index}", "decision", context) for index in range(50)]
            await asyncio.gather(*(store.write(item) for item in links))

            parents = await store.parents("decision", context=context)
            _check(len(parents) == len(links), f"kept {len(parents)} of {len(links)} writes")

        self._run(scenario)

    def _run(self, scenario: Callable[[ProvenanceStore], Awaitable[None]]) -> None:
        async def body() -> None:
            store = await self.make_store()
            try:
                await scenario(store)
            finally:
                await store.close()

        self.run_scenario(body())

    async def _all(
        self,
        store: ProvenanceStore,
        tenant_id: str,
        *,
        run_id: UUID | None = None,
        item_type: type[StoredItem] | type[XAIEvent] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StoredItem]:
        query = self.make_query(
            _APPLICATION, tenant_id, run_id=run_id, item_type=item_type, limit=limit, offset=offset
        )
        return [item async for item in store.query(query)]
