# BioSeqDownloader

**BioSeqDownloader** is a Python tool designed for downloading biological sequences. Initially focused on Uniprot, this tool aims to scale and support multiple sequences databases, providing a unified and efficient way to retrieve biological data.

Furthermore, it includes functionalities for sequence analysis, such as BLAST searches and multiple sequence alignments, making it a comprehensive solution for bioinformatics workflows.

# Table of Contents

- [Installation](#installation)
    - [Optional Steps for specific functionalities](#optional-steps-for-specific-functionalities)
- [Usage](#usage)
    - [Graphic User Interface (GUI)](#graphic-user-interface-gui)
    - [Command-Line Interface (CLI)](#command-line-interface-cli)
    - [Programmatic API](#programmatic-api)
- [Configuration](#configuration)
- [To do list](#to-do-list)
- [Future Features](#future-features)
- [Acknowledgements](#acknowledgements)

# Installation

To set up **BioSeqDownloader**, follow these steps:

1. Clone the repository:
    ```bash
    git clone https://github.com/ProteinEngineering-PESB2/BioSeqDownloader
    cd BioSeqDownloader
    ```
2. It's hightly recommended to create a virtual environment. Use your preferred method. For example, using `conda`:
    ```bash
    conda create -n bioseqdownloader python
    conda activate bioseqdownloader
    ```
3. Install the package and its dependencies:
    ```bash
    pip install -e .
    ```
4. Optional: To use BLAST functionalities, install BLAST+ from Bioconda:
    ```bash
    conda install -c bioconda blast
    ```
5. Before using the tool, do a first time setup running:
    ```bash
    bioseq-dl
    ```
    This will copy all the config files to your `.config` directory in your home directory.

### Optional Steps for specific functionalities

- To use BioGRID you need to generate an Access Key from [here](https://webservice.thebiogrid.org/). After that you need to add the key to the configuration file located at `~/.config/bioseq_dl/biogrid/init.yml`.
- To use BRENDA you also need to register at [here](https://www.brenda-enzymes.org/login.php). After that you need to add your email and password to the configuration file located at `~/.config/bioseq_dl/brenda/init.yml`.

# Usage
Once installed , you can use the graphical user interface (GUI), command-line interface (CLI), or Python API to download sequences and related data.
Lots of functionalities are available at `bioseq-dl` command. You can check them by running:
```bash
bioseq-dl --help
```

## Graphic User Interface (GUI)
You can launch the GUI using the following command:
```bash
bioseq-dl gui run
```
This will make a local server available at `http://localhost:7560` where you can interactively use the tool.

## Command-Line Interface (CLI)

You can use the CLI to perform various tasks. For example, you can collect data from different databases. Here are some examples:

### To search antimicrobial proteins that have a certain length in UniProt and save the results in a CSV file:
```bash
bioseq-dl collect-data uniprot search-by-query run \
    --query "(length:[50 TO 51]) AND antimicrobial AND reviewed:true" \
    --fields accession,protein_name,gene_primary,sequence,ec \
    --crossref_fields alphafold,pdb \
    --output results.csv
```
### For a given data with other databases IDs (e.g., PDB, AlphaFold, BioGRID, BRENDA), you can retrieve more information using:
```bash
bioseq-dl collect-data uniprot search-crossreferences run \
    --input results.csv \
    --databases alphafold,pdb \
    --out_dir enriched_results
```
Note: This will create a new directory called `structures` where the structure files will be downloaded.

___

### For a given data with unknown UniProt IDs, you can do a BLAST alignment to find the closest sequences in UniProt using:
```bash
bioseq-dl blast-alignment run \
    --database uniprotkb_reviewed \
    --seq-column sequence \
    --input unknown_sequences.csv \ 
    --output blast_results.csv
```
### Alternatively, you can do a uniprot search using:
```bash
bioseq-dl blast-alignment run \
    --database uniprotkb_reviewed \
    --seq-column sequence \
    --input unknown_sequences.csv \ 
    --output blast_results.csv \
    --do-uniprot-search
```

## Programmatic API
You can also use the Python API to interact with the tool. Here's an example of how to use the Uniprot interface:
```python
from bioseq_dl import UniprotInterface
import pandas as pd

df = pd.DataFrame({
    "id": [1, 2, 3],
    "accession": ["A1L3X0", "A0JNC4", "A2RUC4"]
})
uniprot = UniprotInterface()
results = instance.download_batch(
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
___
An enricher module is also available to enrich your data with cross references. Here's an example:
```python
from bioseq_dl.core.crossref_enricher import CrossRefEnricher, EndpointSpec

specs = [
    EndpointSpec(database="alphafold", endpoint="prediction", option=None, params={}),
    EndpointSpec(database="pdb", endpoint="entry", option=None, params={}),
]
enricher = CrossRefEnricher(specs)
concat_df = enricher.enrich(results_df, concat_results=True)
concat_df
```
This will facilitate the enrichment of your data with information from multiple databases.


# Configuration
Configuration files are located in the `.config/bioseq_dl` directory in your home directory. You can modify these files to customize the behavior of the tool.
For every api there is a `fields.yml` file where you can define the fields to be parsed after downloading the data.
For example the config tree should look like this:
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

# To do list
- [ ] Add .env definition in README
- [ ] Add example for blast alignment in examples
- [ ] Polish the other API example notebook
- [ ] Add examples to the main README
- [ ] Add a logging system

# Future Features
- [ ] Make a GUI for the config files

# Acknowledgements
Some of the code is based on the [Uniprot API](https://www.uniprot.org/help/api) and the [Uniprot ID mapping](https://www.uniprot.org/help/id_mapping) service.