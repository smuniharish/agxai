"""Plugin contract for semantic artifacts recorded outside the core sinks."""

from __future__ import annotations

from abc import ABC, abstractmethod

from agxai.core.models import (
    AttributionResult,
    Decision,
    Evidence,
    Explanation,
    MemoryReference,
    PolicyDecision,
)

type SemanticArtifact = (
    Evidence | Decision | AttributionResult | Explanation | PolicyDecision | MemoryReference
)


class XAIPlugin(ABC):
    """Base class for instance-scoped consumers of semantic artifacts.

    Evidence, decisions, memory references, and artifacts passed to
    `XAIRuntime.record_artifact` are delivered to every registered plugin as they
    are recorded. Subclass it and implement `record` to persist them, forward
    them to a review queue, or index them for search; override `flush` and
    `close` if the plugin buffers or holds resources.
    """

    @abstractmethod
    async def record(self, artifact: SemanticArtifact) -> None:
        """Receive one semantic artifact."""

    async def flush(self) -> None:  # noqa: B027 - optional hook, no-op by default
        """Deliver any buffered artifacts. The default does nothing."""

    async def close(self) -> None:  # noqa: B027 - optional hook, no-op by default
        """Flush and release resources. The default does nothing."""
