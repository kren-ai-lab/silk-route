# BioSeqDownloader

**BioSeqDownloader** is a Python package and command-line tool for reproducible biological data retrieval. It provides database-specific interfaces, parsing helpers, enrichment and mapping utilities, YAML workflow descriptors, metadata capture, and export to CSV, JSON, XML, and Parquet.

The validated workflow surface currently focuses on UniProt protein retrieval, ChEMBL activity retrieval with UniProt target mapping, and interaction-oriented retrieval through the existing interfaces. BLAST-backed UniProt sequence search is exposed in the CLI, but should be treated as experimental and requires BLAST+ plus local database setup.

### Available Database Interfaces

Currently available CLI/API interfaces include:

| Database  | Description |
| ------------- | ------------- |
| UniProt  | Universal protein sequence database |
| AlphaFold  | Protein structure predictions |
| BioDBNet  | Biological database network |
| BioGRID  | Protein-protein interaction data |
| BRENDA  | Enzyme information system |
| CheBI  | Chemical Entities of Biological Interest |
| ChEMBL  | Bioactive molecule database |
| Gene Ontology  | Functional annotation of genes |
| InterPro  | Protein families and domains |
| KEGG  | Kyoto Encyclopedia of Genes and Genomes |
| Panther | Protein family classification |
| Pathway Commons | Biological pathways |
| PDB  | Protein Data Bank |
| Pride  | Proteomics data repository |
| PubChem | Chemical molecule database; not part of the validated YAML compound workflow |
| Reactome | Pathway database |
| RefSeq  | NCBI Reference Sequence Database |
| Rhea  | Biochemical reactions database |
| STRING  | Protein-protein interaction networks |


## Table of Contents

