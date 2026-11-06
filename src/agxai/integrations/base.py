"""Framework-neutral instrumentation lifecycle for custom agent integrations."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator, Mapping

    from agxai.runtime import Run, XAIRuntime


class FrameworkInstrumentor[Target, Instrumented](ABC):
    """Adapt a framework to the runtime without depending on its implementation.

    Subclasses implement `instrument` and wrap each top-level call in `capture`
    or `capture_sync`. Those helpers activate a run for `record_*` calls, persist
    its outcome, and reuse the active run for nested calls of the same runtime.
    They do not change the wrapped application's result or suppress its errors.
    Framework-specific callbacks can record nodes, tools, and other artifacts
    through the runtime's public methods.
    """

    def __init__(self, runtime: XAIRuntime) -> None:
        self.runtime = runtime

    @abstractmethod
    def instrument(self, target: Target) -> Instrumented:
        """Return an instrumented target preserving the framework's call contract."""
        ...

    @asynccontextmanager
    async def capture(self, config: Mapping[str, Any] | None = None) -> AsyncIterator[Run]:
        """Capture an async call, reusing an existing run for nested calls."""
        if (active := self.runtime.current_run) is not None:
            yield active
            return
        run = await self.runtime.start_run(config)
        with self.runtime.activate_run(run):
            try:
                yield run
            except BaseException as error:
                await self.runtime.finish_run(
                    run,
                    error,
                    cancelled=isinstance(
                        error, (asyncio.CancelledError, GeneratorExit, KeyboardInterrupt)
                    ),
                )
                raise
            else:
                await self.runtime.finish_run(run)

    @contextmanager
    def capture_sync(self, config: Mapping[str, Any] | None = None) -> Iterator[Run]:
        """Capture a synchronous call, including calls made inside an event loop."""
        if (active := self.runtime.current_run) is not None:
            yield active
            return
        run = self.runtime.run_sync(self.runtime.start_run(config))
        with self.runtime.activate_run(run):
            try:
                yield run
            except BaseException as error:
                self.runtime.run_sync(
                    self.runtime.finish_run(
                        run,
                        error,
                        cancelled=isinstance(
                            error, (asyncio.CancelledError, GeneratorExit, KeyboardInterrupt)
                        ),
                    )
                )
                raise
            else:
                self.runtime.run_sync(self.runtime.finish_run(run))
