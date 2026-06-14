# Refactor Plan — BioSeqDownloader

Quality improvement plan: align with the group stack (Sylphy / Roxy), fix correctness
bugs, and reduce structural repetition.

**Execution mode:** one phase at a time → review → commit → next phase.
Each phase lists concrete steps, files touched, and acceptance criteria.

## Decisions made

| Topic        | Decision                                                                                              |
|--------------|-------------------------------------------------------------------------------------------------------|
| Tooling      | Adopt group stack: `uv` + `taskipy` + `ruff` + `ty` + `pyrefly` + `pytest`/`pytest-cov` + `prek`      |
| HTTP mock    | `responses` for now, isolated in `conftest` fixtures. Migrates with niquests in Phase 4               |
| HTTP client  | `requests` for now → `niquests` in Phase 4 (deferred)                                                 |
| License      | Migrate GPLv2 → **GPLv3** (align with group)                                                          |
| Versioning   | Dynamic via hatchling from `__version__` in `bioseq_dl/__init__.py`                                   |
| Data backend | `pandas` for now → **`polars`** in Phase 5 (ecosystem consistency)                                    |

## Group references

- `/home/dxh/david/roxy` — HTTP/descriptors lib, closest in structure.
- `/home/dxh/david/sylphy` — offline test pattern with self-contained fakes.
- Shared conventions: ruff `select=["ALL"]` line 110 py312; ignores
  `COM812,D203,D213,N802,N803,N806,PLR0913`; per-file-ignores for `cli/`,
  `tests/`, `examples/`; tasks `format/lint/lint-fix/test/test-v/test-cov/ty/pyrefly`;
  tests mirror the source tree; offline; `AGENTS.md` + `CLAUDE.md` symlink; `DEVELOPMENT.md`.

---

## Phase 0 — Bootstrap group stack

**Goal:** bring the repo to the same tooling/structure as Roxy/Sylphy, without touching
business logic. Every later commit already passes `ruff`/`ty`.

### 0.1 — `pyproject.toml`

- [ ] Add extras `dev` (`pyrefly`, `ruff`, `taskipy`, `ty`) and `tests`
  (`pytest>=9`, `pytest-cov>=7`, `responses`).
- [ ] `[tool.ruff]` block: `line-length = 110`, `target-version = "py312"`.
- [ ] `[tool.ruff.lint]` `select = ["ALL"]`, `ignore` = group set.
- [ ] `[tool.ruff.lint.per-file-ignores]` for `bioseq_dl/cli/*`
  (`B008,FBT001,FBT002,FBT003,TC003`), `tests/*`, `examples/*` (copy from roxy).
- [ ] `[tool.taskipy.tasks]`: `sort-imports/format/lint/lint-fix/test/test-v/test-cov/ty/pyrefly`
  pointing to `bioseq_dl/ tests/ examples/`.
- [ ] Dynamic versioning: `[tool.hatch.version]` `path = "bioseq_dl/__init__.py"`,
  remove static `version = "0.1.0"`, add `dynamic = ["version"]`.
- [ ] License classifier GPLv2 → GPLv3; `license = "GPL-3.0-only"`.

### 0.2 — License

- [ ] Copy GPLv3 `LICENSE` from `roxy/LICENSE` (no LICENSE file currently exists).

### 0.3 — Version

- [ ] Add `__version__ = "0.1.0"` at the top of `bioseq_dl/__init__.py`.

### 0.4 — `.gitignore` ⚠️ critical

- [ ] Global rules `*.json` and `*.csv` would exclude test fixtures. Add
  exceptions: `!tests/**/*.json`, `!tests/**/*.csv` (and review `examples/data`).

### 0.5 — Lazy imports in `__init__.py`

- [ ] Currently imports all 21 interfaces eagerly → `import bioseq_dl` loads `zeep`/SOAP
  and everything. Group rule: no import side-effects. Implement `__getattr__` (PEP 562)
  lazy loading, keeping `__all__`. Verify `from bioseq_dl import XInterface` still works.

### 0.6 — Docs and meta

- [ ] `DEVELOPMENT.md` (adapt from sylphy: uv setup, task commands, layout, testing notes).
- [ ] `AGENTS.md` + `CLAUDE.md -> AGENTS.md` symlink (overview, layout, commands, invariants).
- [ ] `prek.toml` (hooks: check-yaml/toml, eof-fixer, trailing-whitespace + local format/lint/ty/pyrefly).
- [ ] `.github/workflows/` CI (lint + test, copy from roxy/sylphy).

