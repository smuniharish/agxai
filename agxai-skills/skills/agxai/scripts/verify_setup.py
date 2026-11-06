"""Check that agxai is installed and works in this Python environment.

Runs offline and changes nothing. Prints one PASS, FAIL, or INFO line per check
and exits with status 1 if any check fails:

    python scripts/verify_setup.py
"""

from __future__ import annotations

import argparse
import asyncio
import platform
import re
import sys
from importlib import metadata
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from agxai import ExplanationContext, PolicyAction, PolicyDecision, Run, XAIRuntime

REQUIRED = {
    "pydantic": ((2, 14, 3), (3,)),
}
LANGGRAPH = {
    "langgraph": ((1, 2, 20), (2,)),
    "langchain-core": ((1, 7, 6), (2,)),
}
OPTIONAL = ("langsmith", "langfuse", "opentelemetry-sdk", "langchain-openai")
SCORE = 0.9173

failures: list[str] = []


def report(passed: bool, message: str) -> bool:
    print(f"{'PASS' if passed else 'FAIL'}  {message}")
    if not passed:
        failures.append(message)
    return passed


def installed(distribution: str) -> str | None:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return None


def release(version: str) -> tuple[int, ...]:
    """The numeric release of a version string: "1.2.12rc1" -> (1, 2, 12)."""
    numbers = []
    for part in version.split(".")[:3]:
        digits = re.match(r"\d+", part)
        numbers.append(int(digits.group()) if digits else 0)
    return tuple(numbers)


def dotted(version: tuple[int, ...]) -> str:
    return ".".join(map(str, version))


def check_environment(*, langgraph: bool) -> bool:
    report(
        sys.version_info >= (3, 12),
        f"Python {platform.python_version()} (3.12 or newer required)",
    )
    version = installed("agxai")
    if version is None:
        return report(False, "agxai is not installed: pip install agxai")
    report(release(version)[:1] == (1,), f"agxai {version} (1.x expected by this skill)")
    required = REQUIRED | LANGGRAPH if langgraph else REQUIRED
    for distribution, (lowest, below) in required.items():
        found = installed(distribution)
        compatible = found is not None and lowest <= release(found) < below
        report(
            compatible,
            f"{distribution} {found or 'is not installed'} "
            f"(>={dotted(lowest)},<{dotted(below)} required)"
            + (
                '; install "agxai[langgraph]"'
                if distribution in LANGGRAPH and not compatible
                else ""
            ),
        )
    extras = {name: installed(name) for name in OPTIONAL}
    present = [f"{name} {version}" for name, version in extras.items() if version]
    absent = [name for name, version in extras.items() if not version]
    print(
        f"INFO  optional integrations: {', '.join(present) or 'none'}"
        + (f" (not installed: {', '.join(absent)})" if absent else "")
    )
    return not failures


class Review(TypedDict, total=False):
    amount: float
    score: float
    route: str


async def check_core() -> None:
    from agxai import ExecutionStatus, XAIRuntime

    runtime = XAIRuntime(application_id="verify-setup", graph_id="core")
    run = await runtime.start_run()
    with runtime.activate_run(run):
        evidence = await runtime.record_evidence(
            "rule", summary="Amount exceeds the review threshold."
        )
        decision = await runtime.record_decision("REVIEW", evidence_ids=[evidence.id])
    await runtime.finish_run(run)
    explanation = await runtime.explain_decision(decision, run=run)
    report(
        run.execution.status is ExecutionStatus.COMPLETED
        and bool(explanation.supporting_evidence)
        and not runtime.errors,
        "framework-neutral recording and explanation work",
    )
    await runtime.close()


class EndUserPolicy:
    """End users see the outcome and reasons only."""

    async def evaluate(self, context: ExplanationContext, action: PolicyAction) -> PolicyDecision:
        from agxai import Audience, PolicyDecision

        end_user = context.audience == Audience.END_USER
        return PolicyDecision(
            context=context.execution.context,
            policy_id="verify-setup",
            action=action,
            allowed=True,
            audience=context.audience,
            denied_fields={"contributing_factors", "supporting_evidence"} if end_user else set(),
        )


