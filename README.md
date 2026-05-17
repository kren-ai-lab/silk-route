# BioSeqDownloader

**BioSeqDownloader** is a Python-based tool for downloading, analyzing, and enriching biological sequences from multiple databases. Initially focused on **UniProt**, it is designed to scale and support several sources such as **AlphaFold**, **BioGRID**, **BRENDA**, **PDB**, and **KEGG**, providing a unified, reproducible, and efficient way to retrieve biological data.

Additionally, it includes functionalities for **sequence analysis** (e.g., BLAST searches, multiple sequence alignments), making it a comprehensive solution for **bioinformatics workflows**.

### Supported Databases

Currently supported databases include:

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
| PubChem | Chemical molecule database |
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

- Unified access to multiple biological databases.
- Command-Line and Graphical Interfaces.
- Configurable YAML-based field parsing system.
- Cross-database enrichment and mapping (e.g., UniProt ↔ AlphaFold ↔ BioGRID).
- Optional BLAST and multiple sequence alignment capabilities.
- Modular and extensible architecture.

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

4. **Optional:** Install BLAST+ from Bioconda:
   ```bash
   conda install -c bioconda blast
   ```

5. **Run the initial setup:**
   ```bash
   bioseq-dl
   ```
   This will copy the configuration files to `~/.config/bioseq_dl/`.

---

### Optional Steps for Specific Functionalities