### 0.7 — `tests/` skeleton

- [ ] `tests/__init__.py`, root `tests/conftest.py`.
- [ ] Mirror structure: `tests/core/`, `tests/cli/`, `tests/core/interfaces/` with `__init__.py`.

**Phase 0 acceptance criteria**

- `uv sync --extra dev --extra tests` ok.
- `uv run task lint` runs (may report findings; not fixed yet).
- `uv run pytest -q` collects and runs (0 or trivial tests) with no collection error.
- `import bioseq_dl` does not import `zeep`/heavy modules (verifiable).
- `uv run bioseq-dl --help` ok.

**Review + commit:** `chore: adopt group dev stack (ruff/ty/pyrefly/pytest, GPLv3, dynamic version)`

---

## Phase 1 — Cosmetics + lint alignment

**Goal:** cleanup with no behavior change. Done before the fixes so the bug diffs stay clean.

### 1.1 — Typos and duplicates

- [ ] `base.py:110` `retrues` → `retries`.
- [ ] `base.py` duplicate `from typing import` (lines 6 and 13).

### 1.2 — Dead code

- [ ] Commented-out blocks in `base.py` (`_filter_dict_keys` 191-196, `fetch_single` 818-824, etc.).
- [ ] `_child_db_base.py`: template with `raise NotImplementedError` + unreachable code
  and non-existent `YOUR_DATABASE` import. Move to `examples/` as a template or delete.

### 1.3 — Logging

- [ ] Replace `print()` in `core/` (~16) with `log.*`. Includes
  `base.py:497` `print(f"Joined ...")`.

### 1.4 — Lint/format per module

- [ ] `uv run task format` + `lint-fix` incrementally per subpackage, checking that
  no auto-fix changes semantics (watch out for `B`, `SIM`, `RUF`).
- [ ] For non-trivial findings: fix or add a justified ignore, no mass silencing.

**Phase 1 acceptance criteria**

- `uv run task lint` clean (or justified ignores documented).
- `uv run task ty` and `pyrefly` with no new regressions.
- No observable behavior change.

**Review + commit:** `style: cleanup dead code, typos, print→logger, ruff pass`

---

## Phase 2 — Correctness bugs (TDD)

**Goal:** fix real bugs. For each: a test expressing the **desired** behavior (fails on
current code) → fix → test passes.

### 2.1 — `core/exceptions.py` (foundation for the rest)

- [ ] Hierarchy roxy-style: `BioSeqError` > `APIError` > `{RequestError, ParseError, ConfigError}`.
- [ ] Replace silent `return {}` where "no data" vs "failed" must be distinguished.
  Keep graceful degradation where intentional, but record it in metadata
  (`failed_ids`) consistently.

### 2.2 — CLI: tuple treated as DataFrame

- [ ] Bug: `result = interface.fetch_single(...)` returns `(data, metadata)`, then
  `result.to_csv(...)` → `AttributeError`. Affects chebi, chembl, panther, pubchem,
  reactome and more.
- [ ] Create helper `cli/_shared.py:save_or_print(data, output)` (roxy `_shared.py` pattern)
  that unpacks, type-checks, and saves/prints.
- [ ] Replace the repeated pattern across all `cli/interfaces/*`.
- [ ] CLI tests with `typer.testing.CliRunner` + `responses`.

### 2.3 — `cli/interfaces/reactome.py:16`

- [ ] Bug: `{"id": identifier.strip() for identifier in id.split(",")}` → constant key,
  keeps only the last id. Decide the contract (single id, or list) and fix.

### 2.4 — `get_nested` (`base_auxiliary_methods.py`)

- [ ] Bug A: collapses single-element lists to a scalar (lines 42-45) → inconsistent shape.
- [ ] Bug B: ignores `sep` in recursion (hardcodes `"."`).
- [ ] ⚠️ Changes downstream data shape → cover with broad tests before touching.

### 2.5 — `fetch_batch` partial cache

- [ ] Bug: when a query has several subqueries and only some are cached,
  `index_query_map[i] = query` marks the whole query for refetch → duplicates +
  unnecessary refetch. Fix to fetch only the missing subqueries.

### 2.6 — `reactome.validate_query`

- [ ] Returns `{}` on error but the caller ignores the return and proceeds with an
  invalid query. Make it raise `ParseError`/`RequestError` or abort.

