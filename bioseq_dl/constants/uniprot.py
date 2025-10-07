# Constants for UniProt data fields and cross-references
# Only should be added the fields that are available and defined
# in the file bioseq_dl/core/interfaces/uniprot.py at line 187
VALID_FIELDS = [
    "accession",
    "protein_name",
    "ec",
    "organism_name",
    "gene_primary",
    "organism_id",
    "sequence",
    "length",
    "keyword"
]

VALID_CROSS_REF_FIELDS = {
    "alphafold": "alphafold_ids",
    "biogrid": "biogrid_ids",
    "brenda": "brenda_ids",
    "go": "go_terms",
    "chembl": "chembl_ids",
    "interpro": "interpro_ids",
    "kegg": "kegg_ids",
    "panther": "panther_ids",
    "pathwaycommons": "pathwaycommons_ids",
    "pdb": "pdb_ids",
    "pfam": "pfam_ids",
    "pride": "pride_ids",
    "refseq": "refseq_ids",
    "reactome": "reactome_ids",
    "string": "string_ids",
    "rhea": "rhea_ids",
}

# Mapping of cross-reference fields to (field_name, endpoint_name)
# If there is not a uniprot field associated, just use the endpoint name
XREF_MAPPING = {
    "AlphaFold": ("xref_alphafolddb", "alphafold"),
    "BioDBNet": (None, "biodbnet"),
    "BioGRID": (None, "biogrid"),
    "Brenda": ("xref_brenda", "brenda"),
    "ChEMBL": ("xref_chembl", "chembl"),
    "ChEBI": (None, "chebi"),
    "GO": ("go_id", "genontology"),
    "InterPro": ("xref_interpro", "interpro"),
    "KEGG": ("xref_kegg", "kegg"),
    "Panther": ("xref_panther", "panther"),
    "PathwayCommons": ("xref_pathwaycommons", "pathwaycommons"),
    "PDB": ("xref_pdb", "pdb"),
    "PubChem": (None, "pubchem"),
    "Reactome": ("xref_reactome", "reactome"),
    "Rhea": ("rhea", "rhea"),
    #"PFAM": ("xref_pfam", None),
    "RefSeq": ("xref_refseq", "refseq"),
    "StringDB": ("xref_string", "string"),
}

DATABASES = {
    "uniprotkb_reviewed": "knowledgebase/complete/uniprot_sprot",
    "uniprotkb_unreviewed": "knowledgebase/complete/uniprot_trembl",
    "uniref100": "uniref/niref100/uniref100",
    "uniref90": "uniref/uniref90/uniref90",
    "uniref50": "uniref/uniref50/uniref50",
}

BASE_URL = "https://ftp.uniprot.org/pub/databases/uniprot/current_release"
