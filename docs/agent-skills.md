# Agent Skills

`agxai` publishes one portable Agent Skill that teaches coding agents
how to integrate, configure, test, and debug `agxai` in an
application. The skill is guidance for agents; it is not part of the Python
package and does not change how `agxai` is installed.

| Component | Location |
| --- | --- |
| agxai Python package | [`src/agxai/`](https://github.com/smuniharish/agxai/tree/master/src/agxai) |
| The Agent Skill | [`agxai-skills/skills/agxai/`](https://github.com/smuniharish/agxai/tree/master/agxai-skills/skills/agxai) |
| Its instructions | [`SKILL.md`](https://github.com/smuniharish/agxai/blob/master/agxai-skills/skills/agxai/SKILL.md) |

## What the skill contains

The skill follows the [Agent Skills specification](https://agentskills.io/specification).
Agents read `SKILL.md` first and open the other files only when a task needs
them:

- **`SKILL.md`**: when to use the skill, the core workflow, and the rules an
  integration follows. Its frontmatter has `name`, `description`, `license`,
  `compatibility`, and `metadata.version`, the `agxai` release it
  describes.
- **`references/API.md`**: public imports, runtime methods, settings, records,
  and provider contracts.
- **`references/RECIPES.md`**: complete patterns for instrumenting graphs and
  agents, extending custom frameworks through `FrameworkInstrumentor`,
  human-in-the-loop, disclosure policies, storage, tracing backends,
  failure modes, and LLM-phrased explanations.
- **`references/TROUBLESHOOTING.md`**: symptoms, causes, and fixes.
- **`scripts/verify_setup.py`**: an offline check that the project's
  environment has compatible versions and that the core records and explains.
  If LangGraph is installed, also checks graph capture and run linkage;
  `--langgraph` makes that integration mandatory.
- **`assets/test_disclosure_policy.py`**: a pytest template that tests what
  each audience may and may not see.

The repository validates the skill on every change: the reference validator,
link checks, the setup script, and the template run in its test suite. There
is no separate Claude, Codex, Cursor, or Copilot copy of the skill.

## Install from skills.sh

The [skills CLI](https://www.skills.sh/docs/cli) installs skills from a GitHub
source. Install the `agxai` skill directory directly:

```bash
npx skills add https://github.com/smuniharish/agxai/tree/master/agxai-skills/skills/agxai
```

This is the portable installation route. Follow the CLI's current target
selection prompts, then verify that it placed the `agxai` folder in
the target agent's supported skills directory. The shorthand
`npx skills add agxai-skills` is **not** a valid source identifier.

## Install manually

First obtain the canonical skill directory from the
[repository](https://github.com/smuniharish/agxai/tree/master/agxai-skills/skills/agxai).
Copy the complete `agxai` directory, including `SKILL.md`, into one
of the host-specific locations below.

### Claude Code

Claude Code discovers standalone skills in:

| Scope | Destination |
| --- | --- |
| Current repository | `.claude/skills/agxai/` |
| All local projects | `~/.claude/skills/agxai/` |

Start or restart Claude Code after copying the directory. Claude can select
the skill when its description matches the task, or you can invoke it with
`/agxai`. See [Claude Code Skills](https://code.claude.com/docs/en/skills).

`agxai` does not currently ship a Claude plugin manifest or marketplace
package. The standalone skill is sufficient today.

### Codex

Codex discovers repository skills by scanning `.agents/skills` from the
working directory to the repository root. Copy the directory to:

| Scope | Destination |
| --- | --- |
| Current repository | `.agents/skills/agxai/` |
| All local projects | `~/.agents/skills/agxai/` |

Codex detects changes automatically; restart it if the skill does not appear.
Invoke it explicitly with `$agxai` or use `/skills` to inspect
available skills. See [ChatGPT and Codex Skills](https://learn.chatgpt.com/docs/build-skills).

### Cursor

Cursor supports the standard `.agents/skills` locations, which makes the Codex
layout above portable. It also supports Cursor-specific locations:

| Scope | Destination |
| --- | --- |
| Current repository | `.agents/skills/agxai/` or `.cursor/skills/agxai/` |
| All local projects | `~/.agents/skills/agxai/` or `~/.cursor/skills/agxai/` |

Restart Cursor after copying the directory. In Agent chat, type `/` and select
`agxai` to attach it to a message; Cursor can also activate it from
its description. See [Cursor Agent Skills](https://cursor.com/docs/skills).

### GitHub Copilot

GitHub Copilot supports the standard `.agents/skills` layout, and also the
following project and personal locations:

| Scope | Destination |
| --- | --- |
| Current repository | `.agents/skills/agxai/`, `.github/skills/agxai/`, or `.claude/skills/agxai/` |
| All local projects | `~/.agents/skills/agxai/` or `~/.copilot/skills/agxai/` |

For Copilot CLI, start a new session or run `/skills reload`, then verify the
skill with `/skills info agxai`. You can explicitly request it in a
prompt using `/agxai`. See [Adding agent skills for GitHub Copilot
CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills).

### Other Agent Skills-compatible hosts

Use the host's documented skill directory and copy the complete
`agxai` folder there. The canonical skill relies only on the standard
`SKILL.md` frontmatter, so it does not require a host-specific adapter.

If a host needs package metadata, a registry entry, or a plugin manifest,
follow that host's current official documentation and add only a thin adapter
that points to this canonical skill. Do not duplicate the skill instructions.

## Update and verify

To update a manual installation, replace the complete installed
`agxai` folder with the latest directory from the repository, then
restart or reload the host.

After installation, confirm all of the following:

1. The directory name is `agxai`, and it contains `SKILL.md`,
   `references/`, `scripts/`, and `assets/`.
2. The host lists `agxai` as an available skill, if it exposes a
   skill listing command or UI.
3. From your project's Python environment, the setup check passes:

    ```bash
    python <skills directory>/agxai/scripts/verify_setup.py
    ```

    ```text
    PASS  Python 3.14.10 (3.12 or newer required)
    PASS  agxai 1.0.0 (1.x expected by this skill)
    PASS  pydantic 2.14.3 (>=2.14.3,<3 required)
    PASS  langgraph 1.2.20 (>=1.2.20,<2 required)
    PASS  langchain-core 1.7.6 (>=1.7.6,<2 required)
    INFO  optional integrations: langsmith 0.14.17, langfuse 5.2.0, opentelemetry-sdk 1.45.2, langchain-openai 1.7.4
    PASS  framework-neutral recording and explanation work
    PASS  instrumented graph recorded nodes ['score', 'route'], 2 state changes, 1 evidence, 1 decision
    PASS  auditor explanation: The routing decision selected 'REVIEW'.
    PASS  end-user explanation withholds the score and announces it
    PASS  no instrumentation errors (0 recorded)
    PASS  interrupt and resume recorded and linked through the checkpoint
    All checks passed.
    ```

4. A task about agent explainability, custom-framework integration, provenance,
   evidence, decisions, disclosure policy, or instrumentation activates the skill, or you can
   invoke it explicitly.

See the distribution's
[README](https://github.com/smuniharish/agxai/blob/master/agxai-skills/README.md)
and [validation process](https://github.com/smuniharish/agxai/blob/master/agxai-skills/validation/README.md)
for maintenance details.