### 2.7 — Findings surfaced by ruff in Phase 1 (currently in the transition ignore-list)

Remove each rule from the `pyproject.toml` ignore-list as it gets fixed.

- [ ] `interpro.query_usage` references undefined `data_types` / `db_types` /
  `entry_integration_types` → `NameError` when called (ruff `F821`, pyrefly error).
- [ ] `alphafold.fetch_single`: `new_result = {}` assigned but never used (`F841`) —
  check whether structure-download result was meant to be returned.
- [ ] `B026` star-arg after keyword arg in several `fetch`/`fetch_single` calls
  (alphafold, base, genontology, pride, pubchem) — e.g.
  `super().fetch_single(query, parse=parse, *args, **kwargs)`. Error-prone ordering.
- [ ] `B904` raise-from in except blocks (cli + base + utils) — chain exceptions once
  `core/exceptions.py` exists (2.1).
- [ ] `data = data` no-op self-assignment in ~13 interface `parse` methods (`PLW0127`) —
  fold into the Phase 3 dedup (likely `if not isinstance(...): return {}`).

**Phase 2 acceptance criteria**

- New tests red before / green after for each bug.
- `uv run task test` green, coverage on the fixed paths.

**Review + commit:** one commit per bug or logically grouped
(`fix: ...`), reviewing the diff before each.

---

## Phase 3 — Comprehensive offline test suite

**Goal:** lock the current behavior of **every** API interface before the
structural refactor. Tests run fully offline; fixtures are captured **once** from
the real APIs, frozen on disk, and replayed via `responses` (or a client-boundary
mock for non-HTTP clients).

### Decisions (confirmed)

- **Capture mechanism:** a **gated capture script** under `tests/_capture/`,
  enabled by an env var (`BIOSEQ_CAPTURE=1`). Run manually to (re)generate
  `tests/fixtures/<api>/*.json`. The default `uv run task test` never touches the
  network.
- **Hard APIs (auth / non-HTTP):** **mock at the client boundary.** BRENDA (SOAP /
  `zeep`) → mock the zeep client; keyed / multi-step APIs (BioGRID key, UniProt
  id-mapping) → capture with env creds when available, otherwise hand-craft a
  minimal fixture and replay.
- **Assertion depth:** **URL + parse shape + cache.** Per interface: assert the
  request URL/params are built correctly, `parse()` returns the expected
  keys/shape (columns/types, not exact values), and `fetch_single` round-trips
  through the cache (1 request first call, 0 on the second).

### 3.1 — Layout

```
tests/
  fixtures/<api>/<case>.json     # frozen raw API responses (committed)
  _capture/
    __init__.py
    capture.py                   # env-gated; per-api capture funcs -> fixtures/
  core/interfaces/test_<api>.py  # offline tests replaying fixtures
```

- Add a `load_fixture(api, case)` helper (e.g. `tests/_helpers.py`) and reuse the
  existing `mocked_responses` conftest fixture.
- `.gitignore` already whitelists `tests/**/*.json` (Phase 0), so fixtures commit.

### 3.2 — Capture script (`tests/_capture/capture.py`)

- No-op unless `BIOSEQ_CAPTURE=1`. Reads optional creds from env
  (`BIOGRID_KEY`, `BRENDA_EMAIL`, `BRENDA_PASSWORD`, …); skips APIs whose creds
  are missing and logs which were skipped.
- One small, representative request per interface method; writes pretty JSON to
  `tests/fixtures/<api>/<case>.json`.
- Documented in `DEVELOPMENT.md`; never invoked by CI.

### 3.3 — Per-interface offline tests

For each interface, a `test_<api>.py` that asserts (the agreed depth):

- **fetch():** register the frozen body with `responses`; assert the URL and
  query params the client builds (responses records the call), and that the raw
  return matches the fixture.
- **parse():** feed the fixture through `parse()`; assert output keys/shape
  (DataFrame columns / dict keys / list element shape) — not exact values.
- **fetch_single():** round-trip — first call performs 1 request and writes the
  cache; second call serves from cache with 0 requests.
- Where relevant, one `fetch_batch` test (multi-id, partial-cache already covered
  in Phase 2).

### 3.4 — Client-boundary mocks (hard APIs)

- **BRENDA:** monkeypatch the `zeep` client/service so methods return a frozen
  dict captured from a real call; assert `parse()` shape. No real SOAP in tests.
