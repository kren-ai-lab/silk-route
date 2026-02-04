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
  - [Graphical User Interface (GUI)](#graphical-user-interface-gui)
  - [Command-Line Interface (CLI)](#command-line-interface-cli)
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

### Graphical User Interface (GUI)

Launch the GUI:
```bash
bioseq-dl gui run
```
A local server will be available at [http://localhost:7560](http://localhost:7860), providing an interactive web interface.

---

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

- [ ] GUI for configuration management
- [ ] Automatic caching and offline mode
- [ ] Integration with external ML workflows

## License

This project is licensed under the **MIT License**.

## Acknowledgements

Some modules are based on:
- [UniProt API](https://www.uniprot.org/help/api)
- [UniProt ID Mapping](https://www.uniprot.org/help/id_mapping)
- [AlphaFold Database](https://alphafold.ebi.ac.uk)
