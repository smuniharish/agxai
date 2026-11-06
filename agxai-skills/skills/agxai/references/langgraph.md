# LangGraph and LangChain

Read this file when instrumenting a LangGraph graph, a LangChain runnable, or a prebuilt agent. Each pattern follows a tested example: <https://github.com/smuniharish/agxai/tree/master/examples>.

## Contents

- [Instrument a graph and explain a decision](#instrument-a-graph-and-explain-a-decision)
- [Synchronous graphs and nodes](#synchronous-graphs-and-nodes)
- [Prebuilt agents](#prebuilt-agents)
- [Correlate runs across agents and services](#correlate-runs-across-agents-and-services)

## Instrument a graph and explain a decision

A complete program. Nodes record evidence and the decision; the caller keeps
the run and explains the decision to an auditor.

Install `pip install "agxai[langgraph]"` for the LangGraph recipes.

```python
import asyncio
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from agxai import Audience, DecisionFactor, DecisionType, EvidenceType, XAIRuntime

runtime = XAIRuntime(application_id="payments", tenant_id="acme-bank", graph_id="fraud-review")


class Review(TypedDict, total=False):
    amount: float
    risk_score: float
    route: str


async def score_risk(state: Review) -> Review:
    risk_score = 0.91 if state["amount"] > 5000 else 0.12
    await runtime.record_evidence(
        EvidenceType.TOOL_RESULT,
        summary=f"Fraud model scored the transaction {risk_score:.2f}.",
        confidence=0.97,
    )
    return {"risk_score": risk_score}


async def route(state: Review) -> Review:
    run = runtime.current_run
    assert run is not None
    selected = "HUMAN_REVIEW" if state["risk_score"] >= 0.8 else "AUTO_APPROVE"
    evidence_ids = [item.id for item in run.evidence]
    await runtime.record_decision(
        selected,
        decision_type=DecisionType.ROUTING,
        candidate_actions=["AUTO_APPROVE", "HUMAN_REVIEW"],
        evidence_ids=evidence_ids,
        factors=[
            DecisionFactor(
                name="fraud_risk_score", value=state["risk_score"], evidence_ids=evidence_ids
            )
        ],
        confidence=0.93,
    )
    return {"route": selected}


builder = StateGraph(Review)
builder.add_node("score_risk", score_risk)
builder.add_node("route", route)
builder.add_edge(START, "score_risk")
builder.add_edge("score_risk", "route")
builder.add_edge("route", END)
graph = runtime.instrument(builder.compile())


async def main() -> None:
    with runtime.collect_runs() as runs:
        result = await graph.ainvoke({"amount": 9200.0})
    (run,) = runs
    explanation = await runtime.explain_decision(
        run.decisions[-1], audience=Audience.AUDITOR, run=run
    )
    print(result["route"], explanation.summary, explanation.reasons)


asyncio.run(main())
```

- The graph's output is unchanged. `run.execution` holds the nodes and state
  changes; `run.evidence` and `run.decisions` hold what the nodes recorded.
- Record a decision where it is made, with its alternatives and the evidence
  it relied on. Factors with `evidence_ids` drive attribution.
- Link derived data with `record_provenance(source_id, target_id, "DERIVED_FROM")`,
  for example from a transaction URI to the evidence computed from it.

## Synchronous graphs and nodes

`invoke`, `stream`, and `batch` are recorded like their async forms. Inside a
synchronous node, run a recording coroutine with `run_sync`:

```python
def score_risk(state: Review) -> Review:
    risk_score = 0.91 if state["amount"] > 5000 else 0.12
    runtime.run_sync(
        runtime.record_evidence(EvidenceType.TOOL_RESULT, summary=f"Scored {risk_score:.2f}.")
    )
    return {"risk_score": risk_score}


with runtime.collect_runs() as runs:
    result = graph.invoke({"amount": 9200.0})
explanation = runtime.run_sync(runtime.explain_decision(runs[0].decisions[-1], run=runs[0]))
```

The current run reaches tools, middleware, and subgraphs through context
variables. In a thread you start yourself, pass `run=` explicitly.

## Prebuilt agents

`create_agent` and `create_deep_agent` return compiled graphs. Instrument the
agent; tool calls are captured automatically. Record the decision in
middleware once the model has finished:

```python
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage


class DecisionRecorder(AgentMiddleware):
    def __init__(self, runtime: XAIRuntime) -> None:
        super().__init__()
        self.runtime = runtime

    async def aafter_model(self, state, runtime):
        # `runtime` is the agent's LangGraph runtime (injected by name); agxai's is self.runtime.
        messages = state["messages"]
        if getattr(messages[-1], "tool_calls", None):
            return None  # the model asked for another tool
        results = [message for message in messages if isinstance(message, ToolMessage)]
        evidence = [
            await self.runtime.record_evidence(
                EvidenceType.TOOL_RESULT,
                summary=f"{message.name} returned {message.text}.",
                content_reference=f"tool-call://{message.tool_call_id}",
            )
            for message in results
        ]
        score = max((float(message.text) for message in results), default=0.0)
        await self.runtime.record_decision(
            "ESCALATE_FOR_REVIEW" if score >= 0.8 else "NO_ACTION",
            decision_type=DecisionType.ESCALATION,
            candidate_actions=["ESCALATE_FOR_REVIEW", "NO_ACTION"],
            evidence_ids=[item.id for item in evidence],
        )
        return None


agent = create_agent(model, tools=[check_fraud_risk], middleware=[DecisionRecorder(runtime)])
with runtime.collect_runs() as runs:
    await runtime.instrument(agent).ainvoke({"messages": [{"role": "user", "content": question}]})
```

An agent called inside a node of an instrumented graph joins that graph's run.

## Correlate runs across agents and services

Pass identifiers in the LangChain config of each call:

```python
await graph.ainvoke(
    payload,
    {
        "metadata": {"trace_id": "req-8841", "xai_tenant_id": "globex"},
        "configurable": {"thread_id": "review-42"},
    },
)
```

- `trace_id` ties runs of different graphs and services to one request, and
  observability adapters attach it as `xai.trace_id`.
- `xai_application_id`, `xai_tenant_id`, `xai_graph_id`, and `xai_run_id`
  override the runtime's defaults for one call.
- Query a store with `StoreFilter(application_id=..., tenant_id=..., run_id=...)`.
