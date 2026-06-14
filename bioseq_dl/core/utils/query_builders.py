# bioseq_dl/core/utils/query_builders.py
"""Query builders for cross-reference queries.

These functions take a row of a DataFrame, check whether the fields required for the
query are present, and return a list of query parameters for the corresponding API call.
"""

import ast
from collections.abc import Callable
from functools import partial
from typing import Any

import numpy as np
import pandas as pd

from bioseq_dl import (
    AlphafoldInterface,
    BioDBNetInterface,
    BioGRIDInterface,
    BrendaInterface,
    ChEBIInterface,
    ChEMBLInterface,
    GenOntologyInterface,
    InterproInterface,
    KEGGInterface,
    PantherInterface,
    PathwayCommonsInterface,
    PDBInterface,
    PubChemInterface,
    ReactomeInterface,
    RefSeqInterface,
    RheaInterface,
    SabiorkInterface,
    StringInterface,
)

QueryBuilder = Callable[[pd.Series, dict], list]

# A valid EC number has four dot-separated components (e.g. "1.1.1.1").
EC_NUMBER_PARTS = 4

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
    "string": StringInterface,
}

##########################################
# Helper functions
###########################################


def to_str_list(value: Any) -> list[str]:
    """Normalize a cell value into a clean list[str].

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


def register_query_builder(
    database: str, method: str, option: str | None = None
) -> Callable[[QueryBuilder], QueryBuilder]:
    """Register a query builder function in QUERY_BUILDERS.

    Args:
        database (str): Database name, such as "biodbnet".
        method (str): Main endpoint name, such as "db2db".
        option (str, optional): Endpoint option, when applicable.

    Usage:
        @register_query_builder("biodbnet", "db2db")
        def build_biodbnet_db2db_query(...):
            ...

        @register_query_builder("uniprot", "search", "reviewed")
        def build_uniprot_search_reviewed_query(...):
            ...

    """
    return partial(_register_query_builder, database=database, method=method, option=option)


def _register_query_builder(
    func: QueryBuilder, *, database: str, method: str, option: str | None = None
) -> QueryBuilder:
    """Store a query builder function and return it unchanged."""
    key = "_".join([part for part in (database, method, option) if part])
    QUERY_BUILDERS[key] = func
    return func


def get_query_builder(database: str, method: str, option: str | None = None) -> QueryBuilder:
    """Return the registered query builder for a database endpoint."""
    key = "_".join([part for part in (database, method, option) if part])
    builder = QUERY_BUILDERS.get(key)
    if builder is None:
        msg = f"No query builder registered for endpoint '{key}'"
        raise ValueError(msg)
    return builder


@register_query_builder("alphafold", "prediction")
def build_query_alphafold_prediction(row: pd.Series, params: dict) -> list:
    """Build AlphaFold prediction queries from 'alphafold_ids' column."""
    alphafold_ids = to_str_list(row.get("alphafold_ids"))
    if alphafold_ids:
        return alphafold_ids
    return []


@register_query_builder("biodbnet", "db2db")
def build_query_biodbnet_db2db(row: pd.Series, params: dict) -> list:
    """Build BioDBNet db2db queries from 'gene_primary' and 'organism_id' columns."""
    genes = to_str_list(row.get("gene_primary"))
    organism = to_str_list(row.get("organism_id"))[0]
    if genes and organism:
        return [{"inputValues": genes, "taxonId": organism, **params}]
    return []


@register_query_builder("biodbnet", "getpathways")
def build_query_biodbnet_getpathways(row: pd.Series, params: dict) -> list:
    """Build BioDBNet getpathways queries from 'organism_id' column."""
    organism = to_str_list(row.get("organism_id"))
    if organism:
        return [{"taxonId": organism_id, **params} for organism_id in organism]
    return []


@register_query_builder("biogrid", "interactions")
def build_query_biogrid_interactions(row: pd.Series, params: dict) -> list:
    """Build BioGRID interactions queries from 'gene_primary' and 'organism_id' columns."""
    genes = to_str_list(row.get("gene_primary"))
    organism = to_str_list(row.get("organism_id"))[0] if to_str_list(row.get("organism_id")) else None
    biogrid_ids = to_str_list(row.get("biogrid_ids"))

    if genes and organism:
        return [{"geneList": genes, "taxId": organism, **params}]
    if biogrid_ids:
        return [{"id": biogrid_id, **params} for biogrid_id in biogrid_ids]
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
def build_query_brenda(row: pd.Series, params: dict) -> list:
    """Build BRENDA kinetics queries from the 'ec' (EC number) column."""
    ec_numbers = to_str_list(row.get("ec"))
    ec_numbers = [
        ec
        for ec in ec_numbers
        if len(ec.split(".")) == EC_NUMBER_PARTS
        and all(part.isdigit() for part in ec.replace("-", "").split("."))
    ]

    if ec_numbers:
        return [{"ecNumber": ec, **params} for ec in ec_numbers]
    return []


@register_query_builder("chembl", "activity")
@register_query_builder("chembl", "binding_site")
def build_query_chembl(row: pd.Series, params: dict) -> list:
    """Build ChEMBL activity/binding_site queries from 'chembl_ids' column."""
    chembl_ids = to_str_list(row.get("chembl_ids"))
    if chembl_ids:
        return [{"target_chembl_id": chembl_id, **params} for chembl_id in chembl_ids]
    return []


@register_query_builder("chebi", "compounds")
def build_query_chebi_compounds(row: pd.Series, params: dict) -> list:
    """Build ChEBI compound queries from 'chebi_ids' column, grouped by 5."""
    group_of = 5
    chebi_ids = to_str_list(row.get("chebi_ids"))
    if chebi_ids:
        return [
            {"chebi_ids": chebi_ids[i : i + group_of], **params} for i in range(0, len(chebi_ids), group_of)
        ]
    return []


@register_query_builder("chebi", "ontology-children")
@register_query_builder("chebi", "ontology-parents")
def build_query_chebi_ontology(row: pd.Series, params: dict) -> list:
    """Build ChEBI ontology queries from 'chebi_ids' column."""
    chebi_ids = to_str_list(row.get("chebi_ids"))
    if chebi_ids:
        return [{"chebi_id": chebi_id, **params} for chebi_id in chebi_ids]
    return []


@register_query_builder("go", "bioentity-function")
@register_query_builder("go", "ontology-term")
def build_query_go(row: pd.Series, params: dict) -> list:
    """Build Gene Ontology queries from 'go_terms' column."""
    go_terms = to_str_list(row.get("go_terms"))
    if go_terms:
        return go_terms
    return []


@register_query_builder("interpro", "entry")
def build_query_interpro(row: pd.Series, params: dict) -> list:
    """Build InterPro entry queries from 'interpro_ids' or 'accession'+'organism_id' columns."""
    interpro_ids = to_str_list(row.get("interpro_ids"))
    accession = to_str_list(row.get("accession"))[0]
    organism = to_str_list(row.get("organism_id"))[0]
    if interpro_ids:
        return [
            {"id": interpro_id, "db": "InterPro", "modifiers": {}, **params} for interpro_id in interpro_ids
        ]
    if accession and organism:
        # If accession and organism_id are present, use them to fetch InterPro entries
        return [
            {
                "db": "InterPro",
                "modifiers": {},
                "filters": [
                    {"type": "protein", "db": "reviewed", "value": accession},
                    {"type": "taxonomy", "db": "uniprot", "value": organism},
                ],
                **params,
            }
        ]
    return []


@register_query_builder("kegg", "get")
def build_query_kegg(row: pd.Series, params: dict) -> list:
    """Build KEGG get queries from 'kegg_ids' column."""
    kegg_ids = to_str_list(row.get("kegg_ids"))
    if kegg_ids:
        return [{"entries": kegg_id, **params} for kegg_id in kegg_ids]
    return []


@register_query_builder("panther", "familymsa")
def build_query_panther_familymsa(row: pd.Series, params: dict) -> list:
    """Build PANTHER familymsa queries from 'panther_ids' column."""
    panther_ids = to_str_list(row.get("panther_ids"))
    if panther_ids:
        return [{"family": panther_id, **params} for panther_id in panther_ids]
    return []


@register_query_builder("panther", "geneinfo")
def build_query_panther_geneinfo(row: pd.Series, params: dict) -> list:
    """Build PANTHER geneinfo queries from 'gene_primary' and 'organism_id' columns."""
    genes = to_str_list(row.get("gene_primary"))
    organism = to_str_list(row.get("organism_id"))

    if genes and organism:
        return [{"geneInputList": genes, "organism": org, **params} for org in organism]
    return []


@register_query_builder("pathwaycommons", "fetch")
def build_query_pathwaycommons_fetch(row: pd.Series, params: dict) -> list:
    """Build PathwayCommons 'fetch' requests from 'reactome_ids' column.

    Returns a list of query dicts. Empty if no valid IDs.
    """
    ids = to_str_list(row.get("reactome_ids"))
    if not ids:  # no ambiguous truth value here
        return []
    return [{"uri": [rid], **params} for rid in ids]


@register_query_builder("pathwaycommons", "top_pathways")
def build_query_pathwaycommons_top_pathways(row: pd.Series, params: dict) -> list:
    """Build PathwayCommons top_pathways queries from 'gene_primary' and 'organism_id' columns."""
    genes = to_str_list(row.get("gene_primary"))
    organism = to_str_list(row.get("organism_id"))

    if genes and organism:
        return [{"q": gene, "organism": organism, **params} for gene in genes]
    return []


@register_query_builder("pathwaycommons", "neighborhood")
def build_query_pathwaycommons_neighborhood(row: pd.Series, params: dict) -> list:
    """Build PathwayCommons neighborhood queries from 'accession' and 'organism_id' columns."""
    accession = row.get("accession") if not pd.isna(row.get("accession")) else None
    organism = to_str_list(row.get("organism_id"))

    if accession and organism:
        return [{"source": [accession], "organism": organism, **params}]
    return []


@register_query_builder("pdb", "entry")
def build_query_pdb(row: pd.Series, params: dict) -> list:
    """Build PDB entry queries from 'pdb_ids' column."""
    pdb = to_str_list(row.get("pdb_ids"))
    if pdb:
        return pdb
    return []


@register_query_builder("pubchem", "compound", "summary")
def build_query_pubchem_compound_summary(row: pd.Series, params: dict) -> list:
    """Build PubChem compound summary queries from 'gene_primary' and 'organism_id' columns."""
    if not pd.isna(row.get("gene_primary")) and not pd.isna(row.get("organism_id")):
        gene_primary = (
            ast.literal_eval(row["gene_primary"])
            if isinstance(row["gene_primary"], str) and row["gene_primary"].startswith("[")
            else [row["gene_primary"]]
        )
        return [{"genesymbol": gene, "taxid": str(row["organism_id"]), **params} for gene in gene_primary]
    return []


@register_query_builder("pubchem", "protein", "summary")
@register_query_builder("pubchem", "protein", "concise")
def build_query_pubchem_protein(row: pd.Series, params: dict) -> list:
    """Build PubChem protein queries from 'accession' column."""
    if not pd.isna(row.get("accession")):
        return [{"accession": row["accession"], **params}]
    return []


@register_query_builder("reactome", "data-discover")
def build_query_reactome(row: pd.Series, params: dict) -> list:
    """Build Reactome data-discover queries from 'reactome_ids' column."""
    ids_raw = to_str_list(row.get("reactome_ids"))
    if ids_raw:
        return ids_raw
    return []


@register_query_builder("rhea", "rhea")
def build_query_rhea(row: pd.Series, params: dict) -> list:
    """Build Rhea queries from 'rhea_ids' column."""
    ids_raw = to_str_list(row.get("rhea_ids"))
    if ids_raw:
        return [{"query": rhea_id, **params} for rhea_id in ids_raw]
    return []


@register_query_builder("refseq", "protein")
def build_query_refseq(row: pd.Series, params: dict) -> list:
    """Build RefSeq protein queries from 'refseq_ids' column."""
    ids_raw = to_str_list(row.get("refseq_ids"))
    if ids_raw:
        return ids_raw
    return []


@register_query_builder("sabio-rk", "kineticlaws")
def build_query_sabiork_kineticlaws(row: pd.Series, params: dict) -> list:
    """Build SABIO-RK kineticlaws queries from 'sabiork_ids' column."""
    sabiork_ids = to_str_list(row.get("sabiork_ids"))

    if sabiork_ids:
        return [{"UniProtKB_AC": sabiork_id, **params} for sabiork_id in sabiork_ids]
    return []


@register_query_builder("string", "interaction_partners")
@register_query_builder("string", "get_string_ids")
def build_query_stringdb(row: pd.Series, params: dict) -> list:
    """Build STRING interaction queries from 'string_ids' or 'gene_primary'+'organism_id' columns."""
    string_ids = to_str_list(row.get("string_ids"))
    organism = to_str_list(row.get("organism_id"))[0]
    gene_primary = to_str_list(row.get("gene_primary"))
    if string_ids:
        return [{"identifiers": string_id, **params} for string_id in string_ids]
    if gene_primary and organism:
        return [{"identifiers": gene, "species": organism, **params} for gene in gene_primary]
    return []