- **BioGRID:** capture with `BIOGRID_KEY` when present; offline test replays the
  frozen body via `responses` (no key needed offline).
- **UniProt:** id-mapping is multi-step (submit → poll → results); capture/craft
  the response sequence and replay them in order with `responses`.

### 3.5 — Coverage checklist (one test module each)

alphafold · biodbnet · biogrid · brenda · chebi · chembl · genontology ·
interpro · kegg · panther · pathwaycommons · pride · proteindatabank(pdb) ·
pubchem · reactome · refseq · rhea · stringdb · uniprot (+ crossref).

**Phase 3 acceptance criteria**

- `uv run task test` fully offline and green; no network in the default run.
- Every interface module has fetch / parse / cache coverage.
- Capture script reproduces the committed fixtures and is documented.

**Review + commit:** grouped per interface or small batches
(`test: offline suite for <api>`), reviewing each batch.

---

## Phase 4 — Structural refactor

**Goal:** reduce repetition with the Phase 2 + Phase 3 test net as regression safety.

### 3.1 — Duplicate `__init__` across ~18 subclasses

- [ ] Pattern `if cache_dir: abspath else: DB.CACHE_DIR` identical in all of them.
- [ ] Move to `BaseAPIInterface`: subclass declares `DB_CONFIG: ClassVar[DBConfig] = KEGG`,
  base resolves cache_dir/config_dir from it. Aligns with "factory entry points" rule.

### 3.2 — Split `base.py` (1102 lines)

- [ ] `_empty_metadata()` factory (13-key dict repeated in fetch_single/fetch_batch).
- [ ] `_build_data_info(df)` helper (columns block repeated 3+ times).
- [ ] Extract "check cache → fetch remaining → split → save" into a named method.
- [ ] Simplify `_maybe_parse` + format conversion (dedup vs the multi-query branch).

### 3.3 — Unify config

- [ ] `BaseAPIInterface._load_all_configs` and `ConfigLoader` (`interfacesconfig.py`) do
  the same thing (load YAML from a dir). Unify into one.

### 3.4 — UniProt inherits from `BaseAPIInterface` (last, highest risk)

- [ ] Currently inherits from `UniprotBase(object)`: own session/retries, does not share
  cache/fetch_single/fetch_batch/METHODS.
- [ ] Refactor to inherit from `BaseAPIInterface`, moving id-mapping into specialized methods.
- [ ] Solid test coverage before touching.

**Phase 4 acceptance criteria**

- `uv run task test` green (no regressions).
- Measurable reduction in lines/duplication across interfaces.

**Review + commit:** per sub-item (`refactor: ...`).

---

## Phase 5 — `fields.yml` as package internals (drop user overrides)

**Goal:** treat `fields.yml` as **library internals loaded only from package
resources**. Drop the user-override path for them entirely — no copy to
`~/.config`, no precedence, no prerequisite.

### Problem

- `fields.yml` (22 of 26 packaged files) are **library internals** — API-response
  path → output-column maps, tightly coupled to `parse`/`_extract_fields`. They are
  data, not user preferences; editing them (renaming/removing keys) silently breaks
  parsing. No real use case for user overrides.
