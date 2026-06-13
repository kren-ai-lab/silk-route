import os
from pathlib import Path

from platformdirs import user_cache_dir, user_config_dir

from bioseq_dl.core.dbconfig import DBConfig

POLLING_INTERVAL = 3

APP_NAME = "bioseq_dl"

DATABASES = {
    "alphafold_ids": "AlphaFoldDB",
    "biogrid_ids": "BioGRID",
    "brenda_ids": "BRENDA",
    "go_terms": "GO",
    "chembl_ids": "ChEMBL",
    "interpro_ids": "InterPro",
    "kegg_ids": "KEGG",
    "panther_ids": "PANTHER",
    "pathwaycommons_ids": "PathwayCommons",
    "pdb_ids": "PDB",
    "pfam_ids": "Pfam",
    "pride_ids": "PRIDE",
    "reactome_ids": "Reactome",
    "refseq_ids": "RefSeq",
    "rhea_ids": "Rhea",
    "chebi_ids": "ChEBI",
    "sabiork_ids": "SABIO-RK",
    "string_ids": "STRING",
}

# Platform-appropriate cache/config roots (XDG on Linux, ~/Library on macOS,
# %LOCALAPPDATA% on Windows). Overridable via env for tests/CI/custom layouts.
BASE_CACHE_DIR = Path(os.getenv("BIOSEQ_DL_CACHE_DIR") or user_cache_dir(APP_NAME))
BASE_BLAST_DB_DIR = BASE_CACHE_DIR / "blast_db"
BASE_CONFIG_DIR = Path(os.getenv("BIOSEQ_DL_CONFIG_DIR") or user_config_dir(APP_NAME))

ALPHAFOLD = DBConfig(
    API_URL="https://alphafold.ebi.ac.uk/api/",
    CACHE_DIR=os.path.join(BASE_CACHE_DIR, "alphafold"),
    CONFIG_DIR=os.path.join(BASE_CONFIG_DIR, "alphafold"),
)

BIODBNET = DBConfig(
    API_URL="https://biodbnet.abcc.ncifcrf.gov/webServices/rest.php/biodbnetRestApi.json",
    CACHE_DIR=os.path.join(BASE_CACHE_DIR, "biodbnet"),
    CONFIG_DIR=os.path.join(BASE_CONFIG_DIR, "biodbnet"),
)

BIOGRID = DBConfig(
    API_URL="https://webservice.thebiogrid.org/",
    CACHE_DIR=os.path.join(BASE_CACHE_DIR, "biogrid"),
    CONFIG_DIR=os.path.join(BASE_CONFIG_DIR, "biogrid"),
)

BRENDA = DBConfig(
    API_URL="https://www.brenda-enzymes.org/soap/brenda_zeep.wsdl",
    CACHE_DIR=os.path.join(BASE_CACHE_DIR, "brenda"),
    CONFIG_DIR=os.path.join(BASE_CONFIG_DIR, "brenda"),
)

CHEMBL = DBConfig(
    API_URL="https://www.ebi.ac.uk/chembl/api/data/",
    CACHE_DIR=os.path.join(BASE_CACHE_DIR, "chembl"),
    CONFIG_DIR=os.path.join(BASE_CONFIG_DIR, "chembl"),
)

CHEBI = DBConfig(
    # API_URL="https://www.ebi.ac.uk/chebi/beta/api/public/", # Old API, deprecated
    API_URL="https://www.ebi.ac.uk/chebi/backend/api/public/",
    CACHE_DIR=os.path.join(BASE_CACHE_DIR, "chebi"),
    CONFIG_DIR=os.path.join(BASE_CONFIG_DIR, "chebi"),
)

GENONTOLOGY = DBConfig(
    API_URL="https://api.geneontology.org/api/",
    CACHE_DIR=os.path.join(BASE_CACHE_DIR, "go"),
    CONFIG_DIR=os.path.join(BASE_CONFIG_DIR, "go"),
)

KEGG = DBConfig(
    API_URL="https://rest.kegg.jp/",
    CACHE_DIR=os.path.join(BASE_CACHE_DIR, "kegg"),
    CONFIG_DIR=os.path.join(BASE_CONFIG_DIR, "kegg"),
)

PANTHER = DBConfig(
    API_URL="https://pantherdb.org/services/oai/pantherdb/",
    CACHE_DIR=os.path.join(BASE_CACHE_DIR, "panther"),
    CONFIG_DIR=os.path.join(BASE_CONFIG_DIR, "panther"),
)

PATHWAYCOMMONS = DBConfig(
    API_URL="https://www.pathwaycommons.org/pc2/v2/",
    CACHE_DIR=os.path.join(BASE_CACHE_DIR, "pathwaycommons"),
    CONFIG_DIR=os.path.join(BASE_CONFIG_DIR, "pathwaycommons"),
)

PDB = DBConfig(
    API_URL="https://data.rcsb.org/rest/v1/core/",
    STRUCTURE_URL="https://files.rcsb.org/download/",
    CACHE_DIR=os.path.join(BASE_CACHE_DIR, "pdb"),
    CONFIG_DIR=os.path.join(BASE_CONFIG_DIR, "pdb"),
)

PRIDE = DBConfig(
    API_URL="https://www.ebi.ac.uk/pride/ws/archive/v3/",
    CACHE_DIR=os.path.join(BASE_CACHE_DIR, "pride"),
    CONFIG_DIR=os.path.join(BASE_CONFIG_DIR, "pride"),
)

PUBCHEM = DBConfig(
    API_URL="https://pubchem.ncbi.nlm.nih.gov/rest/",
    CACHE_DIR=os.path.join(BASE_CACHE_DIR, "pubchem"),
    CONFIG_DIR=os.path.join(BASE_CONFIG_DIR, "pubchem"),
)

REACTOME = DBConfig(
    API_URL="https://reactome.org/ContentService/",
    CACHE_DIR=os.path.join(BASE_CACHE_DIR, "reactome"),
    CONFIG_DIR=os.path.join(BASE_CONFIG_DIR, "reactome"),
)

RHEA = DBConfig(
    API_URL="https://www.rhea-db.org/",
    CACHE_DIR=os.path.join(BASE_CACHE_DIR, "rhea"),
    CONFIG_DIR=os.path.join(BASE_CONFIG_DIR, "rhea"),
)

INTERPRO = DBConfig(
    API_URL="https://www.ebi.ac.uk:443/interpro/api/",
    CACHE_DIR=os.path.join(BASE_CACHE_DIR, "interpro"),
    CONFIG_DIR=os.path.join(BASE_CONFIG_DIR, "interpro"),
)

SABIORK = DBConfig(
    API_URL="https://sabiork.h-its.org/sabioRestWebServices/",
    CACHE_DIR=os.path.join(BASE_CACHE_DIR, "sabiork"),
    CONFIG_DIR=os.path.join(BASE_CONFIG_DIR, "sabiork"),
)

STRING = DBConfig(
    API_URL="https://string-db.org/api/",
    CACHE_DIR=os.path.join(BASE_CACHE_DIR, "string"),
    CONFIG_DIR=os.path.join(BASE_CONFIG_DIR, "string"),
)

REFSEQ = DBConfig(
    CACHE_DIR=os.path.join(BASE_CACHE_DIR, "refseq"), CONFIG_DIR=os.path.join(BASE_CONFIG_DIR, "refseq")
)

UNIPROT = DBConfig(
    API_URL="https://rest.uniprot.org",
    CACHE_DIR=os.path.join(BASE_CACHE_DIR, "uniprot"),
    CONFIG_DIR=os.path.join(BASE_CONFIG_DIR, "uniprot"),
)
