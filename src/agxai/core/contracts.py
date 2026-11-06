"""Provider-neutral capability contracts consumed by `XAIRuntime`.

Every capability is an abstract base class. A provider subclasses the
capability and implements its abstract methods; the runtime's `Registry`
rejects any object that does not. The runtime resolves capabilities by type
and never branches on concrete classes, so adding a backend never requires a
runtime change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from .models import (
        AttributionResult,
        CanonicalEvent,
        Execution,
        ExecutionContext,
        Explanation,
        ExplanationContext,
        PolicyAction,
        PolicyDecision,
        ProvenanceLink,
    )


@dataclass(frozen=True, slots=True)
class RunInterrupt:
    """A pause in a run, passed to `XAIRuntime.finish_run`.

    Framework instrumentors convert their framework's interrupt objects to this
    type. ``id`` is the framework's stable interrupt reference; ``value`` is the
    interrupt payload, sanitized before it is recorded.
    """

    id: str
    value: Any = None


class StoreQuery:
    """Base class for provider-specific, typed store query objects."""


class ProvenanceStore(ABC):
    """Base class for stores of executions, provenance links, and canonical events.

    The runtime uses `InMemoryProvenanceStore` unless another store is
    registered. To keep records in your own database, subclass this class and
    implement `write`, `get`, `query`, `parents`, `children`, and `delete_run`;
    `lineage` and `close` work as inherited. The repository's
    ``examples/postgres_store.py`` is a complete PostgreSQL store built this
    way, and `agxai.testing.ProvenanceStoreContract` checks a store against
    this contract.

    A store must:

    - make `write` an idempotent upsert keyed by the record's application,
      tenant, run, record type, and ID, where the latest write wins: an
      `Execution` is written when its run starts, when it finishes, and when a
      record is added after it finished. A record in one tenant or run never
      replaces a record in another, even if their IDs are equal;
    - scope `query` to one application and tenant, and `get`, `parents`,
      `children`, and `delete_run` to one run, so tenants and runs never see or
      change each other's records;
    - return results in a stable order.
    """

    @abstractmethod
    async def write(self, item: Execution | ProvenanceLink | CanonicalEvent) -> None:
        """Insert or replace one record."""
        ...

    @abstractmethod
    async def get(
        self, entity_id: str, *, context: ExecutionContext
    ) -> Execution | ProvenanceLink | CanonicalEvent | None:
        """Return the record whose ``id`` is ``entity_id`` in the context's run, or ``None``.

        Only the application, tenant, and run of ``context`` are searched, so a
        caller cannot read another tenant's record by guessing its ID.

        Raises:
            LookupError: If records of more than one type in the run share the ID.
        """
        ...

    @abstractmethod
    def query(
        self, query: StoreQuery
    ) -> AsyncIterator[Execution | ProvenanceLink | CanonicalEvent]:
        """Yield the records matching an isolation-aware query, in a stable order."""
        ...

    @abstractmethod
    async def parents(
        self, entity_id: str, *, context: ExecutionContext
    ) -> Sequence[ProvenanceLink]:
        """Return the links that point *into* ``entity_id`` (its direct sources) in one run."""
        ...

    @abstractmethod
    async def children(
        self, entity_id: str, *, context: ExecutionContext
    ) -> Sequence[ProvenanceLink]:
        """Return the links that point *out of* ``entity_id`` (what it produced) in one run."""
        ...

    @abstractmethod
    async def delete_run(self, context: ExecutionContext) -> int:
        """Delete every record of the context's run and return how many were deleted.

        Removes the run's execution, provenance links, and canonical events in
        the context's application and tenant, and nothing else. Deleting a run
        that has no records returns ``0``, so the call is idempotent. Use it to
        honor erasure requests and to apply a retention period.
        """
        ...

    async def lineage(
        self,
        entity_id: str,
        *,
        context: ExecutionContext,
        max_depth: int = 100,
    ) -> Sequence[ProvenanceLink]:
        """Return every upstream link of ``entity_id``, breadth-first and nearest first.

        Walks `parents` one level at a time and expands each entity once, so
        every link is returned exactly once and cycles terminate. Override it
        only to use a faster native query, such as a recursive SQL query.

        Raises:
            ValueError: If ``max_depth`` is less than 1.
        """
        if max_depth < 1:
            raise ValueError("max_depth must be positive")
        result: list[ProvenanceLink] = []
        visited = {entity_id}
        frontier = [entity_id]
        for _ in range(max_depth):
            next_frontier: list[str] = []
            for current in frontier:
                for link in await self.parents(current, context=context):
                    result.append(link)
                    source = str(link.source_id)
                    if source not in visited:
                        visited.add(source)
                        next_frontier.append(source)
            if not next_frontier:
                break
            frontier = next_frontier
        return tuple(result)

    async def close(self) -> None:  # noqa: B027 - optional hook, no-op by default
        """Release resources held by the store. The default does nothing."""


class ObservabilityProvider(ABC):
    """Base class for telemetry sinks of canonical events.

    The runtime forwards each canonical event to the registered provider, so an
    existing tracing stack gains the explainability layer without a separate
    integration per provider. Subclass it and implement `emit`; override
    `flush` and `close` if the backend buffers or holds a connection.
    `ObservabilityAdapter` is a subclass that adds deduplication and error
    wrapping.
    """

    @abstractmethod
    async def emit(self, event: CanonicalEvent) -> None:
        """Send one canonical event to the backend."""

    async def flush(self) -> None:  # noqa: B027 - optional hook, no-op by default
        """Deliver any buffered events. The default does nothing."""

    async def close(self) -> None:  # noqa: B027 - optional hook, no-op by default
        """Flush and release the backend connection. The default does nothing."""


class AttributionEngine(ABC):
    """Base class for engines that score what contributed to a decision, and by how much.

    See [Concepts: Attribution](../guide/concepts/attribution.md) for the output shape
    and what an `AttributionResult` does and does not claim.
    """

    @abstractmethod
    async def attribute(self, context: ExplanationContext) -> AttributionResult:
        """Return signed contributions for the decision in ``context``."""


class ExplanationEngine(ABC):
    """Base class for engines that assemble an `Explanation` from a policy-filtered context.

    Set ``requires_llm = True`` on a subclass whose `explain` calls a live model;
    the runtime then refuses to run it unless `XAIConfig.llm_explanation_enabled`
    is set.
    """

    requires_llm: ClassVar[bool] = False

    @abstractmethod
    async def explain(self, context: ExplanationContext) -> Explanation:
        """Render an explanation for ``context.audience``."""


class PolicyProvider(ABC):
    """Base class for policies that decide what an audience may see.

    See [Concepts: Policies](../guide/concepts/policies.md) for a real `PolicyDecision`
    and how the explanation engines honor it.
    """

    @abstractmethod
    async def evaluate(self, context: ExplanationContext, action: PolicyAction) -> PolicyDecision:
        """Return the policy decision for ``action`` and ``context.audience``."""


class CapturePolicy(ABC):
    """Base class for policies that decide whether each canonical event may be captured."""

    @abstractmethod
    async def evaluate(self, event: CanonicalEvent) -> PolicyDecision:
        """Return a decision whose ``allowed`` flag gates the event."""
