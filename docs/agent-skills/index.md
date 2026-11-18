# Agent Skills

agxai publishes two [Agent Skills](https://agentskills.io). They give a coding
agent the instructions, references, scripts, templates and tests it needs to
use agxai correctly. They work in Claude Code, Codex, Cursor, GitHub Copilot
and any other agent that reads the open Agent Skills format.

<div class="ax-agentic" markdown>

## Agentic installation

Install the skills so your coding agent knows how to:

- instrument your agent;
- record evidence and decisions;
- explain each decision to every audience under a tested disclosure policy;
- extend agxai to other frameworks and databases.

=== "Ask your coding agent"

    Give your coding agent the repository and let it install the skills it
    needs.

    ```text title="Agent instruction"
    Install the Agent Skills from https://github.com/smuniharish/agxai
    (agxai-skills/skills/agxai and agxai-skills/skills/agxai-extend) into
    this project, run the agxai skill's scripts/verify_setup.py, then add
    explainability to this application with agxai, following the skill's
    workflow and rules.
    ```

=== "skills CLI"

    The [skills CLI](https://github.com/vercel-labs/skills) finds both skills
    in the repository and installs them for the agents in your project. It
    needs Node.js 22.20 or later.

    ```bash
    npx skills add smuniharish/agxai
    ```

    To install a single skill, add `--skill agxai` or `--skill agxai-extend`.
    Add `-g` to install it for every project.

=== "Manual installation"

    Copy the skill directories into your agent's skills directory, for
    example:

    ```bash
    git clone --depth 1 https://github.com/smuniharish/agxai.git
    cp -r agxai/agxai-skills/skills/agxai .agents/skills/agxai
    cp -r agxai/agxai-skills/skills/agxai-extend .agents/skills/agxai-extend
    ```

    [Install in your agent](install.md) lists the directory each agent reads.

</div>

## The skills

<div class="grid cards" markdown>

-   :material-play-circle-outline:{ .lg .middle } __[agxai](agxai.md)__

    ---

    Adds agxai to an application. Covers instrumenting LangGraph graphs and
    LangChain agents, recording evidence and decisions, disclosure policies,
    human-in-the-loop, exporting to tracing backends, and troubleshooting.

    Includes an offline setup check and a disclosure-policy test template.

-   :material-puzzle-outline:{ .lg .middle } __[agxai-extend](agxai-extend.md)__

    ---

    Extends agxai. Use it to write a `FrameworkInstrumentor` for Agno, CrewAI
    or your own agent loop, or a `ProvenanceStore` for your database.

    Includes templates with their tests and a store contract checker.

</div>

Each skill tells the agent when to use the other one, so you can install both
and the agent picks the right one. If your application only uses agxai,
`agxai` alone is enough.

## Skills for supported integrations

Some optional integrations have separate, upstream-maintained Agent Skills.
They are not part of agxai and do not install or change Python dependencies.
Install only the skills relevant to your stack:

| Upstream | Skill | Use | Install |
| --- | --- | --- | --- |
| [Pydantic](https://github.com/pydantic/pydantic) | `pydantic` | Model and validate data with Pydantic. | `npx skills add https://github.com/pydantic/pydantic --skill pydantic` |
| [LangChain skills](https://github.com/langchain-ai/langchain-skills) | `langchain-build-agent` | Build or modify Deep Agents, LangGraph, or LangChain apps. | `npx skills add langchain-ai/langchain-skills --skill langchain-build-agent --yes` |
| [LangChain skills](https://github.com/langchain-ai/langchain-skills) | `langchain-agent-tracing` | Instrument and troubleshoot LangSmith tracing. | `npx skills add langchain-ai/langchain-skills --skill langchain-agent-tracing --yes` |
| [LangChain skills](https://github.com/langchain-ai/langchain-skills) | `langchain-agent-monitoring` | Set up production monitoring and online evaluation with LangSmith. | `npx skills add langchain-ai/langchain-skills --skill langchain-agent-monitoring --yes` |
| [LangChain skills](https://github.com/langchain-ai/langchain-skills) | `langchain-eval-engineering` | Design agent evaluations and benchmarks. | `npx skills add langchain-ai/langchain-skills --skill langchain-eval-engineering --yes` |
| [Langfuse skills](https://github.com/langfuse/skills) | `langfuse` | Work with Langfuse tracing, prompts, datasets, and evaluation. | `npx skills add langfuse/skills --skill langfuse` |
| [Langfuse skills](https://github.com/langfuse/skills) | `migrate-to-langfuse` | Migrate from another observability or evaluation platform. | `npx skills add langfuse/skills --skill migrate-to-langfuse` |

The LangChain skills repository notes that it is in early development. For
Langfuse API-backed actions, use an authorized project account and credentials;
never paste or commit credential values. Review each source and its current
prerequisites before installing; skill content can change independently of
agxai. We did not find verified, user-facing integration skills for the other
optional dependencies during this review.

## Use them

Once installed, describe the task. The agent loads a skill when the task
matches it:

| You ask | Skill |
| --- | --- |
| "Add explainability to my LangGraph agent and explain its routing decision." | `agxai` |
| "Show customers why a payment was held, without our fraud score." | `agxai` |
| "Record the reviewer's approval and link the resumed run." | `agxai` |
| "Ship agxai events to Langfuse without losing any on shutdown." | `agxai` |
| "Write an agxai integration for our CrewAI crew." | `agxai-extend` |
| "Store agxai records in SQLite, with tests that prove it works." | `agxai-extend` |

You can also invoke a skill by name: `/agxai` or `/agxai-extend` in Claude
Code, Cursor and GitHub Copilot, and `$agxai` or `$agxai-extend` in Codex.

Both skills teach the agent the rules that keep an integration correct:

- observe the application without steering it;
- record decisions explicitly instead of inferring them;
- never collect a model's chain-of-thought;
- never weaken a disclosure policy or a store contract to make a test pass.

## Next steps

<div class="grid cards" markdown>

-   :material-download:{ .lg .middle } __[Install in your agent](install.md)__

    ---

    Where each agent looks for skills, and how to verify and update an
    installation.

-   :material-check-decagram-outline:{ .lg .middle } __[Evaluation](evaluation.md)__

    ---

    How the skills are tested in CI and evaluated against real tasks.

</div>
