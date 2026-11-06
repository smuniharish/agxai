"""Extend agxai for your own framework without installing LangGraph."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from agxai import Audience, DecisionType, FrameworkInstrumentor, XAIRuntime

type Agent = Callable[[float], Awaitable[str]]


class AgentInstrumentor(FrameworkInstrumentor[Agent, Agent]):
    """Wrap an async agent callable; adapt this boundary to your framework."""

    def instrument(self, target: Agent) -> Agent:
        async def call(amount: float) -> str:
            async with self.capture():
                return await target(amount)

        return call


async def main() -> None:
    runtime = XAIRuntime(application_id="payments", graph_id="custom-agent")

    async def review(amount: float) -> str:
        evidence = await runtime.record_evidence("rule", summary=f"Transaction amount: {amount}.")
        route = "REVIEW" if amount > 5000 else "APPROVE"
        await runtime.record_decision(
            route,
            decision_type=DecisionType.ROUTING,
            candidate_actions=["APPROVE", "REVIEW"],
            evidence_ids=[evidence.id],
        )
        return route

    agent = AgentInstrumentor(runtime).instrument(review)
    with runtime.collect_runs() as runs:
        print(f"Route: {await agent(9200)}")
    (run,) = runs
    explanation = await runtime.explain_decision(
        run.decisions[0], audience=Audience.AUDITOR, run=run
    )
    print(explanation.summary)
    await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())
