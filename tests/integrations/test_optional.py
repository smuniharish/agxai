"""Core imports and manual recording must not require any framework."""

from __future__ import annotations

import builtins
import subprocess
import sys
from typing import Any

import pytest
from langchain_core.runnables import RunnableLambda

from agxai import XAIRuntime


def test_core_without_framework_imports() -> None:
    code = """
import asyncio
import importlib.abc
import sys

class BlockFrameworks(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.partition('.')[0] in {'langgraph', 'langchain', 'langchain_core'}:
            raise ModuleNotFoundError(fullname, name=fullname)

sys.meta_path.insert(0, BlockFrameworks())
import agxai
from agxai.core import InterruptLike

async def main():
    runtime = agxai.XAIRuntime()
    run = await runtime.start_run()
    with runtime.activate_run(run):
        evidence = await runtime.record_evidence('rule', summary='Amount exceeds limit')
        decision = await runtime.record_decision('review', evidence_ids=[evidence.id])
    await runtime.finish_run(run)
    explanation = await runtime.explain_decision(decision, run=run)
    assert explanation.supporting_evidence
    await runtime.close()
    try:
        runtime.instrument(object())
    except ImportError as error:
        assert 'pip install "agxai[langgraph]"' in str(error)
    else:
        raise AssertionError('missing extra must raise')
asyncio.run(main())
assert not any(name.partition('.')[0] in {'langgraph', 'langchain_core'} for name in sys.modules)
"""
    result = subprocess.run(  # noqa: S603 - fixed code and interpreter
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=30, check=False
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("missing", ["langgraph", "langchain_core", "unrelated", None])
def test_instrument_import_errors_are_specific(
    monkeypatch: pytest.MonkeyPatch, missing: str | None
) -> None:
    original = builtins.__import__

    def importing(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "agxai.integrations.langgraph":
            raise ModuleNotFoundError("missing", name=missing)
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", importing)
    target = RunnableLambda(lambda value: value)
    if missing in {"langgraph", "langchain_core"}:
        with pytest.raises(ImportError, match=r"agxai\[langgraph\]"):
            XAIRuntime().instrument(target)
    else:
        with pytest.raises(ModuleNotFoundError, match="missing"):
            XAIRuntime().instrument(target)
