# agxai

[![PyPI](https://img.shields.io/pypi/v/agxai.svg)](https://pypi.org/project/agxai/)
[![Python](https://img.shields.io/pypi/pyversions/agxai.svg)](https://pypi.org/project/agxai/)
[![CI](https://github.com/smuniharish/agxai/actions/workflows/ci.yml/badge.svg)](https://github.com/smuniharish/agxai/actions/workflows/ci.yml)
[![Docs](https://readthedocs.org/projects/agxai/badge/?version=latest)](https://agxai.readthedocs.io/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/smuniharish/agxai/blob/master/LICENSE)

**Explainability for AI agents: what ran, why it was decided, and
what each audience may see.**

`agxai` provides a framework-agnostic runtime for structured, versioned
execution records and explanations. Its optional LangGraph/LangChain integration
captures nodes, state changes, tools, retrievers, and human-in-the-loop interrupts
automatically. Your code records the
evidence it relied on and the decisions it made. From those records it builds
explanations for developers, auditors, business owners, or end users, filtered
by a disclosure policy you control.

![agxai architecture](https://raw.githubusercontent.com/smuniharish/agxai/master/docs/assets/diagrams/architecture-overview.png)

## Features

- **Optional LangGraph/LangChain instrumentation.** `runtime.instrument(graph)` records `invoke`,
  `stream`, `batch`, `astream_events`, and the other Runnable entry points,
  sync and async, without changing inputs, outputs, or exceptions. It works
  with `StateGraph`, the functional API, `create_agent`, `deepagents`,
  subgraphs, and MCP tools.
- **Human-in-the-loop aware.** Interrupts and resumes are recorded with the
  reviewer's answer. For a graph with a checkpointer, each run is linked to
  its checkpoints, and a resumed run points back to the run it continues, even
  across processes.
- **Evidence, decisions, and provenance as data.** Explanations are built from
  recorded facts, never from model reasoning.
- **Audience-aware explanations.** Attribution shows how much each factor and
  piece of evidence contributed. A per-audience policy decides what each
  reader sees, and withheld sections are announced.
- **Safe by default.** Credentials are redacted before anything is stored,
  explanations fail closed, LLM phrasing needs two explicit opt-ins, and
  instrumentation failures never break your graph unless you ask them to.
- **Pluggable.** Records are kept in memory by default. Subclass
  `ProvenanceStore` for your database; a complete PostgreSQL store is included
  as an example. Events can be forwarded to LangSmith, Langfuse, or any
  OpenTelemetry backend.
- **Extend to your framework.** Subclass `FrameworkInstrumentor` to wrap Agno,
  CrewAI, or your own agent loop using `capture()` / `capture_sync()` and the
  runtime's public recording methods. No built-in Agno or CrewAI adapter is
  claimed or required. See the [custom-framework example](examples/custom_framework.py)
  and [integration guide](https://agxai.readthedocs.io/en/latest/integrations/custom-frameworks/).

## Install

```bash
pip install agxai
```

Requires Python 3.12+ and Pydantic 2.x. The core installs no agent framework.
For the LangGraph quickstart below, install the `langgraph` extra, which adds
LangGraph 1.x (1.2.20 or newer) and LangChain Core 1.x (1.7.6 or newer).
LangGraph and LangChain are distinct projects supported by the same integration.
Integrations are optional extras:

```bash
pip install "agxai[langgraph]"  # LangGraph graphs and LangChain Runnables
pip install "agxai[langsmith]"   # LangSmithObservability
pip install "agxai[langfuse]"    # LangfuseObservability
pip install "agxai[otel]"        # OpenTelemetryObservability
pip install "agxai[llm-openai]"  # LLM-phrased explanations with langchain-openai
```

## LangGraph quickstart

```python
import asyncio
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from agxai import Audience, DecisionType, EvidenceType, XAIRuntime

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

The [fraud review example](https://agxai.readthedocs.io/en/latest/examples/full-explanation/)
goes further: it explains one decision to an auditor, with attribution and
evidence, and to a customer, with internal scores withheld and the withholding
disclosed.

## How it relates to tracing

LangSmith, Langfuse, and OpenTelemetry show **what ran**: run trees, spans,
latency, tokens. `agxai` records **why it was decided** and **who may
see the explanation**. The two work together, and the bundled adapters send
`agxai` events to the tracing backend you already use.

## Documentation

Full documentation: **[agxai.readthedocs.io](https://agxai.readthedocs.io/)**

- [Quickstart](https://agxai.readthedocs.io/en/latest/getting-started/quickstart/)
- [Concepts](https://agxai.readthedocs.io/en/latest/concepts/)
- [How-to guides](https://agxai.readthedocs.io/en/latest/how-to/)
- [Examples](https://agxai.readthedocs.io/en/latest/examples/)
- [API reference](https://agxai.readthedocs.io/en/latest/api/)

`agxai` 1.x follows semantic versioning: minor releases add features
without breaking your code or your stored records. Changes are listed in the
[changelog](https://github.com/smuniharish/agxai/blob/master/CHANGELOG.md).

An [Agent Skill](https://agxai.readthedocs.io/en/latest/agent-skills/)
teaches coding agents such as Claude Code, Codex, Cursor, and GitHub Copilot to
integrate `agxai` correctly.

## Contributing

Contributions are welcome. See
[CONTRIBUTING.md](https://github.com/smuniharish/agxai/blob/master/CONTRIBUTING.md)
for the development setup and checks, and
[SECURITY.md](https://github.com/smuniharish/agxai/blob/master/SECURITY.md)
to report a vulnerability.

## License

Apache License 2.0. See
[LICENSE](https://github.com/smuniharish/agxai/blob/master/LICENSE).
