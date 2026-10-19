# Changelog

## 0.2.0

Aligns the CLI with the shared ecosystem CLI contract.

### Breaking changes

- Exit codes: config and usage errors exit 2, runtime failures exit 3 (failed runs, API and I/O errors), unexpected errors exit 4 with the traceback. These replace the former exit code 1.
- `workflow validate` is now `workflow validate-config`. It exits 2 (not 1) on invalid descriptors and prints `path: message` lines to stderr instead of the former error report on stdout.
- Primary result tables (`uniprot_results`, `chembl_results`, `pubchem_results`, `chebi_results`) always start with a string `id` column taken from the table's native key. The positional `<label>_<n>` ids are gone.
- `harmonization.id_column` only renames the id column (default `id`). Ids must be unique and non-empty, otherwise the run exits 3. In `query_composition` runs a record returned under several labels is kept once per label (each `(id, _label)` pair is unique), with a warning; the run sidecar lists those ids under `extensions.ids_in_several_labels`.
- Enrichment tables no longer get an id column.
- A `query.fields` selection now always keeps `accession` in the UniProt table.
- The unused keys `export.result_files`, `harmonization.label_column`, `harmonization.unique_sequence_strategy` and `harmonization.metadata_fields` are now unknown-key errors, and the GUI no longer offers them.
- `fetch -o FILE` writes `FILE.provenance.json` instead of `FILE.metadata.json`; the old metadata fields moved under `extensions`. `--no-metadata` still disables it.
- `search chemical` writes `<db>_results.csv.provenance.json` instead of `<db>_metadata.json`.
- The UniProt cross-reference command writes `<input>_results.csv.provenance.json` instead of `metadata.json`, and only when it produced results.

### Added

- `workflow validate-config CONFIG [--json]`: reports every error (several per section), each with a dotted path, and prints the `validate-errors` JSON array with `--json`.
- `workflow run` writes `<output_dir>.provenance.json` (`provenance/1`) next to the output directory, on `success` and `completed_with_errors`. `metadata.json` and `run_summary.yml` stay inside it.
- Contract conformance tests against the shared JSON schemas (`tests/contract/`, `jsonschema` as a dev dependency).
