# Development

This guide covers local setup, day-to-day commands, and the code structure behind
SilkRoute.

## Local Setup

SilkRoute uses `uv` for environment management and `taskipy` for common developer
commands.

Install development dependencies:

```bash
uv sync --extra dev --extra tests
```

Editable install with `pip` also works:

```bash
pip install -e ".[dev,tests]"
```

## Common Commands

Run tests:

```bash
uv run task test
uv run task test-v
uv run task test-cov
uv run pytest tests/core/interfaces/test_reactome.py -v
```

Lint, format, and type-check:

```bash
uv run task lint
uv run task lint-fix
uv run task format
uv run task sort-imports
uv run task ty
uv run task pyrefly
```

Build the package:

```bash
uv build
```

Smoke-test the CLI:

```bash
uv run silkroute --help
```

## Project Layout

```text
silkroute/
├── cli/                  # Typer commands (root in cli/main.py)
│   └── interfaces/       # Per-database CLI sub-apps
├── constants/            # Per-database constants and DBConfig values
├── core/
│   ├── interfaces/       # BaseAPIInterface + per-database API clients
│   ├── utils/            # Shared helpers (query builders, parsing, BLAST)
│   ├── workflow/         # Multi-step download workflows
│   ├── cache.py          # Cache helpers
│   └── export.py         # Output/export helpers
├── logging/              # Unified logging setup
└── __init__.py           # Public API (lazy) + __version__

tests/                    # Mirrors the source tree
examples/                 # Scripts for manual exploration
```

## Design Rules

- Avoid side effects on import (public top-level API is lazy via `__getattr__`).
- Use logging instead of `print`.
- New interfaces inherit from `BaseAPIInterface` and declare their `DBConfig`.
- Keep the public API small and explicit.

## Testing Notes

The test suite is designed to run offline.

- HTTP interactions are mocked (`responses`), isolated behind `conftest` fixtures.
- Test layout mirrors the source layout.
- New features should ship with focused unit tests and CLI coverage when applicable.

### Offline interface suite and fixtures

Every API interface has an offline test module under
`tests/core/interfaces/test_<api>.py`. Each one replays a frozen API response
from `tests/fixtures/<api>/<case>.json` and asserts three things:

- **fetch** builds the right URL/params and unwraps the body as expected;
- **parse** returns the expected keys/shape (not exact values);
- **fetch_single** round-trips through the cache (1 request on the first call,
  0 on the second).

Non-HTTP / credentialed clients are mocked at the client boundary instead of via
`responses`: BRENDA (zeep SOAP `Client`), RefSeq (`Bio.Entrez`), BioGRID (API key
supplied explicitly), and the standalone UniProt id-mapping flow
(submit → status → details → results).

Fixtures are loaded with the helpers in `tests/_helpers.py`
(`load_fixture` / `load_fixture_text`). They are committed despite the global
`*.json` gitignore rule thanks to the `!tests/**/*.json` exception.

### Regenerating fixtures (network-gated)

`tests/_capture/capture.py` regenerates the fixtures from the real APIs. It is
**never** run by the test suite (and never on push / pull request) and refuses to
do anything unless `SILKROUTE_CAPTURE=1` is set:

```bash
SILKROUTE_CAPTURE=1 uv run python -m tests._capture.capture          # all APIs
SILKROUTE_CAPTURE=1 uv run python -m tests._capture.capture rhea chebi
```

Each capture drives the real interface, so the request (URL, params, method,
body) matches production exactly, and records the raw HTTP body the interface
receives — the same payload the offline tests register with `responses`.

Credentialed / non-HTTP APIs are captured only when their env vars are present
(`SILKROUTE_BIOGRID_API_KEY`, `SILKROUTE_REFSEQ_EMAIL`,
`SILKROUTE_BRENDA_EMAIL`/`SILKROUTE_BRENDA_PASSWORD`); otherwise they are skipped
with a log line. These read from a gitignored `.env` at the repo root, loaded
automatically by the capture script.

Because fixtures are real bodies, re-capturing can change response shape and
require updating the affected test assertions — that is expected and the point:
the tests then reflect what the APIs actually return.

### Scheduled re-capture (`refresh-fixtures` workflow)

`.github/workflows/refresh-fixtures.yml` runs the capture script on the 1st and
15th of every month at 06:00 UTC (also on `workflow_dispatch`, with an optional
space-separated `apis` input). It always checks out and targets `dev`, never `main`
— the file only lives on the default branch because that is where GitHub fires
`schedule` from.

What happens next depends on the offline suite, run in-job against the fresh
fixtures:

| fixtures changed | `pytest -q` | outcome |
| --- | --- | --- |
| no | not run | nothing; job green |
| yes | passes | committed straight to `dev` |
| yes | fails | pushed to `chore/refresh-fixtures`, PR opened against `dev` |

So a PR appearing means an API changed shape and the assertions need reconciling:
fix them on the branch, and re-run `REGEN_FIELD_BASELINE=1 uv run pytest` if the
field-coverage baseline moved. The PR body carries the capture log and the tail of
the failing run. A re-run reuses the same branch and PR rather than stacking new
ones.

The job itself goes red only when the capture script exits non-zero, so a dead or
renamed endpoint is visible in the Actions tab. That is independent of the commit
decision: a partial capture whose fixtures still pass is committed to `dev` (the
APIs that answered gave valid bodies) *and* leaves the run red for the one that
did not.

Credentialed captures need repository secrets with the same names as the env vars
above (`SILKROUTE_BIOGRID_API_KEY`, `SILKROUTE_REFSEQ_EMAIL`,
`SILKROUTE_BRENDA_EMAIL`, `SILKROUTE_BRENDA_PASSWORD`); without them those three
APIs skip themselves and their fixtures stay frozen.

## Releasing

`.github/workflows/publish-pypi.yml` builds with `uv build` and publishes to PyPI
via [trusted publishing](https://docs.pypi.org/trusted-publishers/) (OIDC, no API
token stored in the repo). It triggers on any `v*` tag, and on `workflow_dispatch`
for a build-only dry run — the `publish` job is gated on `startsWith(github.ref,
'refs/tags/v')`, so a manual run only produces artifacts.

The version is dynamic: hatch reads `__version__` from `silkroute/__init__.py`. To
cut a release, bump it, commit, then tag the same number:

```bash
git tag v0.2.0 && git push origin v0.2.0
```

The build job refuses to continue when the tag and `__version__` disagree, because
a filename on PyPI cannot be reused after upload.

One-time setup on PyPI: add a trusted publisher for project `silkroute` with owner
`kren-ai-lab`, repository `silk-route`, workflow `publish-pypi.yml`, environment
`pypi`. The `pypi` GitHub environment is where any release approvals or reviewers
would go.

## Additional Context

For more architecture detail, see [AGENTS.md](AGENTS.md).
