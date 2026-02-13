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

| Database | Requirement | Configuration File |
|-----------|--------------|--------------------|
| **BioGRID** | Access Key ([request here](https://webservice.thebiogrid.org/)) | `~/.config/bioseq_dl/biogrid/init.yml` |
| **BRENDA** | Email and password ([register here](https://www.brenda-enzymes.org/login.php)) | `~/.config/bioseq_dl/brenda/init.yml` |

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

### Workflow Interface (Automated Data Collection Workflows)

The **Workflow** interface allows you to run **pre-configured, automated data collection workflows** that handle complex, multi-step queries across different data modalities (proteins, compounds, interactions). Workflows automatically handle enrichment and cross-database linking.

#### Overview

Workflows simplify the process of collecting and enriching biological data by:
- Supporting multiple **modalities**: proteins, compounds, interactions
- Offering two **modes** of operation: single-query or multi-query composition
- Automatically enriching results with cross-references
- Handling retries and multi-threaded API calls
- Exporting results in multiple formats (CSV, JSON, XML)

#### Modalities

| Modality | Description | Primary Data |
|----------|-------------|--------------|
| **protein** | Protein sequences and properties | Temperature, activity data, sequences |
| **compound** | Chemical compounds and bioactivity | IC50, binding affinity, activity |
| **interaction** | Protein-protein interactions | Network data, interaction strength |

#### Modes

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
- `-d, --mode TEXT`: Execution mode (`query_first`, `query_composition`)
- `-q, --query TEXT`: Query or list of queries

##### Optional Options

- `-e, --export-format TEXT`: Export format (`dataframe`, `json`, `xml`) — Default: `dataframe`
- `--enrich/--no-enrich`: Enable/disable data enrichment — Default: `True`
- `-w, --max-workers INTEGER`: Number of worker threads for API calls — Default: `5`
- `-r, --total-retries INTEGER`: Retry attempts for failed API calls — Default: `3`
- `--debug`: Enable debug logging

#### Example 1: Query First Mode – Protein Temperature Data

Search for proteins with temperature information and retrieve all available data:

```bash
bioseq-dl workflow run \
  -o result \
  -q "temperature:*" \
  -m "protein" \
  -d "query_first" \
  -w 5 \
  -r 1 \
  --debug
```

**What happens:**
1. Searches all available protein databases for entries with temperature data
2. Collects results from BRENDA, UniProt, and other temperature-related sources
3. Automatically enriches results with AlphaFold predictions, PDB structures, and UniProt annotations
4. Exports results as CSV files in the `result/` directory
5. Creates a `metadata.json` file with execution details

**Output files:**
```
result/
├── {database}_{endpoint}.csv   # Cross-referenced data (e.g., BRENDA)
├── uniprot_results.csv         # UniProt enrichment data
├── metadata.json               # Execution metadata
```

#### Example 2: Query Composition Mode – Comparative Analysis

Compare proteins at different temperature optima using labeled queries:

```bash
bioseq-dl workflow run \
  -o workflow_test \
  -q "temp_99=temperature:99,temp_98=temperature:98" \
  -m "protein" \
  -d "query_composition" \
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
├── {database}_{endpoint}.csv   # Cross-referenced data (e.g., BRENDA)
├── uniprot_results.csv         # UniProt enrichment data
├── metadata.json               # Execution metadata
```

**Use case:** Compare protein properties, identify temperature-dependent characteristics, or study differential protein behavior under different conditions.

#### Example 3: Query Composition Mode – Compound Bioactivity

Classify compounds by bioactivity levels (IC50 ranges):

```bash
bioseq-dl workflow run \
  -o workflow_compound \
  -q "ic50:10-50=active,ic50:50-100=inactive" \
  -m "compound" \
  -d "query_composition" \
  --debug
```

**What happens:**
1. Searches compound databases (ChEMBL, PubChem, etc.) for compounds with IC50 values in different ranges
2. Creates two labeled datasets: `active` (IC50: 10-50 nM) and `inactive` (IC50: 50-100 nM)
3. Enriches each compound with protein target information from UniProt
4. Enables bioactivity-based classification and drug discovery workflows
5. Compares structure-activity relationships (SAR) across datasets

**Output files:**
```
workflow_compound/
├── chembl_results.csv          # Compound data from ChEMBL
├── uniprot_results.csv         # UniProt data
└── metadata.json               # Execution metadata
```

**Use case:** Drug discovery, compound screening and classification of bioactive molecules.

#### Output Files and Enrichment

Workflows generate two main types of output:

1. **Main Results** (`uniprot_results.csv|json|xml`): Raw query results
2. **Enrichment Data** (`{database}_{endpoint}.csv|json|xml`): Cross-referenced data from other databases

#### Advanced Options

**Multi-threading and Performance:**
```bash
bioseq-dl workflow run \
  -o result \
  -q "temperature:*" \
  -m "protein" \
  -d "query_first" \
  -w 10 \
  -r 3
```
- `-w 10`: Use 10 worker threads (faster, higher API load)
- `-r 3`: Retry failed requests up to 3 times (more resilient)

#### Typical Workflow Scenarios

| Scenario | Modality | Mode | Example Query |
|----------|----------|------|---------------|
| Find all thermophilic proteins | protein | query_first | `temperature:*` |
| Compare two temperature optima | protein | query_composition | `temp_low=temperature:20,temp_high=temperature:80` |
| Classify compounds by activity | compound | query_composition | `active=ic50:10-50,inactive=ic50:50-100` |
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

Configuration files are stored in:
```
~/.config/bioseq_dl/
```

Each API module includes:
- `init.yml` — connection and authentication settings
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
Where the main keys are the names of the methods available for that API, and the values are the fields to be parsed. After the method name, the fields are defined as key-value pairs, where the key is the name of the field in the output dataframe, and the value is the name of the field in the API response.

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
