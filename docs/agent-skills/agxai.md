# The agxai skill

The `agxai` skill teaches a coding agent to add agxai to an application and
work with it once it is there. It covers:

- instrumenting a LangGraph graph or a LangChain agent;
- recording evidence and decisions where the code decides;
- explaining each decision per audience under a disclosure policy;
- human-in-the-loop interrupts and approvals;
- exporting to LangSmith, Langfuse, OpenTelemetry, or a database;
- troubleshooting missing runs or explanations.

[:material-github: View on GitHub](https://github.com/smuniharish/agxai/tree/master/agxai-skills/skills/agxai){ .md-button }
[:material-download: Install](index.md#agentic-installation){ .md-button }

## When the agent uses it

The agent loads the skill when the task involves agxai or agent
explainability. Examples include recording why an agent decided something,
explaining decisions to developers, auditors, business users, or end users,
provenance, audit trails, and disclosure policies.

For an agent framework other than LangGraph, or a storage backend of your
own, it hands over to [agxai-extend](agxai-extend.md). It does not set up
generic tracing without explanations, and it never captures a model's
chain-of-thought.

## Workflow

The skill gives the agent a checklist to keep current while it works:

```text
- [ ] 1. verify_setup.py passes
- [ ] 2. One runtime per application and tenant boundary
- [ ] 3. The called graph or agent is instrumented
- [ ] 4. Evidence and decisions recorded where the code decides
- [ ] 5. Decisions explained, per audience, under a tested policy
- [ ] 6. Project tests and verify_setup.py pass again
```

The agent checks the environment before it changes anything and again when
it finishes. If audiences may see different things, it also adds the
disclosure-policy test template to the project.

## What's inside

```text
agxai/
├── SKILL.md                        # workflow, rules, gotchas
├── references/
│   ├── langgraph.md                # graphs, sync nodes, prebuilt agents, middleware
│   ├── human-in-the-loop.md        # interrupt and resume, approvals
│   ├── disclosure.md               # per-audience and LLM-phrased explanations
│   ├── exporting.md                # plugins, LangSmith, Langfuse, OpenTelemetry
│   ├── failure-modes.md            # FAIL_OPEN, FAIL_CLOSED, STRICT, manual runs
│   ├── api.md                      # imports, signatures, settings, records
│   └── troubleshooting.md          # symptoms, causes, fixes
├── scripts/
│   └── verify_setup.py             # offline environment and behavior check
├── assets/
│   └── test_disclosure_policy.py   # pytest template for a disclosure policy
└── evals/                          # test prompts, assertions, trigger queries
```

The agent always sees the skill's name and description. It reads `SKILL.md`
when a task matches, and opens a reference only when the task needs it, so a
simple task costs little context.

## The setup check

`scripts/verify_setup.py` runs offline in the project's Python environment.
It checks:

- the Python version, and the agxai and pydantic versions;
- LangGraph and LangChain, when the extra is installed;
- a full record, explain, and interrupt-and-resume cycle.

| Option | Effect |
| --- | --- |
| `--langgraph` | Fail when the `agxai[langgraph]` extra is missing |
| `--json` | Print one JSON object, `{"ok", "summary", "checks"}`, for the agent to parse |

It exits with `0` when every check passes and `1` otherwise. Sample output is
on the [install page](install.md#verify).

## Rules the agent follows

- **Observe, never steer.** Don't change graph inputs, outputs, state, or
  control flow to make recording work.
- **Record decisions explicitly** where the code decides. Never infer them
  from a trace, and never ask a model for its chain-of-thought.
- **Keep the policy boundary.** Never weaken a disclosure policy, redaction,
  or capture setting to make a test or an export pass.
- **Keep secrets out of records.** Reference people and documents by ID.
