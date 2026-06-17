# CLI notes

The CLI was reworked for consistency (taxonomy, output/format flags, logging,
naming). See `CLI_REFACTOR_PLAN.md` at the repo root for the full record and the
remaining optional stages.

Conventions (current):
- Top-level groups: `fetch` (per-database, API nomenclature), `search` (general
  search interfaces), `workflow`, `cache`.
- Primary identifier is a positional argument; secondary filters are options.
- Output: `--output/-o` (file) or `--output-dir/-o` (directory commands), with
  `--format/-f` for tabular results (csv/json/xml/parquet, inferred from the
  extension if omitted).
- Logging level: global `--log/-l` before the subcommand.

Open items:
- [ ] `chemical` search: exercise every possible query type.
- [ ] Workflows: JSON and XML output coverage.
