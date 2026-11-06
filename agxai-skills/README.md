# agxai Agent Skills

This directory distributes two Agent Skills that teach coding agents to use
the `agxai` package correctly. They are not part of the Python package and add
no runtime behavior.

| Skill | Use it to |
| --- | --- |
| [`agxai`](skills/agxai/SKILL.md) | Add agxai to an application: instrument LangGraph or LangChain, record evidence and decisions, write disclosure policies, handle human-in-the-loop, export to tracing backends, and troubleshoot |
| [`agxai-extend`](skills/agxai-extend/SKILL.md) | Extend agxai: write a `FrameworkInstrumentor` for another agent framework, or a `ProvenanceStore` for a database |

Install both with the [skills CLI](https://github.com/vercel-labs/skills),
which finds them through [`skills.sh.json`](../skills.sh.json):

```bash
npx skills add smuniharish/agxai                    # both
npx skills add smuniharish/agxai --skill agxai      # one
```

Other ways to install are in the
[documentation](https://agxai.readthedocs.io/en/latest/agent-skills/install/).

## Layout

Each skill follows the [Agent Skills specification](https://agentskills.io/specification):

```text
skills/<skill>/
├── SKILL.md      # frontmatter, workflow, rules, gotchas, links to every file
├── references/   # focused documents, one level deep, read only when a task needs them
├── scripts/      # offline checks with --help, --json, and meaningful exit codes
├── assets/       # templates the agent copies into the project, each with its tests
└── evals/        # evals.json, trigger_queries.json, and the input files they use
```

| Skill | Scripts | Assets |
| --- | --- | --- |
| `agxai` | `verify_setup.py`: core check offline; LangGraph too when installed (`--langgraph` to require it) | `test_disclosure_policy.py` |
| `agxai-extend` | `check_store.py`: runs `ProvenanceStoreContract` against any store factory | `instrumentor_template.py`, `test_instrumentor.py`, `store_template.py`, `test_store_contract.py` |

Every Agent Skills host reads the same directories, so there is no separate
copy for Claude Code, Codex, Cursor, or GitHub Copilot.

## Format

- `name` matches the directory. The `description` starts with "Use this skill
  when", names near misses, and hands over to the other skill where they
  meet.
- `license`, `compatibility`, and `metadata.version` are set. The version
  equals the `agxai` release the skill describes.
- `SKILL.md` stays short and links every reference with the task that needs
  it. Scripts and assets are referenced by paths relative to the skill
  directory.

## Maintaining the skills

When the public API or documented behavior changes:

1. Update the affected skill, and `metadata.version` in both skills with each
   release.
2. Check every changed snippet and claim against the code, tests, or
   documentation. Leave out anything that is not implemented.
3. Add or update an eval when the change affects what an agent should do.
4. Run the checks in [`validation/README.md`](validation/README.md).

The skills are covered by the repository's Apache License 2.0; see
[LICENSE](../LICENSE).
