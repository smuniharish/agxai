# agxai Agent Skill

This directory distributes the `agxai` Agent Skill: instructions,
references, a setup check, and a test template that teach coding agents to
integrate the `agxai` package correctly. It is not part of the Python
package and adds no runtime behavior.

It covers the framework-neutral core, optional `agxai[langgraph]` support,
and extending other frameworks through the `FrameworkInstrumentor` ABC.

## Layout

| Path | Contents |
| --- | --- |
| [`skills/agxai/SKILL.md`](skills/agxai/SKILL.md) | When to use the skill, the core workflow, and the rules an integration follows |
| [`skills/agxai/references/`](skills/agxai/references/) | `API.md`, `RECIPES.md`, and `TROUBLESHOOTING.md`, read when a task needs them |
| [`skills/agxai/scripts/verify_setup.py`](skills/agxai/scripts/verify_setup.py) | Offline core check; also checks LangGraph when installed (`--langgraph` to require it) |
| [`skills/agxai/assets/test_disclosure_policy.py`](skills/agxai/assets/test_disclosure_policy.py) | A pytest template for testing an application's disclosure policy |
| [`validation/`](validation/) | How the skill is validated and reviewed |

## Format

The skill follows the [Agent Skills specification](https://agentskills.io/specification):

- The `SKILL.md` frontmatter has `name`, which matches the directory, and
  `description`, `license`, `compatibility`, and `metadata.version`. The
  version equals the `agxai` release the skill describes.
- `SKILL.md` stays short. Details live in `references/`, one level deep, so an
  agent loads them only when a task needs them.
- Scripts and assets are referenced by paths relative to the skill directory.

Every Agent Skills host reads the same directory, so there is no separate copy
for Claude Code, Codex, Cursor, or GitHub Copilot. Installation is described in
the [documentation](https://agxai.readthedocs.io/en/latest/agent-skills/).

## Maintaining the skill

When the public API or documented behavior changes:

1. Update the affected part of the skill, and `metadata.version` with each
   release.
2. Check every changed snippet and claim against the code, tests, or
   documentation. Leave out anything that is not implemented.
3. Run the checks in [`validation/README.md`](validation/README.md).

The skill is covered by the repository's Apache License 2.0; see
[LICENSE](../LICENSE).
