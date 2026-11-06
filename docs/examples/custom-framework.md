# A custom framework without LangGraph

[`examples/custom_framework.py`](https://github.com/smuniharish/agxai/blob/master/examples/custom_framework.py)
is a complete, offline example of extending the runtime through
`FrameworkInstrumentor`.

```bash
pip install agxai
python examples/custom_framework.py
```

The example wraps an async review agent, records evidence and a routing
decision, and explains that decision to an auditor:

```text
Route: REVIEW
The routing decision selected 'REVIEW'.
```

`AgentInstrumentor.instrument()` preserves the callable's input and return
type. Its `capture()` context creates the run and makes it available to
recording calls. `collect_runs()` retains the run for explanation after the
agent returns.

Use the [custom-framework integration guide](../integrations/custom-frameworks.md)
to adapt this boundary to Agno, CrewAI, or your own agent framework. The
example requires none of those frameworks and does not claim their APIs.
