"""DBConfig instances for all supported databases."""

import os
from pathlib import Path

from platformdirs import user_cache_dir, user_config_dir

from bioseq_dl.core.dbconfig import DBConfig

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
BASE_CACHE_DIR = Path(os.getenv("BIOSEQ_DL_CACHE_DIR") or user_cache_dir(APP_NAME)).expanduser()
BASE_BLAST_DB_DIR = BASE_CACHE_DIR / "blast_db"
BASE_CONFIG_DIR = Path(os.getenv("BIOSEQ_DL_CONFIG_DIR") or user_config_dir(APP_NAME)).expanduser()


def _db(slug: str, api_url: str = "", **extra: str) -> DBConfig:
    """Build a DBConfig with cache/config dirs derived from a single ``slug``."""
    return DBConfig(
        API_URL=api_url,
        CACHE_DIR=str(BASE_CACHE_DIR / slug),
        CONFIG_DIR=str(BASE_CONFIG_DIR / slug),
        **extra,
    )


ALPHAFOLD = _db("alphafold", "https://alphafold.ebi.ac.uk/api/")
BIODBNET = _db("biodbnet", "https://biodbnet.abcc.ncifcrf.gov/webServices/rest.php/biodbnetRestApi.json")
BIOGRID = _db("biogrid", "https://webservice.thebiogrid.org/")
BRENDA = _db("brenda", "https://www.brenda-enzymes.org/soap/brenda_zeep.wsdl")
CHEMBL = _db("chembl", "https://www.ebi.ac.uk/chembl/api/data/")
CHEBI = _db("chebi", "https://www.ebi.ac.uk/chebi/backend/api/public/")
GENONTOLOGY = _db("go", "https://api.geneontology.org/api/")
KEGG = _db("kegg", "https://rest.kegg.jp/")
PANTHER = _db("panther", "https://pantherdb.org/services/oai/pantherdb/")
PATHWAYCOMMONS = _db("pathwaycommons", "https://www.pathwaycommons.org/pc2/v2/")
PDB = _db("pdb", "https://data.rcsb.org/rest/v1/core/", STRUCTURE_URL="https://files.rcsb.org/download/")
PRIDE = _db("pride", "https://www.ebi.ac.uk/pride/ws/archive/v3/")
PUBCHEM = _db("pubchem", "https://pubchem.ncbi.nlm.nih.gov/rest/")
REACTOME = _db("reactome", "https://reactome.org/ContentService/")
RHEA = _db("rhea", "https://www.rhea-db.org/")
INTERPRO = _db("interpro", "https://www.ebi.ac.uk:443/interpro/api/")
SABIORK = _db("sabiork", "https://sabiork.h-its.org/sabioRestWebServices/")
STRING = _db("string", "https://string-db.org/api/")
REFSEQ = _db("refseq")
UNIPROT = _db("uniprot", "https://rest.uniprot.org")
