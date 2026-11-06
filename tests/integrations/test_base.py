from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

from agxai import ExecutionStatus, FrameworkInstrumentor, Run, XAIRuntime


class Instrumentor(FrameworkInstrumentor[Callable[[], str], Callable[[], str]]):
    def instrument(self, target: Callable[[], str]) -> Callable[[], str]:
        def call() -> str:
            with self.capture_sync():
                return target()

        return call


def test_instrumentor_is_abstract() -> None:
    assert FrameworkInstrumentor.__abstractmethods__ == {"instrument"}


async def test_async_capture_activates_and_collects_run() -> None:
    runtime = XAIRuntime()
    instrumentor = Instrumentor(runtime)
    with runtime.collect_runs() as runs:
        async with instrumentor.capture({"metadata": {"xai_graph_id": "custom"}}) as run:
            assert runtime.current_run is run
            assert run.execution.context.graph_id == "custom"
            async with instrumentor.capture() as nested:
                assert nested is run
                await runtime.record_decision("accept")
            assert runtime.current_run is run
    assert runs == [run]
    assert run.execution.status is ExecutionStatus.COMPLETED
    assert run.decisions[0].selected_action == "accept"
    assert runtime.current_run is None
    await runtime.close()


@pytest.mark.parametrize("synchronous", [False, True])
@pytest.mark.parametrize(
    ("error_type", "status"),
    [
        (ValueError, ExecutionStatus.FAILED),
        (asyncio.CancelledError, ExecutionStatus.CANCELLED),
        (KeyboardInterrupt, ExecutionStatus.CANCELLED),
        (GeneratorExit, ExecutionStatus.CANCELLED),
    ],
)
async def test_capture_preserves_errors(
    synchronous: bool, error_type: type[BaseException], status: ExecutionStatus
) -> None:
    runtime = XAIRuntime()
    instrumentor = Instrumentor(runtime)
    error = error_type("stopped")

    async def call() -> None:
        if synchronous:
            with instrumentor.capture_sync():
                raise error
        else:
            async with instrumentor.capture():
                raise error

    with runtime.collect_runs() as runs, pytest.raises(error_type) as caught:
        await call()
    assert caught.value is error
    assert runs[0].execution.status is status
    assert runtime.current_run is None
    await runtime.close()


@pytest.mark.parametrize("inside_loop", [False, True])
def test_sync_capture_and_nested_calls(inside_loop: bool) -> None:
    runtime = XAIRuntime()
    instrumentor = Instrumentor(runtime)

    def target() -> str:
        assert runtime.current_run is not None
        runtime.run_sync(runtime.record_decision("accept"))
        with instrumentor.capture_sync() as nested:
            assert nested is runtime.current_run
        return "unchanged"

    def check() -> None:
        with runtime.collect_runs() as runs:
            assert instrumentor.instrument(target)() == "unchanged"
        assert len(runs) == 1
        assert runs[0].execution.status is ExecutionStatus.COMPLETED
        assert len(runs[0].decisions) == 1
        assert runtime.current_run is None

    async def check_in_loop() -> None:
        check()
        await runtime.close()

    if inside_loop:
        asyncio.run(check_in_loop())
    else:
        check()
        runtime.run_sync(runtime.close())


async def test_activation_restores_previous_run() -> None:
    runtime = XAIRuntime()
    first, second = await runtime.start_run(), await runtime.start_run()
    with runtime.activate_run(first):
        with runtime.activate_run(second):
            assert runtime.current_run is second
        assert runtime.current_run is first
    assert runtime.current_run is None
    await runtime.finish_run(first)
    await runtime.finish_run(second)
    await runtime.close()
    with pytest.raises(RuntimeError, match="closed"), runtime.activate_run(first):
        pass


async def test_concurrent_captures_are_isolated() -> None:
    runtime = XAIRuntime()
    instrumentor = Instrumentor(runtime)

    async def call(action: str) -> Run:
        async with instrumentor.capture() as run:
            await asyncio.sleep(0)
            assert runtime.current_run is run
            await runtime.record_decision(action)
            return run

    left, right = await asyncio.gather(call("left"), call("right"))
    assert left is not right
    assert [item.selected_action for item in left.decisions] == ["left"]
    assert [item.selected_action for item in right.decisions] == ["right"]
    await runtime.close()
