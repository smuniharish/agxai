"""A `ProvenanceStore` template shaped like one database table.

Copy this file into your project, rename `TableProvenanceStore`, and replace
each `self._rows` operation with a call to your database. The comment above
each operation shows the SQL it stands for. The template passes
`agxai.testing.ProvenanceStoreContract` unchanged (see ``test_store_contract.py``),
so run the contract after every change.

Table layout, one row per record:

    PRIMARY KEY (application_id, tenant_id, run_id, record_type, record_id)
    timestamp, sequence, source_id, target_id, payload (JSON)
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from agxai import Execution, ProvenanceLink, ProvenanceStore, StoreFilter
from agxai.core import XAIEvent

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Sequence
    from datetime import datetime

    from agxai import ExecutionContext
    from agxai.core import CanonicalEvent, StoreQuery

    type StoredItem = Execution | ProvenanceLink | CanonicalEvent

type Key = tuple[str, str, str, str, str]

# Every concrete record type, by the name stored in the record_type column.
MODELS: dict[str, type[Execution | ProvenanceLink | XAIEvent]] = {
    model.__name__: model for model in (Execution, ProvenanceLink, *XAIEvent.__subclasses__())
}


@dataclass(frozen=True, slots=True)
class Row:
    record_type: str
    timestamp: datetime
    sequence: int
    record_id: str
    source_id: str | None
    target_id: str | None
    payload: str

    @property
    def order(self) -> tuple[datetime, int, str]:
        return (self.timestamp, self.sequence, self.record_id)

    def load(self) -> StoredItem:
        return cast("StoredItem", MODELS[self.record_type].model_validate_json(self.payload))


def scope(context: ExecutionContext) -> tuple[str, str, str]:
    return (context.application_id, context.tenant_id, str(context.run_id))


def record_types(item_type: type | None) -> set[str] | None:
    """The stored type names a `StoreFilter.item_type` selects, subclasses included."""
    if item_type is None:
        return None
    return {name for name, model in MODELS.items() if issubclass(model, item_type)}


class TableProvenanceStore(ProvenanceStore):
    """Executions, events, and provenance links in one table, isolated by tenant and run."""

    def __init__(self) -> None:
        self._rows: dict[Key, Row] = {}
        # A thread lock, not an asyncio lock: the runtime may call one store from several loops.
        self._lock = threading.Lock()

    async def write(self, item: StoredItem) -> None:
        # INSERT ... ON CONFLICT (primary key) DO UPDATE SET every column
        link = item if isinstance(item, ProvenanceLink) else None
        row = Row(
            record_type=type(item).__name__,
            timestamp=item.timestamp,
            sequence=getattr(item, "sequence", -1),
            record_id=str(item.id),
            source_id=str(link.source_id) if link else None,
            target_id=str(link.target_id) if link else None,
            payload=item.model_dump_json(),
        )
        with self._lock:
            self._rows[(*scope(item.context), row.record_type, row.record_id)] = row

    async def get(self, entity_id: str, *, context: ExecutionContext) -> StoredItem | None:
        # SELECT ... WHERE <run scope> AND record_id = $1 LIMIT 2
        with self._lock:
            rows = [
                row
                for key, row in self._rows.items()
                if key[:3] == scope(context) and row.record_id == entity_id
            ]
        if len(rows) > 1:
            raise LookupError("entity ID is ambiguous; use an isolation-aware query")
        return rows[0].load() if rows else None

    async def query(self, query: StoreQuery) -> AsyncIterator[StoredItem]:
        # SELECT ... WHERE application_id, tenant_id [AND run_id] [AND record_type = ANY($types)]
        # ORDER BY timestamp, sequence, record_id LIMIT $limit OFFSET $offset
        if not isinstance(query, StoreFilter):
            raise TypeError(f"{type(self).__name__} requires StoreFilter")
        types = record_types(query.item_type)
        with self._lock:
            rows = [
                row
                for key, row in self._rows.items()
                if key[:2] == (query.application_id, query.tenant_id)
                and (query.run_id is None or key[2] == query.run_id)
                and (types is None or row.record_type in types)
            ]
        rows.sort(key=lambda row: row.order)
        for row in rows[query.offset : query.offset + query.limit]:
            yield row.load()

    async def parents(
        self, entity_id: str, *, context: ExecutionContext
    ) -> Sequence[ProvenanceLink]:
        # SELECT ... WHERE <run scope> AND record_type = 'ProvenanceLink' AND target_id = $1
        return self._links(context, lambda row: row.target_id == entity_id)

    async def children(
        self, entity_id: str, *, context: ExecutionContext
    ) -> Sequence[ProvenanceLink]:
        # SELECT ... WHERE <run scope> AND record_type = 'ProvenanceLink' AND source_id = $1
        return self._links(context, lambda row: row.source_id == entity_id)

    async def delete_run(self, context: ExecutionContext) -> int:
        # DELETE FROM records WHERE <run scope>, returning the row count
        with self._lock:
            keys = [key for key in self._rows if key[:3] == scope(context)]
            for key in keys:
                del self._rows[key]
        return len(keys)

    async def close(self) -> None:
        # Close the connection pool here, if the store owns it.
        pass

    def _links(
        self, context: ExecutionContext, matches: Callable[[Row], bool]
    ) -> list[ProvenanceLink]:
        with self._lock:
            rows = [
                row
                for key, row in self._rows.items()
                if key[:3] == scope(context)
                and row.record_type == "ProvenanceLink"
                and matches(row)
            ]
        rows.sort(key=lambda row: row.order)
        return [cast("ProvenanceLink", row.load()) for row in rows]
