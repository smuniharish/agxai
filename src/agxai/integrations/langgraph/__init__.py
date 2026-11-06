"""LangGraph public-API instrumentation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agxai.integrations import FrameworkInstrumentor

from .graph import InstrumentedGraph

if TYPE_CHECKING:
    from langchain_core.runnables import Runnable


class LangGraphInstrumentor[Input, Output](
    FrameworkInstrumentor[
        "Runnable[Input, Output] | InstrumentedGraph[Input, Output]",
        InstrumentedGraph[Input, Output],
    ]
):
    """Instrument LangGraph graphs and LangChain Runnables with the same runtime."""

    def instrument(
        self, target: Runnable[Input, Output] | InstrumentedGraph[Input, Output]
    ) -> InstrumentedGraph[Input, Output]:
        """Wrap a target once per runtime, preserving all supported entry points."""
        if isinstance(target, InstrumentedGraph):
            if target.runtime is self.runtime:
                return target
            target = target.__wrapped__
        return InstrumentedGraph(target, self.runtime)


__all__ = ["InstrumentedGraph", "LangGraphInstrumentor"]
