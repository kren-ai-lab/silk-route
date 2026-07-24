# AGENTS.md

This file provides guidance to AI agents when working with code in this repository.

## Project Overview

**SilkRoute** is a Python library and CLI to download and integrate biological
data from many web APIs (UniProt, AlphaFold, BioGRID, KEGG, ChEMBL, Reactome, etc.).
It is part of the Kren AI Lab ecosystem alongside **Sylphy** (sequence encoders /
embeddings) and **Roxy** (classical descriptors).

Input: identifiers / queries per database. Output: parsed records as
`polars.DataFrame` / JSON / XML, with on-disk caching.

## Package Layout

```
silkroute/
  __init__.py             # public API (lazy via __getattr__) + __version__
  cli/
    main.py               # Typer root app
    interfaces/           # per-database CLI sub-apps
  constants/              # per-database constants + DBConfig instances (databases.py)
  core/
    interfaces/
      base.py             # BaseAPIInterface (fetch_single/fetch_batch/cache/parse)
      <db>.py             # one client per database, subclass of BaseAPIInterface
    utils/                # query builders, parsing helpers, BLAST
    workflow/             # multi-step download workflows
    cache.py, export.py, dbconfig.py, interfacesconfig.py
  logging/                # get_logger, unified setup
tests/                    # mirrors source tree, offline
examples/                 # standalone demo scripts
```

## Development Commands

This project uses `uv` and `taskipy`.

```bash
uv sync --extra dev --extra tests
uv run task test          # pytest -q
uv run task lint          # ruff check
uv run task lint-fix
uv run task format
uv run task ty            # ty check
uv run task pyrefly
uv run silkroute --help
```

## Architecture Notes

- New API clients inherit from `BaseAPIInterface` and declare their `DBConfig`
  (URL + cache/config dirs) from `constants/databases.py`.
- `fetch_single` / `fetch_batch` handle caching, optional parsing, and output
  format conversion (json / dataframe / xml). `parse` + `fetch` are abstract.
- Per-database field extraction is config-driven (YAML in the config dir).

## Key Invariants

- No import side effects: the top-level public API is lazy (`__getattr__`); importing
  `silkroute` must not pull heavy deps (e.g. `zeep` for BRENDA).
- Use `logging` (`get_logger`), never `print`.
- A `fetch` override returns the empty of its own success type (a list endpoint
  returns `[]`, an object endpoint `{}`); never `None`. The error-vs-empty reason
  is recorded in `metadata.failed` (`request_error` / `empty_result`), not the
  return value. (`chebi`/`pubchem` are genuinely method-polymorphic and return `{}`.)
- Tests run offline: HTTP is mocked (`responses`) behind `conftest` fixtures.
- Tests mirror the source layout.

## Active Work

A multi-phase refactor is in progress — see `REFACTOR_PLAN.md` (phase by phase,
review + commit between phases).
