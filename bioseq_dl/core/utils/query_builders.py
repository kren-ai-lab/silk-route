# bioseq_dl/core/utils/query_builders.py
"""
An important part to build the cross-reference queries is
the "query builders", which are functions that take a row of
a DataFrame, identifies if the fields required for the
query are present, and returns a list of query parameters
to be used in the corresponding API call.
"""

import pandas as pd
import numpy as np
import ast

from bioseq_dl import (
    AlphafoldInterface,
    BioGRIDInterface,
    BioDBNetInterface,
    BrendaInterface,
    ChEMBLInterface,
    ChEBIInterface,
    GenOntologyInterface,
    InterproInterface,
    KEGGInterface,
    PantherInterface,
    PathwayCommonsInterface,
    PDBInterface,
    PubChemInterface,
    ReactomeInterface,
    RheaInterface,
    RefSeqInterface,
    SabiorkInterface,
    StringInterface
)


INTERFACE_CLASSES = {
    "alphafold": AlphafoldInterface,
    "biogrid": BioGRIDInterface,
    "biodbnet": BioDBNetInterface,
    "brenda": BrendaInterface,
    "chembl": ChEMBLInterface,
    "chebi": ChEBIInterface,
    "go": GenOntologyInterface,
    "interpro": InterproInterface,
    "kegg": KEGGInterface,
    "panther": PantherInterface,
    "pathwaycommons": PathwayCommonsInterface,
    "pdb": PDBInterface,
    "pubchem": PubChemInterface,
    "reactome": ReactomeInterface,
    "rhea": RheaInterface,
    "refseq": RefSeqInterface,
    "sabio-rk": SabiorkInterface,
    "string": StringInterface
}

##########################################
# Helper functions
###########################################

def to_str_list(value):
    """
    Normalize a cell value into a clean list[str].
    Handles: None/NaN, scalar strings, JSON-like strings ('[a,b]'),
    lists/tuples/ndarrays, and returns a list of non-empty strings.
    """
    # Missing
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    # Numpy array -> list
    if isinstance(value, np.ndarray):
        value = value.tolist()
    # Already list/tuple
    if isinstance(value, (list, tuple)):
        return [str(x).strip() for x in value if str(x).strip()]
    # String cases
    if isinstance(value, str):
        txt = value.strip()
        if not txt:
            return []
        # Try JSON/py-literal list
        if txt.startswith("[") and txt.endswith("]"):
            try:
                parsed = ast.literal_eval(txt)
                if isinstance(parsed, (list, tuple)):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except Exception:
                pass
        # Fallback: single id
        return [txt]
    # Fallback: scalar -> list with one string
    return [str(value).strip()] if str(value).strip() else []

##########################################
# Query Builders
###########################################
QUERY_BUILDERS = {}

def register_query_builder(database, method, option=None):
    """
    Registra una función constructora de queries (query builder) en QUERY_BUILDERS.

    Args:
        database (str): Nombre de la base de datos (e.g., 'biodbnet').
        method (str): Método/endpoint principal (e.g., 'db2db').
        option (str, optional): Subopción del endpoint, si aplica (e.g., 'full', 'summary').

    Uso:
        @register_query_builder("biodbnet", "db2db")
        def build_biodbnet_db2db_query(...):
            ...

        @register_query_builder("uniprot", "search", "reviewed")
        def build_uniprot_search_reviewed_query(...):
            ...
    """
    def decorator(func):
        key = "_".join([part for part in (database, method, option) if part])
        QUERY_BUILDERS[key] = func
        return func
    return decorator

def get_query_builder(database, method, option=None):
    """
    Obtiene el query builder registrado para una base de datos y método dados.
    """
    key = "_".join([part for part in (database, method, option) if part])
    builder = QUERY_BUILDERS.get(key)
    if builder is None:
        raise ValueError(f"No query builder registered for endpoint '{key}'")
    return builder

@register_query_builder("alphafold", "prediction")
def build_query_alphafold_prediction(row, params):
    alphafold_ids = to_str_list(row.get("alphafold_ids"))
    if alphafold_ids:
        return alphafold_ids
    else:
        return []


@register_query_builder("biodbnet", "db2db")
def build_query_biodbnet_db2db(row, params):
    genes = to_str_list(row.get("gene_primary"))
    organism = to_str_list(row.get("organism_id"))[0]
    if genes and organism:
        return [{
            "inputValues": genes,
            "taxonId": organism,
            **params
        }]
    else:
        return []

