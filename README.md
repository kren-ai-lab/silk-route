# BioSeqDownloader

**BioSeqDownloader** is a Python-based tool for downloading, analyzing, and enriching biological sequences from multiple databases. Initially focused on **UniProt**, it is designed to scale and support several sources such as **AlphaFold**, **BioGRID**, **BRENDA**, **PDB**, and **KEGG**, providing a unified, reproducible, and efficient way to retrieve biological data.

Additionally, it includes functionalities for **sequence analysis** (e.g., BLAST searches, multiple sequence alignments), making it a comprehensive solution for **bioinformatics workflows**.

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
   conda create -n bioseqdownloader python
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
A local server will be available at [http://localhost:7560](http://localhost:7560), providing an interactive web interface.

---

### Command-Line Interface (CLI)

**Example 1 – Search antimicrobial proteins (length 50–51) in UniProt:**
```bash
bioseq-dl collect-data uniprot search-by-query run \
--query "(length:[50 TO 51]) AND antimicrobial AND reviewed:true" \
--fields accession,protein_name,gene_primary,sequence,ec \
--crossref_fields alphafold,pdb \
--output results.csv
```

**Example 2 – Enrich existing data with AlphaFold and PDB cross-references:**
```bash
bioseq-dl collect-data uniprot search-crossreferences run \
--input results.csv \
--databases alphafold,pdb \
--out_dir enriched_results
```

**Example 3 – Perform a BLAST alignment against UniProt:**
```bash
bioseq-dl blast-alignment run \
--database uniprotkb_reviewed \
--seq-column sequence \
--input unknown_sequences.csv \
--output blast_results.csv
```

---

### Programmatic API

**Example – Using the UniProt interface:**
```python
from bioseq_dl import UniprotInterface
import pandas as pd

df = pd.DataFrame({
    "id": [1, 2, 3],
    "accession": ["A1L3X0", "A0JNC4", "A2RUC4"]
})

uniprot = UniprotInterface()
results = uniprot.download_batch(
    df,
    id_column="accession",
    auto_db=False,
    from_db="UniProtKB_AC-ID",
    to_db="UniProtKB",
    batch_size=100
)
results_df = uniprot.parse_results(results, None)
print(results_df)
```

**Example – Enriching results with other databases:**
```python
from bioseq_dl.core.crossref_enricher import CrossRefEnricher, EndpointSpec

specs = [
    EndpointSpec(database="alphafold", endpoint="prediction"),
    EndpointSpec(database="pdb", endpoint="entry"),
]

enricher = CrossRefEnricher(specs)
concat_df = enricher.enrich(results_df, concat_results=True)
```

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

## Contributing

Contributions are welcome! To contribute:
1. Fork the repository
2. Create a new branch (`feature/my-feature`)
3. Commit and push your changes
4. Open a Pull Request

## License

This project is licensed under the **MIT License**.

## Acknowledgements

Some modules are based on:
- [UniProt API](https://www.uniprot.org/help/api)
- [UniProt ID Mapping](https://www.uniprot.org/help/id_mapping)
- [AlphaFold Database](https://alphafold.ebi.ac.uk)