- Current flow ships them in `bioseq_dl/config/` but `bioseq-dl-init` **copies** them
  to `~/.config/bioseq_dl/<db>`; interfaces read only from there. Consequences:
  - **Hard prerequisite / flaky first run:** missing dir → `_load_all_configs` raises
    `FileNotFoundError` (Copilot review comment #2).
  - **Stale copies = silent breakage:** `copy_single_file_to_user_config` skips
    existing files, so `pip install -U` never updates a user's `fields.yml`. A library
    update that changes a field path then breaks the user's stale copy with no warning.
  - **Library-hostile:** Sylphy/Roxy import this; import-and-use must work without an
    init CLI writing to `~/.config`.

### Decision

`fields.yml` are **not** user-overridable. Load them straight from package resources;
the library version is always authoritative and in sync with the code.

### Steps

- [x] Added `load_packaged_config(subdir, name)` (`interfacesconfig.py`); `fields.yml`
  loaded via `importlib.resources` only — packaged file is the single source of truth.
- [x] `BaseAPIInterface._load_packaged_fields` overlays packaged fields; `_load_all_configs`
  no longer raises on a missing dir (logs + falls back). Fixes Copilot #2.
- [x] **Killed `bioseq-dl-init` entirely**: deleted `init_config.py`, the
  `bioseq-dl-init` entry point, and the CLI first-run init callback. Removed the now
  unused `ConfigLoader` class.
- [x] `uniprot_crossref/config_endpoints.yml` → package-loaded (crossref enricher + CLI).
- [x] Internal `init.yml` for `download_folder` (alphafold/pdb) → package-loaded;
  overridable via the `output_dir` constructor arg. Deleted the 3 comment-only
  `init.yml` (biogrid/brenda/refseq). Credentials remain env / `.env`.
- [x] Updated README: configuration ships inside the package; field maps are internal
  (not user-overridable); only credentials are user-facing.
- [x] Tests: packaged-fields load with no user dir; `_load_packaged_fields` empty
  without `DB_CONFIG`.

**Phase 5 acceptance criteria**

- Fresh install: `import bioseq_dl` + instantiate any interface + parse works with **no**
  `bioseq-dl-init` run and no `~/.config/bioseq_dl`.
- No code path reads `fields.yml` from a user directory.
- `uv run task test` green; no `FileNotFoundError` on missing config dir.

**Review + commit:** `refactor: load fields.yml from package resources, drop user overrides`

---

## Phase 6 — `requests` → `niquests` migration (deferred)

**Goal:** modernize the HTTP layer. Deferred until the above is stable.

- [ ] Replace `requests` with `niquests` in `base.py` and anywhere `session` is used.
- [ ] Verify `HTTPAdapter`/`Retry` equivalents in niquests.
- [ ] ⚠️ `responses` patches `requests` internals and does **not** work with niquests:
  rewrite the mock behind the `conftest` fixtures (already isolated in Phase 0).
- [ ] Update dependencies in `pyproject.toml`.

**Phase 6 acceptance criteria**

- `uv run task test` green with the new mock.
- No behavior change in the interfaces.

**Review + commit:** `refactor: migrate HTTP layer requests→niquests`

---

## Phase 7 — `pandas` → `polars` migration (deferred)

**Goal:** align the data backend with the group ecosystem (Roxy/Sylphy use `polars`).
The most invasive; goes last.

**Scope — `pandas` is embedded across nearly the whole data flow:**

- `base.py`: `_maybe_parse` (DataFrame construction per format), `fetch_single`
  (multi-query branch: `pd.concat`, `data_info`), `fetch_batch` (result concat,
  `data_info`), `load_cache`/`save_cache` (CSV via pandas), `_load_file`.
- All `cli/interfaces/*`: `result.to_csv(...)` (already touched in Phase 2 via
  `save_or_print` → centralizes the change here).
- `core/export.py`, `core/crossref_enricher.py`, `core/utils/*`, `workflow/*`.

**Steps**

- [ ] Inventory all `pandas` uses (`pd.DataFrame`, `read_csv`, `to_csv`,
  `concat`, `isna`/`isnull`, `dtype`, `to_dict`).
- [ ] Define the public output type (`polars.DataFrame`) and alias it in `types.py`
  (roxy `FeatureFrame` pattern).
- [ ] Migrate central helpers first: `_build_data_info` (Phase 3), `save_or_print`
  (Phase 2), cache CSV I/O. Concentrate the change where it was already centralized.
- [ ] Migrate `_maybe_parse` and the `fetch_single`/`fetch_batch` branches.
- [ ] Migrate `export.py`, `crossref_enricher.py`, `workflow/`, `utils/`.
- [ ] ⚠️ API differences: `isna`→`is_null`, `concat(ignore_index)`→`pl.concat`,
  `df[col].dtype`, `to_dict(orient="records")`→`to_dicts()`, indexes (polars has none),
  `read_csv`/`write_csv`. Review type inference on columns with nulls/mixed types.
- [ ] Drop `pandas`/`pyarrow`/`fastparquet` from deps if no longer used; add `polars`.
- [ ] Tests: update shape/column asserts to the polars API.

**Phase 7 acceptance criteria**

- `uv run task test` green with polars.
- CSV outputs equivalent to the previous ones (compare samples).
- No residual `import pandas` (except an external dep that requires it).

**Review + commit:** `refactor: migrate data backend pandas→polars`

---

## Process notes

- One phase at a time. Don't start the next without review + commit of the previous.
- Branch per phase or per bug if smaller PRs are preferred.
- Tests always offline (no real network).
- No mass lint silencing; ignores justified and documented.
