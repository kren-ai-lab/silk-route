# SilkRoute

**SilkRoute** is a Python library and command-line tool for reproducible biological data
retrieval. It provides database-specific interfaces, config-driven parsing, cross-database
enrichment and mapping, YAML workflow descriptors, run metadata capture, and export to CSV,
JSON, XML, and Parquet.

> **Scope.** The validated workflow surface covers UniProt protein retrieval, compound
> retrieval through the supported ChEMBL / PubChem / ChEBI query prefixes, and
> interaction-oriented retrieval through the existing interfaces. BLAST-backed UniProt
> sequence search is exposed in the CLI but should be treated as experimental — it requires
> BLAST+ and a local database.

- [Quick start](#quick-start)
- [Installation](#installation)
- [Supported databases](#supported-databases)
- [Command-line interface](#command-line-interface)
- [Workflows](#workflows)
- [YAML descriptors](#yaml-descriptors)
- [GUI (optional)](#gui-optional)
- [Python API](#python-api)
- [Configuration](#configuration)
- [Roadmap](#roadmap)

## Quick start

```bash
git clone https://github.com/kren-ai-lab/silk-route
cd silk-route
pip install -e .

# One reviewed UniProt query, exported to CSV with an AlphaFold cross-reference
silkroute search uniprot by-query \
  --query "antimicrobial AND reviewed:true" \
  --fields accession,protein_name,gene_primary,sequence \
  --crossref-fields alphafold \
  --output-dir results/antimicrobial
```

No setup step is needed: configuration ships inside the package. Only APIs that require
credentials (BioGRID, BRENDA, RefSeq) need extra work — see
[Configuration](#configuration).

## Installation

Requires Python 3.11-3.14.

```bash
# recommended: isolated environment
conda create -n silkroute python=3.13 && conda activate silkroute

pip install -e .              # core
pip install -e ".[gui]"       # + optional NiceGUI descriptor editor
pip install -e ".[dev,tests]" # + linting, type checking, test suite
```

Optional extras for specific features:

| Feature | Requirement |
| --- | --- |
| Experimental sequence search | BLAST+ — `conda install -c bioconda blast` |
| BioGRID | Access key ([request](https://webservice.thebiogrid.org/)) via `SILKROUTE_BIOGRID_API_KEY` |
| BRENDA | Email + password ([register](https://www.brenda-enzymes.org/login.php)) via `SILKROUTE_BRENDA_EMAIL` / `SILKROUTE_BRENDA_PASSWORD` |
| RefSeq | Contact email via `SILKROUTE_REFSEQ_EMAIL` |

## Supported databases

<details>
<summary><strong>19 database interfaces</strong> (CLI + Python API)</summary>

| Database | Description |
| --- | --- |
| UniProt | Universal protein sequence database |
| AlphaFold | Protein structure predictions |
| BioDBNet | Biological database network |
| BioGRID | Protein-protein interaction data |
| BRENDA | Enzyme information system |
| ChEBI | Chemical Entities of Biological Interest |
| ChEMBL | Bioactive molecule database |
| Gene Ontology | Functional annotation of genes |
| InterPro | Protein families and domains |
| KEGG | Kyoto Encyclopedia of Genes and Genomes |
| Panther | Protein family classification |
| Pathway Commons | Biological pathways |
| PDB | Protein Data Bank |
| Pride | Proteomics data repository |
| PubChem | Chemical molecule database |
| Reactome | Pathway database |
| RefSeq | NCBI Reference Sequence Database |
| Rhea | Biochemical reactions database |
| STRING | Protein-protein interaction networks |

</details>

## Command-line interface

Four namespaces — run `silkroute --help` or `silkroute <namespace> --help` for the full list.

| Namespace | Purpose | Example |
| --- | --- | --- |
| `fetch <db> <endpoint>` | Direct endpoint access using each API's own nomenclature | `silkroute fetch alphafold prediction P12345 -o out.csv` |
| `search {uniprot,chemical}` | Higher-level search interfaces | `silkroute search uniprot by-ids --input ids.csv` |
| `workflow {run,validate}` | Reproducible multi-step runs | `silkroute workflow run --config run.yml` |
| `cache {list,clear}` | Inspect or purge the on-disk cache | `silkroute cache list` |

Every command exports `csv`, `json`, `xml`, or `parquet` (`dataframe` is internal only, not a
public export format): `fetch` takes `-f/--format` and infers it from the output extension
when omitted, while `search` (`-ef`) and `workflow` (`-e`) take `--export-format` and default
to `csv`.
`fetch` also writes a `<output>.metadata.json` provenance sidecar by default — disable it
with `silkroute fetch --no-metadata`.

**Search UniProt by query** — length-bounded antimicrobial proteins, with cross-references:

```bash
silkroute search uniprot by-query \
  --query "(length:[50 TO 51]) AND antimicrobial AND reviewed:true" \
  --fields accession,protein_name,gene_primary,sequence,ec \
  --crossref-fields alphafold,pdb \
  --output-dir search_query_test
```

**Search UniProt by accession IDs** — read identifiers from a column of a CSV:

```bash
silkroute search uniprot by-ids \
  --input unknown_ids.csv \
  --column accession \
  --output-dir search_ids_test \
  --crossref-fields alphafold
```

**Search UniProt by sequence** (experimental, needs BLAST+):

```bash
silkroute search uniprot by-sequences \
  --database uniprotkb_reviewed \
  --seq-column sequence \
  --min-identity 100.0 \
  --input unknown_sequences.csv \
  --output-dir search_sequences_test
```

## Workflows

Workflows run reproducible data acquisition across the current modalities, with retries,
multi-threaded API calls, optional enrichment, and machine-readable run records
(`metadata.json` + `run_summary.yml`). They are driven by CLI flags, a
[YAML descriptor](#yaml-descriptors), or both.

| Modality | Covers | Typical output |
| --- | --- | --- |
| `protein` | Protein sequences and properties | Temperature, activity data, sequences |
| `compound` | Chemical compounds and bioactivity | IC50, binding affinity, activity |
| `interaction` | Protein interactions | Network data, interaction strength |

| Mode | Use case | Query format |
| --- | --- | --- |
| `query_first` | One query for the selected modality | `temperature:*` |
| `query_composition` | Several labeled queries, compared or grouped | `query1=label1,query2=label2` |

Compound workflows accept ChEMBL, PubChem, and ChEBI source-prefixed queries; PubChem and
ChEBI are reachable only through the supported workflow-v1 query forms.

### Options

```bash
silkroute workflow run [OPTIONS]
silkroute workflow validate CONFIG.yml
```

Required (unless supplied by a descriptor): `-o/--output`, `-m/--modality`, `-d/--mode`,
`-q/--query`.

| Option | Effect |
| --- | --- |
| `-e, --export-format` | `csv` (default), `json`, `xml`, `parquet` |
| `--enrich / --no-enrich` | Toggle cross-reference enrichment |
| `-w, --max-workers` | Worker threads for API calls (higher = faster, more API load) |
| `-r, --total-retries` | Retry attempts for failed calls |
| `--chembl-pages-to-fetch` | `-1` for all pages, positive value to cap |
| `--uniprot-timeout` | UniProt request timeout, seconds |
| `--include-isoform / --no-include-isoform` | Include UniProt isoforms |
| `--debug` | Debug logging |

### Example 1 — `query_first`: proteins with temperature data

```bash
silkroute workflow run \
  -o result \
  -q "temperature:*" \
  --modality protein \
  --mode query_first \
  -w 5 -r 1 --debug
```

Runs the UniProt-compatible query, enriches it when enrichment is on and supported fields
are requested, exports the table, then writes `metadata.json` and `run_summary.yml`:

```
result/
|-- uniprot_results.csv
|-- metadata.json
`-- run_summary.yml
```

### Example 2 — `query_composition`: comparing temperature optima

```bash
silkroute workflow run \
  -o workflow_test \
  -q "temperature:99=temp_99,temperature:98=temp_98" \
  --modality protein \
  --mode query_composition \
  --debug
```

Both labeled queries run, and each exported record carries its label (`temp_99`, `temp_98`)
in the combined result file. Labeling syntax:

- `query=label` or `query|label` — the **final** `=` or `|` is the delimiter.
- Comma-separates multiple pairs: `query1=label1,query2=label2`.
- Internal `=` stays part of the query: `chembl.molecule:name__iexact=Imatinib=imatinib`.

### Example 3 — `query_composition`: compound bioactivity bands

```bash
silkroute workflow run \
  -o workflow_compound \
  -q "ic50:10-50=active,ic50:50-100=inactive" \
  --modality compound \
  --mode query_composition \
  --debug
```

Retrieves ChEMBL activity records into two labeled datasets (`standard_value` 10-50 and
50-100), enforcing `standard_type = IC50` and applying numeric filtering after retrieval.
`standard_units` is constrained when requested — values are never converted between units.

### Outputs

| File | Contents |
| --- | --- |
| `*_results.{csv,json,xml,parquet}` | Retrieved workflow results |
| `{database}_{endpoint}.{ext}` | Cross-referenced data, when enrichment produces output |
| `metadata.json` | Workflow metadata, original descriptor sections, normalized executable values, generated files, reporting metrics |
| `run_summary.yml` | Compact report: dataset/query, status, timings, export settings, row and column counts |

Summary status reflects real execution: `success`, `completed_with_errors` (outputs exist but
metadata records errors), or `failed` (execution failed, or a primary fetch error left no
real output). When `harmonization.id_column` is set, exported tabular files gain a
deterministic ID column if absent — in-memory objects and raw API responses stay untouched.

### Scenario cheat sheet

| Goal | Modality | Mode | Query |
| --- | --- | --- | --- |
| All thermophilic proteins | protein | `query_first` | `temperature:*` |
| Compare two temperature optima | protein | `query_composition` | `temperature:20=temp_low,temperature:80=temp_high` |
| Classify compounds by activity | compound | `query_composition` | `ic50:10-50=active,ic50:50-100=inactive` |
| IC50 activity records | compound | `query_first` | `ic50:<1000 AND standard_units:nM` |
| PubChem compounds | compound | `query_first` | `pubchem.compound:name="glucose"` |
| ChEBI entities | compound | `query_first` | `chebi.entity:chebi_id=CHEBI:15377` |

## YAML descriptors

Descriptors make a run reproducible. They declare `schema_version: "workflow-v1"` plus
`dataset`, `query`, `resources`, `execution`, `harmonization`, `export`, and `reporting`
sections. Canonical examples live in [`examples/workflows/`](examples/workflows/); the full
schema — every field, forbidden key, and limitation — is in
[`docs/workflow_yaml.md`](docs/workflow_yaml.md).

```bash
silkroute workflow validate examples/workflows/protein_query_first_minimal.yml
silkroute workflow run --config examples/workflows/protein_query_first_minimal.yml

# CLI flags override YAML, so one descriptor serves many runs
silkroute workflow run --config examples/workflows/protein_query_first_minimal.yml -o result_override
silkroute workflow run --config examples/workflows/protein_query_first_minimal.yml -e csv
```

Validation reports every section-level error at once and exits non-zero; a valid descriptor
exits zero and echoes the resolved modality, mode, and output directory:

```text
Error: my-workflow.yml has 2 validation error(s):
  - Unsupported dataset.modality 'rna'. Supported modalities are: protein, compound, interaction.
  - Unsupported export format 'xlsx'. Supported formats are: csv, json, xml, parquet.
```

Four things worth knowing before writing one:

- **Not every field executes.** `dataset.modality`, `dataset.mode`, `query.value`, selected
  `query`/`execution` options, and `export` options drive the run. `query.builder`,
  `query.composition`, `query.description`, and `query.filtering_strategy` are descriptive
  metadata — preserved in `metadata.json` and `run_summary.yml`, not executed. If
  `query.composition` is present it must match `query.value`.
- **ChEMBL paging.** `execution.chembl_pages_to_fetch: -1` (default) fetches all pages;
  a positive value caps them. `limit` is records *per page*, not a total or a page count.
- **IC50 units** accept `nM`, `uM`, `mM`, `pM`; `µM`/`μM` normalize to `uM`. No implicit
  numeric conversion happens.
- **Credentials never go in YAML** — only environment variables or `.env`.

<details>
<summary>Minimal protein descriptor</summary>

```yaml
schema_version: "workflow-v1"

dataset:
  name: antimicrobial_reviewed_proteins
  description: Reviewed UniProt protein records retrieved with an antimicrobial query.
  modality: protein
  mode: query_first
  primary_data_source: uniprot

query:
  value: "antimicrobial AND reviewed:true"
  description: Retrieve reviewed UniProt protein entries matching an antimicrobial query.

execution:
  enrich: false
  max_workers: 5
  total_retries: 3

harmonization:
  id_column: "_id"

export:
  output_dir: "results/protein_antimicrobial_reviewed"
  format: csv
  include_metadata: true
  include_summary: true
```

</details>

Tools that generate descriptors can read the schema definition programmatically:

```python
from silkroute.core.workflow.schema import get_workflow_v1_schema_definition
```

## GUI (optional)

A NiceGUI form that **prepares** `workflow-v1` descriptors — it never executes a workflow or
calls an external API. Execution stays in the CLI.

```bash
pip install -e ".[gui]"
silkroute-gui                       # or: python -m silkroute.gui.nicegui_app
```

- **Two query modes.** Manual writes `query.value` directly; Advanced builder offers
  UniProt, ChEMBL, PubChem, and ChEBI builders, filtered by the selected modality and
  interaction type. Either way, `query.value` is the executable output.
- **Round-trips existing files.** Loading a `workflow-v1` YAML populates the supported
  fields; `query-builder-v1` metadata restores editable builder rows. Unsupported or
  malformed metadata falls back to manual/read-only handling and leaves `query.value` intact.
- **Stable IDs, friendly labels.** GUI labels map to exact schema values, and `query.fields`
  stores UniProt field IDs, never visible labels.

Full GUI reference — per-source builder semantics, connector vs. match mode, return-field
selection, harmonization controls, smoke tests — is in
[`docs/workflow_yaml.md`](docs/workflow_yaml.md).

## Python API

Fetch a batch through a database interface:

```python
import polars as pl
from silkroute import UniprotInterface

df = pl.DataFrame({
    "id": [1, 2, 3],
    "accession": ["A1L3X0", "A0JNC4", "A2RUC4"],
})

uniprot = UniprotInterface()
results, _ = uniprot.download_batch(
    df,
    id_column="accession",
    auto_db=False,
    from_db="UniProtKB_AC-ID",
    to_db="UniProtKB",
    batch_size=100,
)
results_df, _ = uniprot.parse(results, None)
print(results_df)
```

Then enrich those results with cross-referenced records from other databases:

```python
from silkroute.core.crossref_enricher import CrossRefEnricher, EndpointSpec

specs = [
    EndpointSpec(database="alphafold", endpoint="prediction"),
    EndpointSpec(database="pdb", endpoint="entry"),
]

enricher = CrossRefEnricher(specs)
concat_df, _ = enricher.enrich(results_df, concat_results=True)
```

## Configuration

### Credentials

The only user-facing configuration. Precedence:

1. Explicit CLI arguments or constructor parameters
2. Environment variables — including values loaded from a `.env` file

`.env` is looked up at `SILKROUTE_ENV_FILE`, then the working directory, then
`~/.config/silkroute/.env` (or a per-interface directory such as
`~/.config/silkroute/biogrid/.env`). Template: `silkroute/config/.env.example`.

| Variable | Used by |
| --- | --- |
| `SILKROUTE_BIOGRID_API_KEY` | BioGRID |
| `SILKROUTE_BRENDA_EMAIL`, `SILKROUTE_BRENDA_PASSWORD` | BRENDA |
| `SILKROUTE_REFSEQ_EMAIL` | RefSeq |

Credentials come only from environment variables or `.env` — never from packaged config, and
never from workflow YAML. Do not commit `.env` files.

### Packaged configuration

Everything else ships inside the package (`silkroute/config/<api>/`) and loads automatically
— nothing to copy to `~/.config`. Per-API `fields.yml` files map API responses to output
columns (endpoint name → `output_column: api.response.path`):

```yaml
# silkroute/config/alphafold/fields.yml
prediction:
  entry: entryId
  gene: gene
  tax_id: taxId
  organism: organismScientificName
```

These are library internals — not user-overridable, since editing them breaks parsing.
Download locations are chosen per call via the interface `output_dir` argument.

## Roadmap

In progress:

- [ ] Improve API example notebooks
- [ ] Expand README examples as additional workflows are validated

Planned:

- [ ] Automatic caching and offline mode
- [ ] Integration with external ML workflows

Done:

- [x] Document `.env` credential loading
- [x] Document YAML workflow descriptors
- [x] Add logging system

## Contributing

Issues and pull requests should keep the documented workflow surface aligned with implemented
and tested behavior. Development setup and testing conventions are in
[DEVELOPMENT.md](DEVELOPMENT.md).

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgements

Some modules are based on:

- [UniProt API](https://www.uniprot.org/help/api)
- [UniProt ID Mapping](https://www.uniprot.org/help/id_mapping)
- [AlphaFold Database](https://alphafold.ebi.ac.uk)
