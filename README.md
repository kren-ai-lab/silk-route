# BioSeqDownloader

**BioSeqDownloader** is a Python tool designed for downloading biological sequences. Initially focused on Uniprot, this tool aims to scale and support multiple sequences databases, providing a unified and efficient way to retrieve biological data.

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
4. Optional: Install blast for sequence alignment:
    ```bash
    conda install -c bioconda blast
    ```
5. Befure using the tool, do a first time setup running:
    ```bash
    bioseq-dl
    ```
    This will copy all the config files to your `.config` directory in your home directory.

### Optional Steps for specific functionalities

- To use BioGRID...
- To use BRENDA you also need to register and use your email and password in the .env file.

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


## Downloading UniProt Data using IDS

To retrieve data for a given list of UniProt IDs, you can use the command:
```bash
bioseq-dl uniprot-search-ids 
```

This example searches for reviewed antibacterial proteins and saves the results in a CSV file. You can customize the query and fields to suit your research needs.

# Configuration
Configuration files are located in the `.config/bioseq_dl` directory in your home directory. You can modify these files to customize the behavior of the tool.
For every api there is a `fields.yml` file where you can define the fields to be parsed after downloading the data.
For example the config tree should look like this:
```
.config/
└── bioseq_dl
    ├── alphafold
    │   └── fields.yml
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


# To do list
- [x] Add .env definition in README
- [x] Add example for blast aligment in examples
- [x] Polish the othe API example notebook
- [x] Add examples to the main README

# Aknowledgements
Some of the code is based on the [Uniprot API](https://www.uniprot.org/help/api) and the [Uniprot ID mapping](https://www.uniprot.org/help/id_mapping) service.