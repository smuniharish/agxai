# Contributing

Contributions are welcome. The full guide, including how to propose changes and
what a pull request needs, is
[CONTRIBUTING.md](https://github.com/smuniharish/agxai/blob/master/CONTRIBUTING.md)
in the repository.

## Set up

```bash
git clone https://github.com/smuniharish/agxai.git
cd agxai
uv sync --all-extras --all-groups
```

## Check a change

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyrefly check
uv run pytest --cov=agxai --cov-branch
uv run zensical build --strict
uv run python scripts/check_site_links.py
node scripts/render-diagrams.mjs --check
```

All of these run in continuous integration on every pull request. See
[Testing](testing.md) for the test layout, property-based tests, and the live
suites.

## Guidelines

- Keep instrumentation observational: never change a graph's inputs, outputs,
  or exceptions.
- Record facts, never model reasoning. New capture must respect redaction,
  capture modes, and the capture policy.
- Treat the canonical models as a versioned contract. Within a schema version,
  changes are additive only; see
  [Canonical model](../architecture/canonical-model.md#compatibility).
- Update the documentation and the changelog with every user-visible change.
