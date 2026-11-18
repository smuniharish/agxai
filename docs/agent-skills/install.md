# Install in your agent

Each skill is one directory with `SKILL.md` at its root: `agxai` and
`agxai-extend`. Every agent that supports the
[Agent Skills format](https://agentskills.io/specification) reads the same
directories, so there is no separate copy per agent.

## With the skills CLI

The [skills CLI](https://github.com/vercel-labs/skills) finds both skills in
the repository, detects the agents in your project, and installs the skills
into each agent you choose. It needs Node.js 22.20 or later.

```bash
npx skills add smuniharish/agxai                       # choose interactively
npx skills add smuniharish/agxai --skill agxai         # only the core skill
npx skills add smuniharish/agxai --skill agxai-extend  # only the extension skill
```

| Option | Effect |
| --- | --- |
| `-g` | Install for every project instead of the current one |
| `-a claude-code` | Install for one agent; see the CLI's [agent list](https://github.com/vercel-labs/skills/blob/main/docs/agents.md) |

## Manually

Copy each complete skill directory, including `SKILL.md`, `references/`,
`scripts/` and `assets/`, into one of the locations for your agent. The
[`agxai`](https://github.com/smuniharish/agxai/tree/master/agxai-skills/skills/agxai)
and [`agxai-extend`](https://github.com/smuniharish/agxai/tree/master/agxai-skills/skills/agxai-extend)
directories are in the agxai repository. Their `evals/` folders only test the
skills, so you can leave them out.

=== "Claude Code"

    | Scope | Destination |
    | --- | --- |
    | Current repository | `.claude/skills/<skill>/` |
    | All local projects | `~/.claude/skills/<skill>/` |

    Restart Claude Code. It selects a skill when the task matches, or invoke
    it with `/agxai` or `/agxai-extend`. See
    [Claude Code Skills](https://code.claude.com/docs/en/skills).

=== "Codex"

    | Scope | Destination |
    | --- | --- |
    | Current repository | `.agents/skills/<skill>/` |
    | All local projects | `~/.agents/skills/<skill>/` |

    Codex detects new skills automatically; restart it if a skill doesn't
    appear. Invoke one with `$agxai` or `$agxai-extend`, or list skills with
    `/skills`. See [Codex Skills](https://learn.chatgpt.com/docs/build-skills).

=== "Cursor"

    | Scope | Destination |
    | --- | --- |
    | Current repository | `.agents/skills/<skill>/` or `.cursor/skills/<skill>/` |
    | All local projects | `~/.agents/skills/<skill>/` or `~/.cursor/skills/<skill>/` |

    Restart Cursor. In Agent chat, type `/` and select the skill, or let
    Cursor activate it from its description. See
    [Cursor Agent Skills](https://cursor.com/docs/skills).

=== "GitHub Copilot"

    | Scope | Destination |
    | --- | --- |
    | Current repository | `.agents/skills/<skill>/`, `.github/skills/<skill>/` or `.claude/skills/<skill>/` |
    | All local projects | `~/.agents/skills/<skill>/` or `~/.copilot/skills/<skill>/` |

    In Copilot CLI, start a new session or run `/skills reload`, then check
    with `/skills info agxai`. Invoke a skill with `/agxai` or
    `/agxai-extend`. See
    [Adding agent skills for GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills).

=== "Other agents"

    Copy the skill folders into the skills directory your agent documents.
    The skills use only standard `SKILL.md` frontmatter, so they need no
    agent-specific adapter.

    If an agent needs a manifest or registry entry, add only a thin adapter
    that points to these directories. Don't copy the instructions.

## Verify

1. Each installed directory is named after its skill (`agxai` or
   `agxai-extend`) and contains `SKILL.md`.
2. Your agent lists the skills, if it has a skill list.
3. From your project's Python environment, the agxai setup check passes:

    ```bash
    python <skills directory>/agxai/scripts/verify_setup.py
    ```

    Example output, with versions and optional checks varying by environment:

    ```text
    PASS  Python <installed version> (3.12 or newer required)
    PASS  agxai <installed version> (1.x expected by this skill)
    ...
    All checks passed.
    ```

    Without the `agxai[langgraph]` extra, the LangGraph checks are skipped
    and the core checks still run. Add `--langgraph` to fail instead, or
    `--json` to print one JSON object.

4. If you installed `agxai-extend`, its store template passes the store
   contract:

    ```bash
    cd <skills directory>/agxai-extend
    python scripts/check_store.py store_template:TableProvenanceStore --path assets
    ```

    The last line is `All 11 promises hold.`

## Update

Run `npx skills update`, or replace the installed folders with the latest
directories from the repository, then restart or reload your agent. Each
skill's `metadata.version` matches the agxai release it describes.
