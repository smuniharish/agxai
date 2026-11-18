# Contributing

Thank you for improving `agxai`. Contributions should keep its focus:
an explainability layer for AI agents, not an agent runtime or an observability
platform.

Keep the core framework-neutral. Framework dependencies belong in optional
extras; integrations extend `FrameworkInstrumentor` and use the runtime's
public recording methods. The bundled LangGraph/LangChain integration is
installed with `agxai[langgraph]`.

## Before opening a change

1. Read the [architecture overview](docs/architecture/index.md).
2. Open an issue first for changes to the public API, the canonical schema,
   disclosure behavior, or an integration.
3. Keep each change focused, with tests and documentation for anything a user
   can observe.

## Development setup

Python 3.12 or later and [uv](https://docs.astral.sh/uv/) are required.

```bash
uv sync --all-extras --all-groups
uv run ruff check .
uv run ruff format --check .
uv run pyrefly check
uv run pytest --cov=agxai --cov-branch
```

The default test run needs no services or API keys, and coverage is kept at
100%. Live suites for PostgreSQL, OpenTelemetry, Langfuse, and LLM endpoints
run when their environment variables are set; see
[Testing](docs/development/testing.md).

Never commit credentials, local environments, or generated reports.

## Documentation and diagrams

### Architecture disclosure

Public documentation should explain the package's purpose, component
responsibilities, supported integrations, public interfaces, configuration,
extension points, and user-facing behavior. Keep examples, compatibility
limits, error handling, security guarantees, and their limitations explicit.

Prefer conceptual diagrams and concise explanations over unnecessary internal
execution sequences, routing rules, scheduling details, or optimization
blueprints. Check diagrams against the actual code and review their Mermaid
source, rendered images, surrounding text, examples, and generated API
docstrings together. Do not remove information developers need to use,
extend, or troubleshoot the package.

Flag potentially valuable algorithms, unpublished designs, and
security-sensitive details for maintainer and, where appropriate, legal review
before publication. Do not place confidential material elsewhere in the
public repository. Report suspected secrets or vulnerabilities privately as
described in [SECURITY.md](SECURITY.md).

Public source code and Git history may already reveal details omitted from
documentation; editing documentation does not make them secret. Copyright,
trade secrets, and patents are distinct matters for appropriate review. This
guidance does not change the Apache-2.0 license or restrict independent
implementations.

### Building documentation

```bash
uv run zensical build --strict
uv run python scripts/check_site_links.py
```

Diagrams are Mermaid sources under [`diagrams/`](diagrams), rendered to PNG
with Mermaid CLI 12.2.0. Install it globally; it needs Node.js 22.13 or later.
`--allow-scripts=puppeteer` lets Puppeteer download the headless browser the
CLI renders with:

```bash
npm install --global --allow-scripts=puppeteer @mermaid-js/mermaid-cli@12.2.0
node scripts/render-diagrams.mjs
node scripts/render-diagrams.mjs --check
```

Commit a changed diagram source together with its rendered image and the
updated `docs/assets/diagrams/manifest.json`.

## Pull requests

- Describe the user-visible impact, including any effect on what is captured,
  stored, exported, or disclosed.
- Add or update tests for every behavior change.
- Update the affected pages under [`docs/`](docs) and the
  [changelog](CHANGELOG.md).
- Make sure formatting, lint, type checks, tests, the strict docs build, and
  the diagram check pass.

## Releases

Releases follow [semantic versioning](https://semver.org/). Publishing is a
manual maintainer action; GitHub Actions never uploads distributions to PyPI.

1. Set the version in `pyproject.toml` and `metadata.version` in both Agent
   Skills, `agxai-skills/skills/agxai/SKILL.md` and
   `agxai-skills/skills/agxai-extend/SKILL.md`, then run `uv lock`.
2. Move the changelog entries under a heading with the version and date.
3. Build and inspect distributions locally:

   ```bash
   version="$(uv version --short)"
   uv build --no-sources --out-dir "dist/$version"
   uvx twine check --strict "dist/$version"/*
   python -m tarfile -l "dist/$version/agxai-$version.tar.gz"
   python -c 'import sys, zipfile; z = zipfile.ZipFile(sys.argv[1]); print(z.read(next(n for n in z.namelist() if n.endswith(".dist-info/METADATA"))).decode())' "dist/$version/agxai-$version-py3-none-any.whl"
   ```

   Inspect the archive contents and wheel metadata before publishing. Use a
   clean version-specific output directory so older artifacts are not uploaded.
4. Merge to `master`.
5. Publish manually from the maintainer's machine using a short-lived or
   otherwise appropriately protected PyPI token. For example, set
   `UV_PUBLISH_TOKEN` in the local environment and run
   `uv publish "dist/$version"/*`. Never commit the token or configure it as a
   GitHub Actions secret.
6. Create the GitHub release manually with a `v`-prefixed tag such as
   `v1.0.0`; attach the inspected distributions if desired.

The [release workflow](.github/workflows/release.yml) only checks the tag,
builds the distributions, and uploads them as a GitHub Actions artifact. It
has no PyPI publishing job, publishing credentials, or Trusted Publishing
permissions.

## Security reports

Do not report vulnerabilities in public issues. Follow [SECURITY.md](SECURITY.md).