def review_graph(runtime: XAIRuntime):
    from langgraph.graph import END, START, StateGraph

    from agxai import DecisionFactor, DecisionType, EvidenceType

    async def score(state: Review) -> Review:
        await runtime.record_evidence(
            EvidenceType.TOOL_RESULT, summary=f"Risk model scored {SCORE}.", confidence=0.95
        )
        return {"score": SCORE}

    async def route(state: Review) -> Review:
        run = runtime.current_run
        assert run is not None
        evidence_ids = [item.id for item in run.evidence]
        await runtime.record_decision(
            "REVIEW",
            decision_type=DecisionType.ROUTING,
            candidate_actions=["APPROVE", "REVIEW"],
            evidence_ids=evidence_ids,
            factors=[DecisionFactor(name="score", value=state["score"], evidence_ids=evidence_ids)],
        )
        return {"route": "REVIEW"}

    builder = StateGraph(Review)
    builder.add_node("score", score)
    builder.add_node("route", route)
    builder.add_edge(START, "score")
    builder.add_edge("score", "route")
    builder.add_edge("route", END)
    return builder.compile()


async def check_recording() -> None:
    from agxai import Audience, PolicyProvider, XAIRuntime

    runtime = XAIRuntime(application_id="verify-setup", tenant_id="local", graph_id="review")
    graph = runtime.instrument(review_graph(runtime))
    with runtime.collect_runs() as runs:
        result = await graph.ainvoke({"amount": 9200.0})
    run: Run = runs[0]
    nodes = [node.node_id for node in run.execution.nodes]
    report(
        result.get("route") == "REVIEW"
        and nodes == ["score", "route"]
        and len(run.evidence) == len(run.decisions) == 1,
        f"instrumented graph recorded nodes {nodes}, "
        f"{len(run.execution.state_transitions)} state changes, "
        f"{len(run.evidence)} evidence, {len(run.decisions)} decision",
    )

    auditor = await runtime.explain_decision(run.decisions[0], audience=Audience.AUDITOR, run=run)
    report(
        bool(auditor.contributing_factors and auditor.supporting_evidence),
        f"auditor explanation: {auditor.summary}",
    )

    runtime.register(PolicyProvider, EndUserPolicy())
    customer = await runtime.explain_decision(run.decisions[0], audience=Audience.END_USER, run=run)
    report(
        not customer.contributing_factors
        and not customer.supporting_evidence
        and str(SCORE) not in customer.model_dump_json(exclude={"timestamp"})
        and len(customer.disclosure) == 2,
        "end-user explanation withholds the score and announces it",
    )
    report(not runtime.errors, f"no instrumentation errors ({len(runtime.errors)} recorded)")
    await runtime.close()


async def check_human_in_the_loop() -> None:
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Command, interrupt

    from agxai import ExecutionStatus, XAIRuntime

    def approve(state: Review) -> Review:
        answer = interrupt({"question": "Approve?"})
        return {"route": "APPROVED" if answer else "REJECTED"}

    builder = StateGraph(Review)
    builder.add_node("approve", approve)
    builder.add_edge(START, "approve")
    builder.add_edge("approve", END)
    runtime = XAIRuntime(application_id="verify-setup", tenant_id="local", graph_id="approval")
    graph = runtime.instrument(builder.compile(checkpointer=InMemorySaver()))
    thread = {"configurable": {"thread_id": "verify-setup"}}
    with runtime.collect_runs() as runs:
        await graph.ainvoke({"amount": 1.0}, thread)
        await graph.ainvoke(Command(resume=True), thread)
    paused, resumed = runs
    report(
        paused.execution.status is ExecutionStatus.INTERRUPTED
        and resumed.execution.status is ExecutionStatus.COMPLETED
        and resumed.execution.continuation_of == paused.run_id
        and any(item.restored for item in resumed.execution.checkpoints),
        "interrupt and resume recorded and linked through the checkpoint",
    )
    await runtime.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--langgraph", action="store_true", help="Require the LangGraph extra.")
    arguments = parser.parse_args()
    langgraph = arguments.langgraph or installed("langgraph") is not None
    if not langgraph:
        print('INFO  LangGraph checks skipped; install "agxai[langgraph]" to enable them.')
    if check_environment(langgraph=langgraph):
        checks = [check_core]
        if langgraph:
            checks.extend((check_recording, check_human_in_the_loop))
        for check in checks:
            try:
                asyncio.run(check())
            except Exception as error:  # report every failing check, then the summary
                report(False, f"{check.__name__}: {type(error).__name__}: {error}")
    print("All checks passed." if not failures else f"{len(failures)} check(s) failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