- [Features](#features)
- [Installation](#installation)
  - [Optional Steps for Specific Functionalities](#optional-steps-for-specific-functionalities)
- [Usage](#usage)
  - [Command-Line Interface (CLI)](#command-line-interface-cli)
  - [Workflow Interface (Automated Data Collection Workflows)](#workflow-interface-automated-data-collection-workflows)
  - [Programmatic API](#programmatic-api)
- [Configuration](#configuration)
  - [Credentials and environment variables](#credentials-and-environment-variables)
- [To-do List](#to-do-list)
- [Future Features](#future-features)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgements](#acknowledgements)

## Features

- Command-line interface and programmatic Python API.
- Reproducible data retrieval workflows described with YAML descriptors.
- Configurable parsing and field mapping for supported database responses.
- Cross-database enrichment and mapping for supported cross-reference fields.
- Credentials loaded from explicit arguments, environment variables, or `.env` files.
- Workflow metadata and run summaries through `metadata.json` and `run_summary.yml`.
- Public export formats: `csv`, `json`, `xml`, and `parquet`.

---

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/ProteinEngineering-PESB2/BioSeqDownloader
   cd BioSeqDownloader
   ```

2. **(Recommended)** Create and activate a virtual environment:
   ```bash
   conda create -n bioseqdownloader python=3.13
   conda activate bioseqdownloader
   ```

3. **Install the package and dependencies:**
   ```bash
   pip install -e .
   ```

4. **Optional, for experimental sequence search:** Install BLAST+ from Bioconda:
   ```bash
   conda install -c bioconda blast
   ```

5. **(Optional) Set credentials.**
   No setup step is required — the library ships its configuration internally and
   works on first import. For APIs needing credentials (BioGRID, BRENDA, RefSeq),
   set the `BIOSEQ_DL_*` environment variables (or place a `.env`; a template lives
   at `bioseq_dl/config/.env.example`). See the credentials section below.

---

### Optional Steps for Specific Functionalities

| Database | Requirement | Credential Source |
|-----------|--------------|-------------------|
| **BioGRID** | Access Key ([request here](https://webservice.thebiogrid.org/)) | `BIOSEQ_DL_BIOGRID_API_KEY` (or `.env`) |
| **BRENDA** | Email and password ([register here](https://www.brenda-enzymes.org/login.php)) | `BIOSEQ_DL_BRENDA_EMAIL` and `BIOSEQ_DL_BRENDA_PASSWORD` (or `.env`) |

---

## Usage

### Command Overview
To explore all available commands:
```bash
bioseq-dl --help
```

### Command-Line Interface (CLI)

**Example 1 - Search antimicrobial proteins (length 50-51) in UniProt:**
```bash
bioseq-dl search uniprot by-query \
--query "(length:[50 TO 51]) AND antimicrobial AND reviewed:true" \
--fields accession,protein_name,gene_primary,sequence,ec \
--crossref-fields alphafold,pdb \
--output-dir search_query_test
```

**Example 2 - Search UniProt entries by accession IDs:**
```bash
bioseq-dl search uniprot by-ids \
--input unknown_ids.csv \
--column accession \
--output-dir search_ids_test \
--crossref-fields alphafold
```

**Example 3 - Experimental BLAST-backed UniProt sequence search:**
```bash
bioseq-dl search uniprot by-sequences \
--database uniprotkb_reviewed \
--seq-column sequence \
--min-identity 100.0 \
--input unknown_sequences.csv \
--output-dir search_sequences_test \
--crossref-fields alphafold
```

This path is exposed by the CLI but is experimental compared with the validated YAML workflow path.

### Parquet outputs

Commands that export parsed tabular results can write Parquet files when `parquet` is selected as the output format. The public export formats are `csv`, `json`, `xml`, and `parquet`; `dataframe` is not accepted as a public export format. Parquet export requires the optional Parquet engine installed with the package dependencies.

### Workflow YAML descriptors

BioSeqDownloader supports structured YAML descriptors for reproducible workflow runs. These descriptors must declare `schema_version: "workflow-v1"` and define dataset, query, execution, harmonization, export, and reporting information. See [`docs/workflow_yaml.md`](docs/workflow_yaml.md) for the full implemented schema, field behavior, forbidden keys, credential policy, and examples.

The `workflow` namespace has two commands:

- `workflow run` — execute a workflow (descriptor and/or CLI options).
- `workflow validate` — check a YAML descriptor without running it.

Workflow runs can be described with a structured dataset descriptor and executed with:

```bash
bioseq-dl workflow run --config examples/workflows/protein_query_first_minimal.yml
```

CLI arguments override YAML values, so a descriptor can be reused with a different output directory or export format:

```bash
bioseq-dl workflow run --config examples/workflows/protein_query_first_minimal.yml -o result_override
bioseq-dl workflow run --config examples/workflows/protein_query_first_minimal.yml -e csv
```

Before running, validate a descriptor to catch schema problems early. All
section-level errors are reported at once:

```bash
bioseq-dl workflow validate examples/workflows/protein_query_first_minimal.yml
```

```text
✗ my-workflow.yml has 2 validation error(s):
  - Unsupported dataset.modality 'rna'. Supported modalities are: protein, compound, interaction.
  - Unsupported export format 'xlsx'. Supported formats are: csv, json, xml, parquet.
```

A valid descriptor exits zero and echoes the resolved modality, mode, and output directory.

YAML descriptors use top-level `schema_version`, `dataset`, `query`, `resources`, `execution`, `harmonization`, `export`, and `reporting` sections, plus a small allowlist of descriptive integration sections. `dataset.mode` is the workflow execution mode, and the only valid values are `query_first` and `query_composition`. Only part of the descriptor is executable: `dataset.modality`, `dataset.mode`, `query.value`, selected `query` options, supported `execution` options, and `export` options are mapped to the current workflow. `query.value` is the actual API query. `query.builder`, `query.composition`, `query.description`, and `query.filtering_strategy` are descriptive metadata only. If `query.composition` is present, it must match the executable `query.value`.

`resources`, allowed domain-specific integration sections, and most harmonization/reporting fields are preserved in `metadata.json` and `run_summary.yml` unless the current workflow already supports that behavior. `execution.merge_results` is descriptor metadata only; it does not currently trigger automatic result merging. Credentials must be provided through `.env` or environment variables, not YAML.

ChEMBL workflow fetches retrieve all available pages by default. In YAML, `execution.chembl_pages_to_fetch: -1` means all pages; a positive value caps the number of pages. ChEMBL `limit` remains records per page, not total records and not a page count. Large ChEMBL queries can take longer when all pages are fetched; use a positive page cap for quick validation runs.

For IC50 queries, the ChEMBL workflow enforces `standard_type = IC50` and numeric `standard_value` constraints for requested ranges. `standard_units` is preserved when returned by ChEMBL, but the workflow does not currently constrain units to nM.

Allowed top-level descriptor sections are: `schema_version`, `dataset`, `query`, `resources`, `execution`, `harmonization`, `export`, `reporting`, `interaction_retrieval`, `activity_retrieval`, `chemical_metadata_integration`, `protein_target_integration`, `temperature_enrichment`, and `cross_source_integration`.

Canonical workflow-v1 example descriptors are available under `examples/workflows/`.
There are no legacy top-level workflow YAML examples. Future GUI or YAML
generator tools can inspect the lightweight schema definition with:

```python
from bioseq_dl.workflow_schema_definition import get_workflow_v1_schema_definition
```

The future simple GUI will generate YAML only and will not execute workflows unless implemented in a separate task later.

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
  filtering_strategy: >
    Filtering is encoded in the UniProt-compatible query string.

execution:
  enrich: false
  max_workers: 5
  total_retries: 3
  debug: true

harmonization:
  id_column: "_id"

export:
  output_dir: "results/protein_antimicrobial_reviewed"
  format: csv
  include_metadata: true
  include_summary: true
  manifest_file: "metadata.json"
  summary_file: "run_summary.yml"
```

### Workflow Interface (Automated Data Collection Workflows)

The **Workflow** interface runs reproducible data acquisition workflows across the current biological modalities: proteins, compounds, and interactions. It supports a query-first run and a labeled query-composition run without introducing a general pipeline language.

#### Overview

Workflows support:
- Multiple modalities: `protein`, `compound`, `interaction`
- Two execution modes: `query_first`, `query_composition`
- Optional enrichment through existing cross-reference support
- Retries and multi-threaded API calls
- Export formats: `csv`, `json`, `xml`, or `parquet`.
- `metadata.json` for detailed technical metadata
- `run_summary.yml` for a compact execution report

The validated compound workflow is ChEMBL activity retrieval with UniProt target mapping. PubChem remains available through its database interface, but it is not part of the validated YAML compound workflow.

#### Modalities

| Modality | Description | Primary Data |
|----------|-------------|--------------|
| **protein** | Protein sequences and properties | Temperature, activity data, sequences |
| **compound** | Chemical compounds and bioactivity | IC50, binding affinity, activity |
| **interaction** | Protein interactions | Network data, interaction strength |

#### Modes

In YAML, set the execution mode with `dataset.mode`. In the CLI, use `--mode` or `-d`.

| Mode | Use Case | Query Format |
|------|----------|--------------|
| **query_first** | Single query for the selected modality | Simple query string (e.g., `temperature:*`) |
| **query_composition** | Multiple labeled queries for comparison or grouping | Comma-separated labeled queries (e.g., `query1=label1,query2=label2`) |

#### Command Structure

```bash
bioseq-dl workflow run [OPTIONS]
bioseq-dl workflow validate CONFIG.yml
```

##### Required Options

- `-o, --output TEXT`: Output directory for results
- `-m, --modality TEXT`: Data modality (`protein`, `compound`, `interaction`)
- `-d, --mode TEXT`: Workflow mode (`query_first`, `query_composition`)
- `-q, --query TEXT`: Query or list of queries

##### Optional Options

- `-e, --export-format TEXT`: Export format (`csv`, `json`, `xml`, `parquet`; default `csv`)
- `--enrich/--no-enrich`: Enable or disable data enrichment
- `-w, --max-workers INTEGER`: Number of worker threads for API calls
- `-r, --total-retries INTEGER`: Retry attempts for failed API calls
- `--chembl-pages-to-fetch INTEGER`: ChEMBL pages to fetch (`-1` for all pages, positive values to cap)
- `--uniprot-timeout FLOAT`: Timeout in seconds for UniProt API requests
- `--include-isoform/--no-include-isoform`: Include or exclude UniProt isoforms
- `--debug`: Enable debug logging

#### Example 1: Query First Mode - Protein Temperature Data

Search for proteins with temperature information and export the workflow result:

```bash
bioseq-dl workflow run \
  -o result \
  -q "temperature:*" \
  --modality "protein" \
  --mode "query_first" \
  -w 5 \
  -r 1 \
  --debug
```

**What happens:**
1. Executes the UniProt-compatible query through the current protein workflow
2. Optionally enriches results if enrichment is enabled and supported fields are requested
3. Exports tabular results in the selected format
4. Writes `metadata.json` when metadata export is enabled
5. Writes `run_summary.yml` when summary export is enabled

**Output files:**
```
result/
|-- uniprot_results.csv
|-- metadata.json
`-- run_summary.yml
```

#### Example 2: Query Composition Mode - Comparative Analysis

Compare proteins at different temperature optima using labeled queries:

```bash
bioseq-dl workflow run \
  -o workflow_test \
  -q "temperature:99=temp_99,temperature:98=temp_98" \
  --modality "protein" \
  --mode "query_composition" \
  --debug
```

**What happens:**
1. Executes two labeled UniProt-compatible queries: one for temperature=99, one for temperature=98
2. Adds the query label (`temp_99`, `temp_98`) to exported records
3. Writes the combined result file plus metadata and summary files

**Query syntax:**
- Use `=` or `|` as delimiter: `query=label` or `query|label`
- Separate multiple labeled queries with commas: `query1=label1,query2=label2,query3=label3`

**Output structure:**
```
result/
|-- uniprot_results.csv
|-- metadata.json
`-- run_summary.yml
```

**Use case:** Compare protein properties, identify temperature-dependent characteristics, or study differential protein behavior under different conditions.

#### Example 3: Query Composition Mode - Compound Bioactivity

Classify compounds by bioactivity levels (IC50 ranges):

```bash
bioseq-dl workflow run \
  -o workflow_compound \
  -q "ic50:10-50=active,ic50:50-100=inactive" \
  --modality "compound" \
  --mode "query_composition" \
  --debug
```

**What happens:**
1. Performs ChEMBL activity retrieval with UniProt target mapping for activity records in different IC50 ranges
2. Creates two labeled datasets: `active` (`standard_value` 10-50) and `inactive` (`standard_value` 50-100)
3. Enforces `standard_type = IC50` and numeric `standard_value` filtering after retrieval
4. Preserves `standard_units` when ChEMBL returns it, without constraining units to nM
5. Writes ChEMBL activity results and available UniProt target-mapping output

**Output files:**
```
workflow_compound/
|-- chembl_results.csv
|-- uniprot_results.csv
|-- metadata.json
`-- run_summary.yml
```

**Use case:** Compound activity grouping and target-aware bioactivity dataset construction.

#### Output Files and Enrichment

Workflows generate two main types of output:

1. **Main Results** (`*_results.csv|json|xml|parquet`): retrieved workflow results
2. **Enrichment Data** (`{database}_{endpoint}.csv|json|xml|parquet`): cross-referenced data from other databases when enrichment produces output

If `harmonization.id_column` is set, exported tabular files receive a deterministic ID column when that column is not already present. The original in-memory tabular objects and raw API outputs are not modified.

`metadata.json` contains existing workflow metadata, the original descriptor sections, normalized executable values, generated output files, and calculated reporting metrics. `run_summary.yml` contains dataset and query information, execution status, start and finish times, duration, export settings, output file names, row and column counts for tabular outputs, and common reporting metrics when they can be calculated. The summary status reflects actual execution: `success` for clean runs, `completed_with_errors` when outputs exist but metadata records errors, and `failed` when execution fails or a primary fetch error leaves no real result output.

#### Advanced Options

**Multi-threading and Performance:**
```bash
bioseq-dl workflow run \
  -o result \
  -q "temperature:*" \
  -m "protein" \
  --mode "query_first" \
  -w 10 \
  -r 3
```
- `-w 10`: Use 10 worker threads (faster, higher API load)
- `-r 3`: Retry failed requests up to 3 times (more resilient)

#### Typical Workflow Scenarios

| Scenario | Modality | Mode | Example Query |
|----------|----------|------|---------------|
| Find all thermophilic proteins | protein | query_first | `temperature:*` |
| Compare two temperature optima | protein | query_composition | `temperature:20=temp_low,temperature:80=temp_high` |
| Classify compounds by activity | compound | query_composition | `ic50:10-50=active,ic50:50-100=inactive` |
| Fetch IC50 activity records | compound | query_first | `ic50:<1000` |

---

### Programmatic API

**Example - Using the UniProt interface:**

You can also use the Python API to interact with the tool. Here's an example of how to use the UniProt interface:
```python
from bioseq_dl import UniprotInterface
import polars as pl

df = pl.DataFrame({
    "id": [1, 2, 3],
    "accession": ["A1L3X0", "A0JNC4", "A2RUC4"]
})

uniprot = UniprotInterface()
results, _ = uniprot.download_batch(
    df,
    id_column="accession",
    auto_db=False,
    from_db="UniProtKB_AC-ID",
    to_db="UniProtKB",
    batch_size=100
)
results_df, _ = uniprot.parse(results, None)
print(results_df)
```

**Example - Enriching results with other databases:**

An enricher module is also available to enrich your data with cross references. Here's an example for a given results_df from UniProt:
```python
from bioseq_dl.core.crossref_enricher import CrossRefEnricher, EndpointSpec

specs = [
    EndpointSpec(database="alphafold", endpoint="prediction"),
    EndpointSpec(database="pdb", endpoint="entry"),
]

enricher = CrossRefEnricher(specs)
concat_df, _ = enricher.enrich(results_df, concat_results=True)
```
This will facilitate the enrichment of your data with information from multiple databases.

---


# Configuration

## Credentials and environment variables

Credentials must be provided through explicit arguments or environment variables.

Credentials can be provided in this order of precedence:
1. Explicit CLI arguments or constructor parameters
2. Environment variables (including values loaded from a .env file)

Create a `.env` file in one of these locations:
- Path specified by `BIOSEQ_DL_ENV_FILE`
- Project working directory (`.env`)
- `~/.config/bioseq_dl/.env` or a per-interface config directory (e.g., `~/.config/bioseq_dl/biogrid/.env`)

Supported environment variables:
- `BIOSEQ_DL_BIOGRID_API_KEY` (legacy: `BIOGRID_API_KEY`, `biogrid_api_key`)
- `BIOSEQ_DL_BRENDA_EMAIL` (legacy: `BRENDA_EMAIL`)
- `BIOSEQ_DL_BRENDA_PASSWORD` (legacy: `BRENDA_PASSWORD`)
- `BIOSEQ_DL_REFSEQ_EMAIL` (legacy: `NCBI_EMAIL`, `ENTREZ_EMAIL`)

Notes:
- Credentials come only from environment variables or a `.env` file — never from
  packaged config.
- Do not commit `.env` files to version control.
- A safe template is available at `bioseq_dl/config/.env.example`.

Configuration ships **inside the package** (`bioseq_dl/config/<api>/`) and is loaded
from there automatically — no setup step, no copying to `~/.config`. The relevant
files per API are:

- `fields.yml` — field-extraction maps (which API-response fields become output
  columns). These are **library internals**: loaded from package resources and not
  user-overridable (editing them would break parsing). Example
  (`alphafold/fields.yml`):
  ```yaml
  prediction:
    entry: entryId
    gene: gene
    tax_id: taxId
    organism: organismScientificName
    is_reviewed: isReviewed
    is_reference: isReferenceProteome
  ```
  Keys are the endpoint names; under each, `output_column: api.response.path`.

The only user-facing configuration is **credentials**, supplied via `BIOSEQ_DL_*`
environment variables or a `.env` file (template: `bioseq_dl/config/.env.example`).
Download locations are set per call via the interface `output_dir` argument.


## To-do List

- [ ] Improve API example notebooks
- [ ] Expand README examples as additional workflows are validated
- [x] Document `.env` credential loading
- [x] Document YAML workflow descriptors
- [x] Add logging system

## Future Features

- [ ] Automatic caching and offline mode
- [ ] Integration with external ML workflows

## Contributing

Issues and pull requests should keep the documented workflow surface aligned with implemented and tested behavior.

## License

This project is licensed under the **GNU General Public License v2 (GPLv2)**, matching the project metadata in `pyproject.toml`.

## Acknowledgements

Some modules are based on:
- [UniProt API](https://www.uniprot.org/help/api)
- [UniProt ID Mapping](https://www.uniprot.org/help/id_mapping)
- [AlphaFold Database](https://alphafold.ebi.ac.uk)
