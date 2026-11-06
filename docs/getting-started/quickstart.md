# Quickstart

This guide uses the optional LangGraph integration to instrument a two-node
fraud-review graph, record its evidence and decision, and explain that decision
to an auditor. It takes about five minutes and needs no external services.

## Requirements

- Python 3.12 or newer
- LangGraph 1.x, 1.2.20 or newer, and LangChain Core 1.x, 1.7.6 or newer,
  installed automatically by the `langgraph` extra

## Install

=== "pip"

    ```bash
    pip install "agxai[langgraph]"
    ```

=== "uv"

    ```bash
    uv add "agxai[langgraph]"
    ```

For other extras, and for using agxai without LangGraph, see
[Installation](installation.md).

## 1. Create a runtime

An `XAIRuntime` owns the configuration and providers for one application. It
works with zero configuration: records go to an in-memory store, and
explanations are built deterministically without a model.

```python
from agxai import XAIRuntime

runtime = XAIRuntime(application_id="payments", tenant_id="acme-bank", graph_id="fraud-review")
```

The three identifiers are stamped on every record, so runs from different
applications, tenants, and graphs never mix.

## 2. Record evidence and decisions in your nodes

Instrumentation captures *what ran*. Your nodes record *why*: the evidence they
relied on and the decision they made. `runtime.current_run` is the run of the
instrumented call that is executing the node.

```python
from typing import TypedDict

from agxai import DecisionType, EvidenceType


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
    run = runtime.current_run  # the run of the instrumented call executing this node
    assert run is not None
    selected = "HUMAN_REVIEW" if state["risk_score"] >= 0.8 else "AUTO_APPROVE"
    await runtime.record_decision(
        selected,
        decision_type=DecisionType.ROUTING,
        candidate_actions=["AUTO_APPROVE", "HUMAN_REVIEW"],
        evidence_ids=[item.id for item in run.evidence],
        confidence=0.93,
    )
    return {"route": selected}
```

## 3. Instrument the graph

Build and compile the graph as usual, then wrap it. The wrapper behaves exactly
like the compiled graph.

```python
from langgraph.graph import END, START, StateGraph

builder = StateGraph(Review)
builder.add_node("score_risk", score_risk)
builder.add_node("route", route)
builder.add_edge(START, "score_risk")
builder.add_edge("score_risk", "route")
builder.add_edge("route", END)
graph = runtime.instrument(builder.compile())
```

## 4. Run the graph and explain the decision

`collect_runs()` hands you the run started by the call, so you can explain it
after the call returns.

```python
import asyncio

from agxai import Audience


async def main() -> None:
    with runtime.collect_runs() as runs:
        result = await graph.ainvoke({"amount": 9200.0})
    (run,) = runs

    print(result)
    print([f"{node.node_id}: {node.status}" for node in run.execution.nodes])

    explanation = await runtime.explain_decision(
        run.decisions[0], audience=Audience.AUDITOR, run=run
    )
    print(explanation.summary)
    print(explanation.reasons)


asyncio.run(main())
```

Output:

```text
{'amount': 9200.0, 'risk_score': 0.91, 'route': 'HUMAN_REVIEW'}
['score_risk: completed', 'route: completed']
The routing decision selected 'HUMAN_REVIEW'.
['Selected action: HUMAN_REVIEW.', 'Alternatives considered: AUTO_APPROVE.', 'Decision confidence: 0.93.']
```

The graph's output is unchanged. Alongside it, the run recorded an `Execution`
with both nodes and their state changes, the evidence, and the decision. The
explanation also carries attribution scores and evidence references; the
[fraud review example](../examples/full-explanation.md) prints the complete
object for two audiences.

## Synchronous graphs

`invoke`, `stream`, and `batch` are instrumented the same way. Recording
methods are coroutines, so a synchronous node runs them with `runtime.run_sync`:

```python
def score_risk(state: Review) -> Review:
    risk_score = 0.91 if state["amount"] > 5000 else 0.12
    runtime.run_sync(
        runtime.record_evidence(EvidenceType.TOOL_RESULT, summary=f"Scored {risk_score:.2f}.")
    )
    return {"risk_score": risk_score}
```

`run_sync` reuses one event loop per thread and carries the caller's context,
so the evidence lands in the run of the graph call that executes the node.

## Next steps

- Withhold internal scores from end users with a
  [disclosure policy](../guide/how-to/disclosure-policies.md).
- Keep records in your database by subclassing `ProvenanceStore`, as in the
  [PostgreSQL store example](../examples/postgres-store.md), or forward them
  to [LangSmith](../integrations/langsmith.md),
  [Langfuse](../integrations/langfuse.md), or
  [OpenTelemetry](../integrations/opentelemetry.md).
- Choose how much state to capture and how failures behave in
  [Configuration](configuration.md).
- Learn the data model in [Concepts](../guide/concepts/index.md).
