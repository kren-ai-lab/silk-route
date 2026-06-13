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

## Additional Context

For more architecture detail, see [AGENTS.md](AGENTS.md).
