# SilkRoute

[![PyPI](https://img.shields.io/pypi/v/silkroute?style=flat-square)](https://pypi.org/project/silkroute/)
[![PyVersions](https://img.shields.io/pypi/pyversions/silkroute?style=flat-square)](https://github.com/kren-ai-lab/silk-route)
[![Tests](https://img.shields.io/github/actions/workflow/status/kren-ai-lab/silk-route/tests.yml?style=flat-square)](https://github.com/kren-ai-lab/silk-route/actions/workflows/tests.yml)
![License](https://img.shields.io/github/license/kren-ai-lab/silk-route?style=flat-square)

SilkRoute is a Python library and command-line tool for reproducible biological data retrieval.

It covers three main workflows:

- Direct API access through 20 database interfaces (UniProt, AlphaFold, ChEMBL, KEGG, and others),
  with config-driven parsing, on-disk caching, and export to CSV, JSON, XML, or Parquet
- Cross-database enrichment, which takes a result set and attaches records other databases hold for
  the same entities
- Reproducible workflows described in YAML, where every run writes its own metadata and a
  machine-readable summary

> [!NOTE]
> The validated workflow surface covers UniProt protein retrieval, compound retrieval through the
> supported ChEMBL, PubChem, and ChEBI query prefixes, and interaction-oriented retrieval. The
> BLAST-backed UniProt sequence search is exposed in the CLI but is experimental: it needs BLAST+
> and a local database.

## Installation

SilkRoute supports Python 3.11 through 3.14.

```bash
pip install silkroute
```

Install optional extras as needed:

- `gui` for the NiceGUI descriptor editor
- `dev` for linting and type checking
- `tests` for the test suite

```bash
pip install 'silkroute[gui]'
pip install 'silkroute[dev,tests]'
```

You do not need a setup step after installing: the configuration ships inside the package. Only the
credentialed APIs and the experimental sequence search need extra work.

| Feature | Requirement |
| --- | --- |
| BioGRID | Access key ([request](https://webservice.thebiogrid.org/)) via `SILKROUTE_BIOGRID_API_KEY` |
| BRENDA | Email and password ([register](https://www.brenda-enzymes.org/login.php)) via `SILKROUTE_BRENDA_EMAIL` and `SILKROUTE_BRENDA_PASSWORD` |
| RefSeq | Contact email via `SILKROUTE_REFSEQ_EMAIL` |
| Experimental sequence search | The BLAST+ binaries on `PATH` |

> [!TIP]
> BLAST+ installs from bioconda: `conda install -c bioconda blast`, or with
> [pixi](https://pixi.prefix.dev/latest/): `pixi global install -c bioconda blast`.

## Quick start

Search UniProt and attach an AlphaFold cross-reference:

```bash
silkroute search uniprot by-query \
  --query "antimicrobial AND reviewed:true" \
  --fields accession,protein_name,gene_primary,sequence \
  --crossref-fields alphafold \
  --output-dir results/antimicrobial
```

Call a single endpoint directly:

```bash
silkroute fetch alphafold prediction P12345 -o out.csv
```

Run a workflow from a descriptor:

```bash
silkroute workflow validate examples/workflows/protein_query_first_minimal.yml
silkroute workflow run --config examples/workflows/protein_query_first_minimal.yml
```

## Supported databases

<details>
<summary><strong>20 database interfaces</strong></summary>

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
| SABIO-RK | Reaction kinetics data (Python API only, no CLI sub-app) |
| STRING | Protein-protein interaction networks |

</details>

## Command-line interface

Four namespaces. Run `silkroute --help` or `silkroute <namespace> --help` for the full list.

| Namespace | Purpose | Example |
| --- | --- | --- |
| `fetch <db> <endpoint>` | Direct endpoint access using each API's own nomenclature | `silkroute fetch alphafold prediction P12345 -o out.csv` |
| `search {uniprot,chemical}` | Higher-level search interfaces | `silkroute search uniprot by-ids --input ids.csv` |
| `workflow {run,validate}` | Reproducible multi-step runs | `silkroute workflow run --config run.yml` |
| `cache {list,clear}` | Inspect or purge the on-disk cache | `silkroute cache list` |

Every command exports `csv`, `json`, `xml`, or `parquet`. `dataframe` is internal only and is not a
public export format. `fetch` takes `-f/--format` and infers the format from the output extension
when you omit it, while `search` (`-ef`) and `workflow` (`-e`) take `--export-format` and default to
`csv`. `fetch` also writes a `<output>.metadata.json` provenance sidecar unless you pass
`--no-metadata`.

<details>
<summary>More <code>search uniprot</code> examples</summary>

By query, for length-bounded antimicrobial proteins with cross-references:

```bash
silkroute search uniprot by-query \
  --query "(length:[50 TO 51]) AND antimicrobial AND reviewed:true" \
  --fields accession,protein_name,gene_primary,sequence,ec \
  --crossref-fields alphafold,pdb \
  --output-dir search_query_test
```

By accession ID, reading identifiers from a column of a CSV:

```bash
silkroute search uniprot by-ids \
  --input unknown_ids.csv \
  --column accession \
  --output-dir search_ids_test \
  --crossref-fields alphafold
```

By sequence, which is experimental and needs BLAST+:

```bash
silkroute search uniprot by-sequences \
  --database uniprotkb_reviewed \
  --seq-column sequence \
  --min-identity 100.0 \
  --input unknown_sequences.csv \
  --output-dir search_sequences_test
```

</details>

## Workflows

Workflows run data acquisition with retries, multi-threaded API calls, optional enrichment, and
machine-readable run records (`metadata.json` plus `run_summary.yml`). You drive them with CLI
flags, a [YAML descriptor](#yaml-descriptors), or both.

| Modality | Covers | Typical output |
| --- | --- | --- |
| `protein` | Protein sequences and properties | Temperature, activity data, sequences |
| `compound` | Chemical compounds and bioactivity | IC50, binding affinity, activity |
| `interaction` | Protein interactions | Network data, interaction strength |

| Mode | Use case | Query format |
| --- | --- | --- |
| `query_first` | One query for the selected modality | `temperature:*` |
| `query_composition` | Several labeled queries, compared or grouped | `query1=label1,query2=label2` |

Compound workflows accept ChEMBL, PubChem, and ChEBI source-prefixed queries. PubChem and ChEBI are
reachable only through the supported workflow-v1 query forms.

```bash
silkroute workflow run \
  -o workflow_test \
  -q "temperature:99=temp_99,temperature:98=temp_98" \
  --modality protein \
  --mode query_composition \
  --debug
```

Both labeled queries run, and each exported record carries its label (`temp_99`, `temp_98`) in the
combined result file. The labeling syntax:

- `query=label` or `query|label`, where the **final** `=` or `|` is the delimiter
- Commas separate multiple pairs: `query1=label1,query2=label2`
- An internal `=` stays part of the query: `chembl.molecule:name__iexact=Imatinib=imatinib`

### Options

A run needs `-o/--output`, `-m/--modality`, `-d/--mode`, and `-q/--query` unless a descriptor
supplies them.

| Option | Effect |
| --- | --- |
| `-e, --export-format` | `csv` (default), `json`, `xml`, `parquet` |
| `--enrich / --no-enrich` | Toggle cross-reference enrichment |
| `-w, --max-workers` | Worker threads for API calls. More threads finish sooner and load the API harder |
| `-r, --total-retries` | Retry attempts for failed calls |
| `--chembl-pages-to-fetch` | `-1` for all pages, a positive value to cap them |
| `--uniprot-timeout` | UniProt request timeout, in seconds |
| `--include-isoform / --no-include-isoform` | Include UniProt isoforms |
| `--debug` | Debug logging |

### Outputs

| File | Contents |
| --- | --- |
| `*_results.{csv,json,xml,parquet}` | Retrieved workflow results |
| `{database}_{endpoint}.{ext}` | Cross-referenced data, when enrichment produces output |
| `metadata.json` | Workflow metadata, original descriptor sections, normalized executable values, generated files, reporting metrics |
| `run_summary.yml` | Compact report: dataset and query, status, timings, export settings, row and column counts |

The summary status reflects real execution: `success`, `completed_with_errors` (outputs exist but
the metadata records errors), or `failed` (execution failed, or a primary fetch error left no real
output). When `harmonization.id_column` is set, exported tabular files gain a deterministic ID
column if they lack one. In-memory objects and raw API responses stay untouched.

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

Descriptors make a run reproducible. They declare `schema_version: "workflow-v1"` plus `dataset`,
`query`, `resources`, `execution`, `harmonization`, `export`, and `reporting` sections. Canonical
examples live in [`examples/workflows/`](examples/workflows/), and
[`docs/workflow_yaml.md`](docs/workflow_yaml.md) documents the full schema, including every field,
forbidden key, and limitation.

```bash
# CLI flags override YAML, so one descriptor serves many runs
silkroute workflow run --config examples/workflows/protein_query_first_minimal.yml -o result_override
```

Validation reports every section-level error at once and exits non-zero:

```text
Error: my-workflow.yml has 2 validation error(s):
  - Unsupported dataset.modality 'rna'. Supported modalities are: protein, compound, interaction.
  - Unsupported export format 'xlsx'. Supported formats are: csv, json, xml, parquet.
```

Four things are worth knowing before you write one.

Not every field executes. `dataset.modality`, `dataset.mode`, `query.value`, selected `query` and
`execution` options, and the `export` options drive the run. `query.builder`, `query.composition`,
`query.description`, and `query.filtering_strategy` are descriptive metadata: they are preserved in
`metadata.json` and `run_summary.yml` but never executed. If `query.composition` is present it must
match `query.value`.

ChEMBL paging works per page. `execution.chembl_pages_to_fetch: -1` (the default) fetches all pages
and a positive value caps them, while `limit` is records *per page* rather than a total or a page
count.

IC50 units accept `nM`, `uM`, `mM`, and `pM`, and `µM`/`μM` normalize to `uM`. SilkRoute never
converts values between units.

Credentials never go in YAML. They come from environment variables or `.env` only.

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

A NiceGUI form that **prepares** `workflow-v1` descriptors. It never executes a workflow or calls an
external API; execution stays in the CLI.

```bash
pip install 'silkroute[gui]'
silkroute-gui                       # or: python -m silkroute.gui.nicegui_app
```

The form offers two query modes. Manual writes `query.value` directly, and the Advanced builder
offers UniProt, ChEMBL, PubChem, and ChEBI builders filtered by the selected modality and
interaction type. Either way `query.value` is the executable output.

Existing files round-trip. Loading a `workflow-v1` YAML populates the supported fields, and
`query-builder-v1` metadata restores editable builder rows. Metadata the GUI cannot read falls back
to manual or read-only handling and leaves `query.value` intact. GUI labels map to exact schema
values, and `query.fields` stores UniProt field IDs rather than the visible labels.

[`docs/workflow_yaml.md`](docs/workflow_yaml.md) carries the full GUI reference: per-source builder
semantics, connector versus match mode, return-field selection, harmonization controls, and smoke
tests.

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

Credentials are the only user-facing configuration. They resolve in this order:

1. Explicit CLI arguments or constructor parameters
2. Environment variables, including values loaded from a `.env` file

SilkRoute looks for `.env` at `SILKROUTE_ENV_FILE`, then in the working directory, then at
`~/.config/silkroute/.env` or a per-interface directory such as
`~/.config/silkroute/biogrid/.env`. `silkroute/config/.env.example` is the template.

| Variable | Used by |
| --- | --- |
| `SILKROUTE_BIOGRID_API_KEY` | BioGRID |
| `SILKROUTE_BRENDA_EMAIL`, `SILKROUTE_BRENDA_PASSWORD` | BRENDA |
| `SILKROUTE_REFSEQ_EMAIL` | RefSeq |

> [!WARNING]
> Credentials come only from environment variables or `.env`, never from packaged config and never
> from workflow YAML. Do not commit `.env` files.

### Cache and config locations

By default SilkRoute keeps its cache and its per-API config in the platform directories:

- Linux: `~/.cache/silkroute` and `~/.config/silkroute`
- macOS: `~/Library/Caches/silkroute` and `~/Library/Application Support/silkroute`
- Windows: `%LOCALAPPDATA%\silkroute\Cache` and `%LOCALAPPDATA%\silkroute`

Two environment variables override them, which is useful for tests, CI, and shared scratch disks:

- `SILKROUTE_CACHE_DIR` for the cache root, which also relocates the BLAST database directory
  (`<cache root>/blast_db`)
- `SILKROUTE_CONFIG_DIR` for the config root

Use `silkroute cache list` and `silkroute cache clear` to inspect or purge what has accumulated.

### Packaged configuration

Everything else ships inside the package under `silkroute/config/<api>/` and loads automatically, so
there is nothing to copy into `~/.config`. The per-API `fields.yml` files map API responses to
output columns, keyed by endpoint name as `output_column: api.response.path`:

```yaml
# silkroute/config/alphafold/fields.yml
prediction:
  entry: entryId
  gene: gene
  tax_id: taxId
  organism: organismScientificName
```

These files are library internals rather than user settings, since editing them breaks parsing.
Download locations are chosen per call through the interface `output_dir` argument.

## Learn more

- [`docs/workflow_yaml.md`](docs/workflow_yaml.md) for the full `workflow-v1` schema and GUI
  reference
- [`examples/`](examples/) for runnable scripts, notebooks, and descriptor examples
- [DEVELOPMENT.md](DEVELOPMENT.md) for local setup, tests, and how the API fixtures are regenerated

## Roadmap

- [ ] Automatic caching and offline mode
- [ ] Integration with external ML workflows
- [ ] Improve the API example notebooks

## Contributing

Issues and pull requests should keep the documented workflow surface aligned with implemented and
tested behavior. [DEVELOPMENT.md](DEVELOPMENT.md) covers development setup and testing conventions.

## License

**MIT**. See [LICENSE](LICENSE).

## Acknowledgements

Built with polars, Biopython, Typer, niquests, and zeep. Some modules are based on the
[UniProt API](https://www.uniprot.org/help/api),
[UniProt ID Mapping](https://www.uniprot.org/help/id_mapping), and the
[AlphaFold Database](https://alphafold.ebi.ac.uk).

Developed by **KREN AI Lab** at Universidad de Magallanes, Chile.