| Database | Requirement | Credential Source |
|-----------|--------------|-------------------|
| **BioGRID** | Access Key ([request here](https://webservice.thebiogrid.org/)) | `BIOSEQ_DL_BIOGRID_API_KEY` (or `.env`) |
| **BRENDA** | Email and password ([register here](https://www.brenda-enzymes.org/login.php)) | `BIOSEQ_DL_BRENDA_EMAIL` and `BIOSEQ_DL_BRENDA_PASSWORD` (or `.env`) |

---

### Command Overview
To explore all available commands:
```bash
bioseq-dl --help
```

### Command-Line Interface (CLI)

**Example 1 – Search antimicrobial proteins (length 50–51) in UniProt:**
```bash
bioseq-dl general-collect uniprot search-by-query run \
--query "(length:[50 TO 51]) AND antimicrobial AND reviewed:true" \
--fields accession,protein_name,gene_primary,sequence,ec \
--crossref_fields alphafold,pdb \
--output search_query_test
```

**Example 2 – Search UniProt entries by accession IDs:**
```bash
bioseq-dl general-collect uniprot search-by-ids run \
--input unknown_ids.csv \
--column accession \
--output search_ids_test \
--crossref_fields alphafold
```

**Example 3 – Perform a BLAST alignment against UniProt:**
```bash
bioseq-dl general-collect uniprot search-by-sequences run \
--database uniprotkb_reviewed \
--seq-column sequence \
--min_identity 100.0 \
--input unknown_sequences.csv \
--output search_sequences_test \
--crossref_fields alphafold
```

### Parquet outputs

Commands that export parsed tabular results can write Parquet files when `parquet` is selected as the output format. Parquet export requires the optional Parquet engine installed with the package dependencies.

### Workflow YAML descriptors

BioSeqDownloader supports structured YAML descriptors for reproducible workflow runs. These descriptors define dataset, query, execution, harmonization, export, and reporting information. See [`docs/workflow_yaml.md`](docs/workflow_yaml.md) for the full implemented schema, field behavior, forbidden keys, credential policy, and examples.

Workflow runs can be described with a structured dataset descriptor and executed with:

```bash
bioseq-dl workflow run --config workflow.yml
```

CLI arguments override YAML values, so a descriptor can be reused with a different output directory or export format:

```bash
bioseq-dl workflow run --config workflow.yml -o result_override
bioseq-dl workflow run --config workflow.yml -e csv
```

YAML descriptors use top-level `dataset`, `query`, `resources`, `execution`, `harmonization`, `export`, and `reporting` sections, plus a small allowlist of descriptive integration sections. `dataset.mode` is the workflow execution mode, and the only valid values are `query_first` and `query_composition`. Only part of the descriptor is executable: `dataset.modality`, `dataset.mode`, `query.value`, selected `query` options, supported `execution` options, and `export` options are mapped to the current workflow. `query.value` is the actual API query. `query.description` and `query.filtering_strategy` are descriptive metadata only.

`resources`, allowed domain-specific integration sections, and most harmonization/reporting fields are preserved in `metadata.json` and `run_summary.yml` unless the current workflow already supports that behavior. `execution.merge_results` is descriptor metadata only; it does not currently trigger automatic result merging. Credentials must be provided through `.env` or environment variables, not YAML.

ChEMBL workflow fetches retrieve all available pages by default. In YAML, `execution.chembl_pages_to_fetch: -1` means all pages; a positive value caps the number of pages. ChEMBL `limit` remains records per page, not total records and not a page count.

Allowed top-level descriptor sections are: `dataset`, `query`, `resources`, `execution`, `harmonization`, `export`, `reporting`, `interaction_retrieval`, `activity_retrieval`, `chemical_metadata_integration`, `protein_target_integration`, `temperature_enrichment`, and `cross_source_integration`.

Validated example descriptors are available at `examples/protein-dataset-construction.yml`, `examples/interaction-aware-dataset-construction.yml`, and `examples/compound-dataset-construction.yml`.

```yaml
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

resources:
  primary:
    - uniprot
  integration: []

execution:
  enrich: false
  max_workers: 5
  total_retries: 3
  merge_results: false
  debug: true

harmonization:
  id_column: "_id"
  label_column: null
  sequence_column: "sequence"
  metadata_fields:
    - accession
    - protein_name
    - organism_name
    - sequence

export:
  output_dir: "results/protein_antimicrobial_reviewed"
  format: csv
  include_metadata: true
  include_summary: true
  manifest_file: "metadata.json"
  summary_file: "run_summary.yml"

reporting:
  workflow_execution_time_seconds: null
  retrieved_records: null
  unique_sequences: null
  notes: >
    Values are filled after execution from exported result files and metadata.
```

### Workflow Interface (Automated Data Collection Workflows)

The **Workflow** interface runs reproducible data acquisition workflows across biological modalities: proteins, compounds, and interactions. It supports a query-first run and a labeled query-composition run without introducing a general pipeline language.

#### Overview

Workflows support:
- Multiple modalities: `protein`, `compound`, `interaction`
- Two execution modes: `query_first`, `query_composition`
- Optional enrichment through existing cross-reference support
- Retries and multi-threaded API calls
- Export formats: CSV, JSON, XML, or Parquet. BioSeqDownloader uses pandas DataFrames internally for tabular data, but `dataframe` is not a user-facing export format.
- `metadata.json` for detailed technical metadata
- `run_summary.yml` for a compact execution report

#### Modalities

| Modality | Description | Primary Data |
|----------|-------------|--------------|
| **protein** | Protein sequences and properties | Temperature, activity data, sequences |
| **compound** | Chemical compounds and bioactivity | IC50, binding affinity, activity |
| **interaction** | Protein interactions | Network data, interaction strength |

#### Modes

In YAML, set the execution mode with `dataset.mode`.

| Mode | Use Case | Query Format |
|------|----------|--------------|
| **query_first** | Single, simple query across all available sources | Simple query string (e.g., `temperature:*`) |
| **query_composition** | Multiple labeled queries, combining different sources | Comma-separated labeled queries (e.g., `query1=label1,query2=label2`) |

#### Command Structure

```bash
bioseq-dl workflow run [OPTIONS]
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

Search for proteins with temperature information and retrieve all available data:

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
1. Executes two parallel queries: one for temperature=99, one for temperature=98
2. Each query is labeled (`temp_99`, `temp_98`) for easy tracking
3. Automatically enriches each dataset with protein information from UniProt
4. Compares and combines results in the output directory
5. Tag the results with their respective labels in the uniprot results for easy differentiation

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
1. Performs ChEMBL activity retrieval with UniProt target mapping for compounds with IC50 values in different ranges
2. Creates two labeled datasets: `active` (IC50: 10-50 nM) and `inactive` (IC50: 50-100 nM)
3. Enriches each compound with protein target information from UniProt
4. Enables bioactivity-based classification and drug discovery workflows
5. Compares structure-activity relationships (SAR) across datasets

**Output files:**
```
workflow_compound/
|-- chembl_results.csv
|-- uniprot_results.csv
|-- metadata.json
`-- run_summary.yml
```

**Use case:** Drug discovery, compound screening and classification of bioactive molecules.

#### Output Files and Enrichment

Workflows generate two main types of output:

1. **Main Results** (`uniprot_results.csv|json|xml`): Raw query results
2. **Enrichment Data** (`{database}_{endpoint}.csv|json|xml`): Cross-referenced data from other databases

If `harmonization.id_column` is set, exported tabular files receive a deterministic ID column when that column is not already present. The original in-memory DataFrames and raw API outputs are not modified.

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
| Screen drug candidates | compound | query_first | `chembl_id:*` |

---

### Programmatic API

**Example – Using the UniProt interface:**

You can also use the Python API to interact with the tool. Here's an example of how to use the UniProt interface:
```python
from bioseq_dl import UniprotInterface
import pandas as pd

df = pd.DataFrame({
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

**Example – Enriching results with other databases:**

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
- Credentials are never read from `init.yml`.
- `init.yml` is only for non-sensitive configuration.
- Do not commit `.env` files to version control.
- A safe template is available at `bioseq_dl/config/.env.example` and copied by `bioseq-dl-init`.

Configuration files are stored in:
```
~/.config/bioseq_dl/
```

Each API module includes:
- `init.yml` — non-sensitive settings
- `fields.yml` — field mappings for result parsing

**Example directory tree:**
```
.config/
└── bioseq_dl
    ├── alphafold
    │   ├── init.yml
    │   └── fields.yml
    ├── biogrid
    │   └── fields.yml
    ...
    └── uniprot
        └── fields.yml
```
Where every `fields.yml` file contains the fields to be parsed for that specific API. For example, the `alphafold/fields.yml` file might look like this:
```yaml
prediction:
  entry: entryId
  gene: gene
  tax_id: taxId
  organism: organismScientificName
  is_reviewed: isReviewed
  is_reference: isReferenceProteome
```
Where the main keys are the names of the methods available for that API, and the values are the fields to be parsed. After the method name, the fields are defined as key-value pairs, where the key is the name of the field in the output DataFrame, and the value is the name of the field in the API response.

The `init.yml` file contains the configuration for that specific API. For example, the `alphafold/init.yml` file might look like this:
```yaml
download_folder: /path/to/download/folder
```


## To-do List

- [ ] Add `.env` file documentation
- [ ] Add BLAST alignment examples
- [ ] Improve API example notebooks
- [ ] Expand README examples
- [x] Add logging system

## Future Features

- [ ] Automatic caching and offline mode
- [ ] Integration with external ML workflows

## License

This project is licensed under the **MIT License**.

## Acknowledgements

Some modules are based on:
- [UniProt API](https://www.uniprot.org/help/api)
- [UniProt ID Mapping](https://www.uniprot.org/help/id_mapping)
- [AlphaFold Database](https://alphafold.ebi.ac.uk)
