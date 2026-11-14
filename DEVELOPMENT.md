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

## Incremental UniProt acquisitions

The opt-in path is implemented by `UniprotInterface.iter_search_pages()`,
`MainWorkflow.run_incremental_uniprot()`, and
`core/workflow/incremental_uniprot.py`. It follows UniProt cursor links exactly,
retries only the current page, parses one page at a time, and passes at most
2,000 parsed records at once to a persistent PyArrow `ParquetWriter`. The
normal HTTP page size is 500, independently of the final partition size.
PyArrow is a runtime dependency but is imported only for partitioned runs.

Run with a descriptor whose `dataset.modality` is `protein`, `dataset.mode` is
`query_first`, `export.format` is `parquet`, and `execution.enrich` is `false`:

```bash
silkroute workflow run --config queries/Q01_DNA_POS_CURATED.yml --write-mode partitioned --batch-size 5000000
```

`--write-mode single` remains the default and uses the legacy aggregate path
and one result file; it does not have bounded record memory. `--batch-size`
means rows per final Parquet file, not rows held in memory. The same options
work with CLI-only workflows when `--no-enrich` and `--export-format parquet`
are supplied. The CLI options are not YAML keys, so `workflow-v1` is unchanged.
Partitioned output is a set of final
`uniprot_results_part-000001.parquet` files, plus
`uniprot_incremental_checkpoint.json`, `metadata.json`, and `run_summary.yml`.
The writer appends many small row groups to one `.parquet.incomplete` file,
closes and validates its row count and schema, checksums it, then atomically
publishes the final `.parquet` part. The provenance sidecar is beside the output
directory. Nested annotations are JSON strings (decode with `json.loads`),
absent values remain Parquet nulls, and `annotation_score` uses Float64 to
retain fractional values. The record key column defaults to `record_id` to
avoid colliding with UniProt's biological `id` field.

The checkpoint records fetched pages, acquired and saved records, per-field
coverage of saved rows, part paths, sizes, SHA-256 checksums, total-count
validation, and status. If UniProt supplies a numeric total count, the run
checks it at the end and rejects a changed header or mismatch. A missing total
cannot prove completeness, and a stable count cannot prove an unchanged remote
snapshot. On a handled request failure, valid buffered rows may be finalized
as a part while the acquisition remains `failed`. A write failure discards the
unfinished part. An abrupt process interruption may leave a `.parquet.incomplete`
file; it is never listed as final output or claimed recoverable. Automatic
resume is unavailable. Every new run requires a fresh, empty output directory.

`--incremental --chunk-size N` is a deprecated compatibility alias: `N` still
means rows per part, and its small page and buffer limits are retained. Remove
the alias only in a later release. The `--batch-size` on `search uniprot by-ids`
is a different option: it controls how many IDs are submitted per mapping batch.

Use the offline tests in
`tests/core/workflow/test_incremental_uniprot.py` and
`tests/cli/test_incremental_workflow.py` to check pagination, partial failure,
schema consistency, CLI reporting, and synthetic memory scaling.

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

- HTTP interactions are mocked (`niquests_mock`), isolated behind `conftest` fixtures.
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
`niquests_mock`: BRENDA (zeep SOAP `Client`), RefSeq (`Bio.Entrez`), BioGRID (API key
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
receives — the same payload the offline tests register with `niquests_mock`.

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