@register_query_builder("biodbnet", "getpathways")
def build_query_biodbnet_getpathways(row, params):
    organism = to_str_list(row.get("organism_id"))
    if organism:
        return [{
            "taxonId": organism_id,
            **params
        } for organism_id in organism]
    else:
        return []
    

@register_query_builder("biogrid", "interactions")
def build_query_biogrid_interactions(row, params):
    genes = to_str_list(row.get("gene_primary"))
    organism = to_str_list(row.get("organism_id"))[0] if to_str_list(row.get("organism_id")) else None
    biogrid_ids = to_str_list(row.get("biogrid_ids"))

    if genes and organism:
        return [{
            "geneList": genes,
            "taxId": organism,
            **params
        }]
    elif biogrid_ids:
        return [{
            "id": biogrid_id,
            **params
        } for biogrid_id in biogrid_ids]
    else:
        return []


@register_query_builder("brenda", "getKmValue")
@register_query_builder("brenda", "getIc50Value")
@register_query_builder("brenda", "getKcatKmValue")
@register_query_builder("brenda", "getKiValue")
@register_query_builder("brenda", "getPhRange")
@register_query_builder("brenda", "getPhOptimum")
@register_query_builder("brenda", "getPhStability")
@register_query_builder("brenda", "getCofactor")
@register_query_builder("brenda", "getTemperatureOptimum")
@register_query_builder("brenda", "getTemperatureStability")
@register_query_builder("brenda", "getTemperatureRange")
def build_query_brenda(row, params):
    ec_numbers = to_str_list(row.get("ec"))
    if ec_numbers:
        return [{
            "ecNumber": ec,
            "organism": row["organism_name"],
            **params
        } for ec in ec_numbers]
    else:
        return []
    
@register_query_builder("chembl", "activity")
@register_query_builder("chembl", "binding_site")
def build_query_chembl(row, params):
    chembl_ids = to_str_list(row.get("chembl_ids"))
    if chembl_ids:
        return [{
            "target_chembl_id": chembl_id,
            **params
        } for chembl_id in chembl_ids]
    else:
        return []
    
@register_query_builder("chebi", "compounds")
def build_query_chebi_compounds(row, params):
    group_of = 5
    chebi_ids = to_str_list(row.get("chebi_ids"))
    if chebi_ids:
        return [{
            "chebi_ids": chebi_ids[i: i + group_of],
            **params
        } for i in range(0, len(chebi_ids), group_of)]
    else:
        return []

@register_query_builder("chebi", "ontology-children")
@register_query_builder("chebi", "ontology-parents")
def build_query_chebi_ontology(row, params):
    chebi_ids = to_str_list(row.get("chebi_ids"))
    if chebi_ids:
        return [{
            "chebi_id": chebi_id,
            **params
        } for chebi_id in chebi_ids]
    else:
        return []

@register_query_builder("go", "bioentity-function")
@register_query_builder("go", "ontology-term")
def build_query_go(row, params):
    go_terms = to_str_list(row.get("go_terms"))
    if go_terms:
        return go_terms
    else:
        return []

@register_query_builder("interpro", "entry")
def build_query_interpro(row, params):
    interpro_ids = to_str_list(row.get("interpro_ids"))
    accession = to_str_list(row.get("accession"))[0]
    organism = to_str_list(row.get("organism_id"))[0]
    if interpro_ids:
        return [{
            "id": interpro_id,
            "db": "InterPro",
            "modifiers": {},
            **params
        } for interpro_id in interpro_ids]
    elif accession and organism:
        # If accession and organism_id are present, use them to fetch InterPro entries
        return [{
            "db": "InterPro",
            "modifiers": {},
            "filters": [
                {
                    "type": "protein",
                    "db": "reviewed",
                    "value": accession
                },
                {
                    "type": "taxonomy",
                    "db": "uniprot",
                    "value": organism
                }
            ],
            **params
        }]
    else:
        return []

@register_query_builder("kegg", "get")
def build_query_kegg(row, params):
    kegg_ids = to_str_list(row.get("kegg_ids"))
    if kegg_ids:
        return [{
            "entries": kegg_id,
            **params
        } for kegg_id in kegg_ids]
    else:
        return []
    
