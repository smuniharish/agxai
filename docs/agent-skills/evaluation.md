# Evaluation

A skill is only useful when an agent picks it up for the right task and then
gets that task right. agxai tests both, following the Agent Skills guidance on
[evaluating skills](https://agentskills.io/skill-creation/evaluating-skills).

## Checked on every change

`tests/skill` runs offline with the rest of the test suite in CI. For both
skills, it checks:

- **Format.** The `skills-ref` reference validator accepts the frontmatter.
  `name` matches the directory, the description starts with "Use this skill
  when", and `metadata.version` equals the agxai release.
- **Progressive disclosure.** `SKILL.md` stays under 500 lines and references
  are one level deep. Every reference is linked from `SKILL.md`, and every
  relative link resolves.
- **Bundled files.** `SKILL.md` mentions every script and asset, so the agent
  can find it.
- **Scripts.**
    - `verify_setup.py` passes, prints valid JSON with `--json`, and
      requires the same dependency ranges as the package.
    - `check_store.py` passes a correct store and names the promise a broken
      store violates. It exits with a distinct code when the store factory
      can't be loaded.
- **Templates.** The disclosure-policy, instrumentor and store templates pass
  their own tests.
- **Discovery.** The skills CLI finds both skills through `skills.sh.json`.

CI runs the setup check and the store contract again against the built wheel,
outside the development environment.

## Evaluated against real tasks

Each skill has an `evals/` folder:

| File | Contents |
| --- | --- |
| `evals.json` | Realistic tasks, each with input files, the expected result, and assertions a grader can verify |
| `trigger_queries.json` | 20 user requests: 10 that should load the skill and 10 near misses that shouldn't, split into training and validation sets |
| `files/` | The projects the tasks start from, such as a LangGraph graph without agxai or an in-house agent framework |

The tasks cover what agents get wrong without the skill:

| Skill | Tasks |
| --- | --- |
| `agxai` | Instrument a LangGraph graph and record the routing decision; withhold a credit score from customers but not analysts; fix `no active run` in a thread pool; ship events to Langfuse without losing them at shutdown |
| `agxai-extend` | Write an instrumentor for an in-house agent framework; write a SQLite store with contract tests; fix a store whose subclass query returns nothing |

The near-miss trigger queries keep the two skills apart: many near misses for
`agxai-extend` are tasks for `agxai`, and the reverse. A test checks that no
query is meant to load both.

To evaluate a change to a skill, run each task with and without the skill in
a fresh agent session. Grade the outputs against the assertions, and compare
pass rates, time, and tokens. The
[validation guide](https://github.com/smuniharish/agxai/blob/master/agxai-skills/validation/README.md)
describes the workflow and records the latest results.

## Reviewed against the source

Automated checks can't tell whether guidance is correct. Each snippet and
claim in a skill is reviewed against the code, tests and documentation it
describes, and anything without an implementation is left out. The
[validation guide](https://github.com/smuniharish/agxai/blob/master/agxai-skills/validation/README.md)
lists the source of truth for each area.
