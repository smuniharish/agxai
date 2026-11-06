# Validating the agxai skills

The `agxai` and `agxai-extend` skills are validated in three ways: automated
checks on every change, evaluations against real tasks, and a review of every
claim against its source.

## Automated checks

Run from the repository root:

```bash
uv run pytest tests/skill
uvx --from skills-ref agentskills validate agxai-skills/skills/agxai
uvx --from skills-ref agentskills validate agxai-skills/skills/agxai-extend
```

`tests/skill` runs offline in continuous integration. For both skills it
checks that:

- the frontmatter passes `skills-ref`. `name` matches the directory, the
  description starts with "Use this skill when", `license` is `Apache-2.0`,
  and `metadata.version` equals the package version;
- `SKILL.md` has fewer than 500 lines and links every reference;
  `references/` is one level deep, and every relative link resolves;
- `SKILL.md` mentions every bundled script and asset;
- `evals/evals.json` and `evals/trigger_queries.json` are well formed. The
  trigger queries are balanced, split into training and validation sets, and
  no query triggers both skills;
- the skills CLI discovers both skills through `skills.sh.json`.

It also runs the bundled code:

- `agxai/scripts/verify_setup.py` passes, with warnings treated as errors,
  prints valid JSON with `--json`, and requires the package's dependency
  ranges;
- `agxai/assets/test_disclosure_policy.py` passes;
- the `agxai-extend` instrumentor and store templates pass their tests;
- `agxai-extend/scripts/check_store.py` handles three cases:
    - it passes a correct store;
    - it names the promise a broken store violates;
    - it exits with code 2 for a factory it can't load.

CI also runs `verify_setup.py --langgraph` and `check_store.py` against the
built wheel.

## Evaluations

Each skill has an `evals/` folder, in the format described in
[Evaluating skills](https://agentskills.io/skill-creation/evaluating-skills):

- `evals.json`: realistic tasks with input files, an expected result, and
  assertions a grader can verify.
- `trigger_queries.json`: 10 requests that should load the skill and 10 near
  misses that shouldn't, split 12/8 into training and validation.

To evaluate a change:

1. Copy each task's input files into fresh workspaces, one with the skill and
   one without.
2. Run each task in a new agent session. The session without the skill can
   read the installed package but not the skill, the docs, or the
   repository's source.
3. Grade every assertion as passed or failed, with the evidence. Record time
   and tool calls.
4. Compare the two variants. Change the skill where the agent went wrong with
   it, or where it did no better than without it, then run the evaluation
   again.

Keep workspaces and benchmark files out of the repository.

### Latest results

agxai 1.0.1, one task per skill, run by a general-purpose coding agent:

| Task | Variant | Assertions | Tool calls | Time |
| --- | --- | --- | --- | --- |
| `agxai` #1: instrument a fraud-review graph and explain its routing | with skill | 6/6 | 5 | 64 s |
| | without skill | 6/6 | 8 | 105 s |
| `agxai-extend` #1: instrumentor and tests for an in-house framework | with skill | 6/6 | 12 | 121 s |
| | without skill | 6/6 | 14 | 166 s |

Findings:

- **No difference in assertions.** Both variants passed every assertion. A
  capable agent can get these tasks right by inspecting the installed
  package, so these assertions don't tell the variants apart.
- **Faster with the skills.** The agents finished about 30% faster, with
  fewer tool calls, and didn't have to discover the API by introspection.
- **A riskier design without `agxai-extend`.** The agent copied the agent
  with `dataclasses.replace` and patched its methods with
  `object.__setattr__`, instead of wrapping it.
- **A skipped step with `agxai`.** The agent ran `verify_setup.py` before the
  change but not after it. Step 6 of `SKILL.md` now says not to finish until
  the second run passes.

Next: add assertions that tell the variants apart. Candidates are
`verify_setup.py` passing after the change, a wrapper rather than a patched
object, and the store-contract tasks.

## Source review

Automated checks can't tell whether guidance is correct. For every change,
check each snippet and claim against its source:

| Claim area | Source of truth |
| --- | --- |
| Public imports, signatures, and the package version | [`src/agxai/__init__.py`](../../src/agxai/__init__.py), [`pyproject.toml`](../../pyproject.toml), and the [API reference](../../docs/api/index.md) |
| Runtime construction, recording, and explanations | [`src/agxai/runtime/runtime.py`](../../src/agxai/runtime/runtime.py) |
| Configuration and failure behavior | [`src/agxai/config.py`](../../src/agxai/config.py), [configuration](../../docs/getting-started/configuration.md), and [failure modes](../../docs/guide/how-to/failure-modes.md) |
| Entry points, interrupts, and checkpoints | [`src/agxai/integrations/langgraph/graph.py`](../../src/agxai/integrations/langgraph/graph.py), the [LangGraph integration](../../docs/integrations/langgraph.md), and [interrupts](../../docs/guide/how-to/interrupts.md) |
| Framework instrumentors | [`src/agxai/integrations/base.py`](../../src/agxai/integrations/base.py), [custom frameworks](../../docs/integrations/custom-frameworks.md), and [`examples/custom_framework.py`](../../examples/custom_framework.py) |
| Storage backends and the store contract | [`src/agxai/storage/`](../../src/agxai/storage/), [`src/agxai/testing.py`](../../src/agxai/testing.py), [storage](../../docs/architecture/storage.md), and [`examples/postgres_store.py`](../../examples/postgres_store.py) |
| Disclosure and security | [disclosure policies](../../docs/guide/how-to/disclosure-policies.md) and [security](../../docs/security.md) |
| Working patterns | [`examples/`](../../examples/) and [`tests/`](../../tests/) |

If a behavior has no implementation, test, or documentation, leave it out of
the skill rather than infer it.

## Routing matrix

Check that the descriptions send each task to the right skill:

| Task | Skill | Route | Avoids |
| --- | --- | --- | --- |
| "Add explainability to my LangGraph agent." | `agxai` | Instrument the compiled graph; record evidence and decisions in nodes. | Changing graph inputs, outputs, or control flow. |
| "Explain why the agent chose this action." | `agxai` | `record_decision` where the choice is made, then `collect_runs` and `explain_decision`. | Inferring reasoning from a trace, or asking for chain-of-thought. |
| "Show customers a reason but not our risk score." | `agxai` | A `PolicyProvider` and the disclosure-policy test template. | Weakening the policy to make a test pass. |
| "Record the reviewer's approval and the resumed run." | `agxai` | A checkpointer and `thread_id`; `record_human_interaction` for outside approvals. | Calling `record_checkpoint` for instrumented checkpointed graphs. |
| "Send our events to Langfuse and OpenTelemetry." | `agxai` | An observability adapter, and `close()` at shutdown. | Credentials in records or code. |
| "Write an agxai integration for our CrewAI crew." | `agxai-extend` | The instrumentor template and its tests. | Using `XAIRuntime.instrument()` for a non-LangGraph agent. |
| "Store agxai records in PostgreSQL." | `agxai-extend` | The store template, the contract tests, and `check_store.py`. | Skipping or weakening a contract test. |
| "Build a new agent framework that logs chain-of-thought." | Neither | Not this package's purpose. | Inventing capabilities. |
