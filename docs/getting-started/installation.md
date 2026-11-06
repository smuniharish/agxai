# Installation

agxai needs Python 3.12 or newer. The core depends only on Pydantic; every
framework and provider integration is an optional extra.

## With LangGraph or LangChain

=== "pip"

    ```bash
    pip install "agxai[langgraph]"
    ```

=== "uv"

    ```bash
    uv add "agxai[langgraph]"
    ```

The `langgraph` extra installs LangGraph 1.x (1.2.20 or newer) and LangChain
Core 1.x (1.7.6 or newer).

## Core only

=== "pip"

    ```bash
    pip install agxai
    ```

=== "uv"

    ```bash
    uv add agxai
    ```

The core is framework-neutral. Use it with Agno, CrewAI or your own agent loop
by subclassing `FrameworkInstrumentor`; see
[Custom frameworks](../integrations/custom-frameworks.md).

## Extras

Combine extras as needed, for example
`pip install "agxai[langgraph,langsmith,otel]"`:

| Extra | Adds | Used by |
| --- | --- | --- |
| `langgraph` | `langgraph`, `langchain-core` | [LangGraph/LangChain instrumentation](../integrations/langgraph.md) |
| `langsmith` | `langsmith` | [`LangSmithObservability`](../integrations/langsmith.md) |
| `langfuse` | `langfuse` | [`LangfuseObservability`](../integrations/langfuse.md) |
| `otel` | `opentelemetry-api`, `opentelemetry-sdk` | [`OpenTelemetryObservability`](../integrations/opentelemetry.md) |
| `llm-openai` | `langchain-openai` | [LLM-phrased explanations](../guide/how-to/llm-explanations.md) |
| `all` | Every integration above | |

Storage needs no extra. Records are kept in memory by default; to use a
database, subclass `ProvenanceStore`, as in the
[PostgreSQL store example](../examples/postgres-store.md).

## Let your coding agent do it

The [agxai Agent Skills](../agent-skills/index.md) teach Claude Code, Codex,
Cursor, GitHub Copilot and other coding agents to install and integrate agxai.
Ask your agent:

```text title="Agent instruction"
Install the Agent Skills from https://github.com/smuniharish/agxai
(agxai-skills/skills/agxai and agxai-skills/skills/agxai-extend) into
this project, run the agxai skill's scripts/verify_setup.py, then add
explainability to this application with agxai, following the skill's
workflow and rules.
```

## Verify

```bash
python -c "import agxai; print(agxai.__version__)"
```

Next: the [Quickstart](quickstart.md).
