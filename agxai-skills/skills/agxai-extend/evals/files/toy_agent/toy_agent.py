"""A tiny agent framework agxai does not know: the starting point of eval 1.

`Agent.arun` and `Agent.run` are the public entry points. Each tool call is
reported to every function in `Agent.on_tool_end`, a documented public hook.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field

type ToolHook = Callable[[str, float, bool], None]


@dataclass
class Agent:
    name: str
    tools: dict[str, Callable[[str], str]]
    on_tool_end: list[ToolHook] = field(default_factory=list)

    async def arun(self, task: str) -> str:
        results = []
        for tool_name, tool in self.tools.items():
            loop = asyncio.get_running_loop()
            started = loop.time()
            try:
                results.append(tool(task))
            except Exception:
                for hook in self.on_tool_end:
                    hook(tool_name, loop.time() - started, True)
                raise
            for hook in self.on_tool_end:
                hook(tool_name, loop.time() - started, False)
        return " | ".join(results)

    def run(self, task: str) -> str:
        return asyncio.run(self.arun(task))
