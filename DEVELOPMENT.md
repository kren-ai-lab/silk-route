# Development

This guide covers local setup, day-to-day commands, and the code structure behind
BioSeqDownloader.

## Local Setup

BioSeqDownloader uses `uv` for environment management and `taskipy` for common developer
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
uv run bioseq-dl --help
```

## Project Layout

```text
bioseq_dl/
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
**never** run by the test suite or CI and refuses to do anything unless
`BIOSEQ_DL_CAPTURE=1` is set:

```bash
BIOSEQ_DL_CAPTURE=1 uv run python -m tests._capture.capture          # all APIs
BIOSEQ_DL_CAPTURE=1 uv run python -m tests._capture.capture rhea chebi
```

Each capture drives the real interface, so the request (URL, params, method,
body) matches production exactly, and records the raw HTTP body the interface
receives — the same payload the offline tests register with `responses`.

Credentialed / non-HTTP APIs are captured only when their env vars are present
(`BIOSEQ_DL_BIOGRID_API_KEY`, `BIOSEQ_DL_REFSEQ_EMAIL`,
`BIOSEQ_DL_BRENDA_EMAIL`/`BIOSEQ_DL_BRENDA_PASSWORD`); otherwise they are skipped
with a log line. These read from a gitignored `.env` at the repo root, loaded
automatically by the capture script.

Because fixtures are real bodies, re-capturing can change response shape and
require updating the affected test assertions — that is expected and the point:
the tests then reflect what the APIs actually return.

## Additional Context

For more architecture detail, see [AGENTS.md](AGENTS.md).
