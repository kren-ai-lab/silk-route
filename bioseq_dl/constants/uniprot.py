VALID_FIELDS = [
    "accession",
    "protein_name",
    "gene_primary",
    "organism_name",
    "lineage",
    "ec",
    "sequence"
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

DATABASES = {
    "uniprotkb_reviewed": "knowledgebase/complete/uniprot_sprot",
    "uniprotkb_unreviewed": "knowledgebase/complete/uniprot_trembl",
    "uniref100": "uniref/niref100/uniref100",
    "uniref90": "uniref/uniref90/uniref90",
    "uniref50": "uniref/uniref50/uniref50",
}

BASE_URL = "https://ftp.uniprot.org/pub/databases/uniprot/current_release"