@register_query_builder("panther", "familymsa")
def build_query_panther_familymsa(row, params):
    panther_ids = to_str_list(row.get("panther_ids"))
    if panther_ids:
        return [{
            "family": panther_id,
            **params
        } for panther_id in panther_ids]
    else:
        return []
    
@register_query_builder("panther", "geneinfo")
def build_query_panther_geneinfo(row, params):
    genes = to_str_list(row.get("gene_primary"))
    organism = to_str_list(row.get("organism_id"))

    if genes and organism:
        return [{
            "geneInputList": genes,
            "organism": org,
            **params
        } for org in organism]
    else:
        return []

@register_query_builder("pathwaycommons", "fetch")
def build_query_pathwaycommons_fetch(row, params):
    """
    Build PathwayCommons 'fetch' requests from 'reactome_ids' column.
    Returns a list of query dicts. Empty if no valid IDs.
    """
    ids = to_str_list(row.get("reactome_ids"))
    if not ids:  # no ambiguous truth value here
        return []
    return [{"uri": [rid], **params} for rid in ids]

@register_query_builder("pathwaycommons", "top_pathways")
def build_query_pathwaycommons_top_pathways(row, params):
    genes = to_str_list(row.get("gene_primary"))
    organism = to_str_list(row.get("organism_id"))

    if genes and organism:
        return [{
            "q": gene,
            "organism": organism,
            **params
        } for gene in genes]
    else:
        return []

@register_query_builder("pathwaycommons", "neighborhood")
def build_query_pathwaycommons_neighborhood(row, params):
    accession = row.get("accession") if not pd.isna(row.get("accession")) else None
    organism = to_str_list(row.get("organism_id"))

    if accession and organism:
        return [{
            "source": [accession],
            "organism": organism,
            **params
        }]
    else:
        return []

@register_query_builder("pdb", "entry")
def build_query_pdb(row, params):
    pdb = to_str_list(row.get("pdb_ids"))
    if pdb:
        return pdb
    return []

@register_query_builder("pubchem", "compound", "summary")
def build_query_pubchem_compound_summary(row, params):
    if not pd.isna(row.get("gene_primary")) and not pd.isna(row.get("organism_id")):
        gene_primary = (
            ast.literal_eval(row["gene_primary"])
            if isinstance(row["gene_primary"], str) and row["gene_primary"].startswith("[")
            else [row["gene_primary"]]
        )
        return [{
            "genesymbol": gene,
            "taxid": str(row["organism_id"]),
            **params
        } for gene in gene_primary]
    else:
        return []

@register_query_builder("pubchem", "protein", "summary")
@register_query_builder("pubchem", "protein", "concise")
def build_query_pubchem_protein(row, params):
    if not pd.isna(row.get("accession")):
        return [{
            "accession": row["accession"],
            **params
        }]
    else:
        return []

@register_query_builder("reactome", "data-discover")
def build_query_reactome(row, params):
    ids_raw = to_str_list(row.get("reactome_ids"))
    if ids_raw:
        return ids_raw
    else:
        return []
    

@register_query_builder("rhea", "rhea")
def build_query_rhea(row, params):
    ids_raw = to_str_list(row.get("rhea_ids"))
    if ids_raw:
        return [{
            "query": id,
            **params
        } for id in ids_raw]
    else:
        return []

@register_query_builder("refseq", "protein")
def build_query_refseq(row, params):
    ids_raw = to_str_list(row.get("refseq_ids"))
    if ids_raw:
        return ids_raw
    else:
        return []

@register_query_builder("sabio-rk", "kineticlaws")
def build_query_sabiork_kineticlaws(row, params):
    sabiork_ids = to_str_list(row.get("sabiork_ids"))

    if sabiork_ids:
        return [{
            "UniProtKB_AC": sabiork_id,
            **params
        } for sabiork_id in sabiork_ids]
    else:
        return []

@register_query_builder("string", "interaction_partners")
@register_query_builder("string", "get_string_ids")
def build_query_stringdb(row, params):
    string_ids = to_str_list(row.get("string_ids"))
    organism = to_str_list(row.get("organism_id"))[0]
    gene_primary = to_str_list(row.get("gene_primary"))
    if string_ids and organism:
        return [{
            "identifiers": string_id,
            "species": organism,
            **params
        } for string_id in string_ids]
    elif gene_primary and organism:
        return [{
            "identifiers": gene,
            "species": organism,
            **params
        } for gene in gene_primary]
    else:
        return []
