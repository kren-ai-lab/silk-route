import gradio as gr
import pandas as pd
from .components.uniprot_query_search import build_ui as build_uniprot_search_ui
from .components.uniprot_blast_search import build_ui as build_uniprot_blast_search_ui
from .components.databases import build_api_ui
from .interfaces import (
    ALPHAFOLD,
    BIODBNET,
    BIOGRID,
    BRENDA,
    CHEMBL,
    CHEBI,
    GENONTOLOGY,
    INTERPRO,
    KEGG,
    PATHWAYCOMMONS,
    PANTHER,
    PDB,
    PRIDE,
    PUBCHEM,
    REACTOME,
    REFSEQ,
    RHEA,
    STRINGDB
)

# For each database interface there is a dictionary entry with:
# - class: the interface class
# - label: the display name
# - init: a dictionary of initialization parameters
# - methods: a dictionary of methods with their input templates

# Methods can have:
# - input_type: 'atomic' (single string) or 'composite' (multiple fields)
# - inputs: a list of input field definitions
# - multisearch: (optional) if True, allows multiple queries separated by commas
# - options: (optional) for methods with multiple options, each option has its own input template

REGISTRY = {
    "AlphaFold": ALPHAFOLD,
    "BioDBNet": BIODBNET,
    "BioGRID": BIOGRID,
    "Brenda": BRENDA,
    "ChEMBL": CHEMBL,
    "ChEBI": CHEBI,
    "GenOntology": GENONTOLOGY,
    "Interpro": INTERPRO,
    "KEGG": KEGG,
    "PathwayCommons": PATHWAYCOMMONS,
    "Panther": PANTHER,
    "ProteinDataBank": PDB,
    "Pride": PRIDE,
    "PubChem": PUBCHEM,
    "Reactome": REACTOME,
    "RefSeq": REFSEQ,
    "Rhea": RHEA,
    "StringDB": STRINGDB
}

# For every code in the component module, there should be a subtab in the main UI

def build_ui():
    """
    This is the main UI builder.
    At the moment it has two main tabs:
    - APIs: Builds the main interface from the REGISTRY
    - Uniprot search: Builds the Uniprot search and Uniprot BLAST search interfaces
    Returns a Gradio Blocks object.
    """
    with gr.Blocks() as demo:
        with gr.Tab("APIs"):
            for api_name, api_info in REGISTRY.items():
                build_api_ui(api_name, api_info)
        with gr.Tab("Uniprot search"):
            build_uniprot_search_ui()
            build_uniprot_blast_search_ui()

    return demo