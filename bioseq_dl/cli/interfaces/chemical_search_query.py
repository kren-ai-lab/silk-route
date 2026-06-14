import json
import logging
from pathlib import Path

import pandas as pd
import typer

from bioseq_dl import ChEBIInterface, ChEMBLInterface, PubChemInterface

# Pending: Uniprot ID
from bioseq_dl.logging import configure_logging, get_logger

log = get_logger("bioseq_dl.cli.chemical_search_query")

app = typer.Typer(
    help="Collect data from chemical databases. A general search interface is provided to query compounds by name, CID, SMILES, InChI, or gene ID."
)

AVAILABLE_DATABASES = ["pubchem", "chembl", "chebi"]


def detect_query_type(query: str) -> str:
    """Detect the type of the query string."""
    query = query.strip()

    if query.startswith("InChI="):
        return "inchi"
    if any(c in query for c in "=#[]") and query.count("C") >= 1 and len(query) > 6:
        return "smiles"
    if query.isupper() and len(query) <= 6:
        return "gene"
    return "name"


def pubchem_search_query(query: str, exact_match: bool = False) -> tuple[pd.DataFrame, dict]:
    """Fetch compound data from PubChem."""
    metadata = {}
    pug_metadata = {}
    pug_view_metadata = {}
    name_type = "complete" if exact_match else "word"

    instance = PubChemInterface()

    query_type = detect_query_type(query)

    if query_type in {"name", "inchi", "smiles"}:
        query_dict = [{query_type: query.strip(), "name_type": name_type} for query in query.split(",")]
        log.info(f"Getting CIDs for {query_type.upper()}s: {query_dict}")
        cids_df, pug_metadata = instance.fetch_batch(
            queries=query_dict, method="pug/compound", parse=True, format="dataframe"
        )
        if not isinstance(cids_df, pd.DataFrame) or cids_df.empty:
            log.warning(f"No CIDs found for the given {query_type.upper()}s.")
            return pd.DataFrame(), metadata

        cids = cids_df["cid"].astype(str).tolist()
        log.info(f"Found CIDs: {cids}")
        query_dict = [{"cid": cid} for cid in cids]
        export_df, pug_view_metadata = instance.fetch_batch(
            queries=query_dict, method="pug_view/compound", parse=True, format="dataframe"
        )
    elif query_type == "gene":
        query_dict = [{"geneid": query.strip()} for query in query.split(",")]
        log.info(f"Fetching data for Gene IDs: {query_dict}")
        export_df, pug_view_metadata = instance.fetch_batch(
            queries=query_dict, method="pug_view/gene", parse=True, format="dataframe"
        )
    else:
        log.error(f"Unsupported query type: {query_type}")
        return pd.DataFrame(), metadata

    if pug_metadata and isinstance(pug_metadata, dict):
        metadata.update(pug_metadata)
    if pug_view_metadata and isinstance(pug_view_metadata, dict):
        metadata.update(pug_view_metadata)

    if isinstance(export_df, pd.DataFrame) and not export_df.empty:
        return export_df, metadata
    log.warning("No PubChem data found for the given query.")
    return pd.DataFrame(), metadata


def chembl_search_query(query: str, exact_match: bool = False) -> tuple[pd.DataFrame, dict]:
    """Fetch compound data from ChEMBL."""
    filter_type = "iexact" if exact_match else "icontains"
    instance = ChEMBLInterface()

    query_type = detect_query_type(query)

    if query_type == "name":
        query_dict = {
            "filters": [{"field": "molecule_name", "filter_type": filter_type, "value": query.strip()}]
        }
        log.info(f"Fetching data for molecule names: {query_dict}")
        export_df, metadata = instance.fetch_single(
            query=query_dict, method="molecule", parse=True, format="dataframe"
        )
    elif query_type == "smiles":
        query_dict = {
            "filters": [
                {
                    "field": "molecule_structures__canonical_smiles",
                    "filter_type": filter_type,
                    "value": query.strip(),
                }
            ]
        }
        log.info(f"Fetching data for SMILES: {query_dict}")
        export_df, metadata = instance.fetch_single(
            query=query_dict, method="molecule", parse=True, format="dataframe"
        )
    elif query_type == "gene":
        query_dict = {
            "filters": [{"field": "gene_symbol", "filter_type": filter_type, "value": query.strip()}]
        }
        log.info(f"Fetching data for Gene IDs: {query_dict}")
        export_df, metadata = instance.fetch_single(
            query=query_dict, method="target", parse=True, format="dataframe"
        )
    elif query_type == "inchi":
        log.error("ChEMBL does not support InChI-based searches yet.")
        return pd.DataFrame(), {}
    else:
        log.error(f"Unsupported query type for ChEMBL: {query_type}")
        return pd.DataFrame(), {}

    if isinstance(export_df, pd.DataFrame) and not export_df.empty:
        return export_df, metadata
    log.warning("No ChEMBL data found for the given query.")
    return pd.DataFrame(), metadata


def chebi_search_query(query: str) -> tuple[pd.DataFrame, dict]:
    """Fetch compound data from ChEBI."""
    metadata = {}
    instance = ChEBIInterface()

    log.info(f"Fetching data for query: {query.strip()}")
    # This search doesnt require exact match parameter
    # Neither requires specifying the query type
    query = {"term": query.strip()}
    export_df, es_search_metadata = instance.fetch_single(
        query=query, method="es_search", parse=True, format="dataframe"
    )
    # Make query for every found chebi_id
    chebi_ids = export_df["chebi_accession"].tolist()
    query = {"chebi_ids": chebi_ids}
    export_df, compounds_metadata = instance.fetch_single(
        query=query, method="compounds", parse=True, format="dataframe"
    )

    if es_search_metadata and isinstance(es_search_metadata, dict):
        metadata.update(es_search_metadata)
    if compounds_metadata and isinstance(compounds_metadata, dict):
        metadata.update(compounds_metadata)

    if isinstance(export_df, pd.DataFrame) and not export_df.empty:
        return export_df, metadata
    log.warning("No ChEBI data found for the given query.")
    return pd.DataFrame(), metadata


@app.command("run")
def run_compound(
    query: str = typer.Argument(
        ...,
        help="Search query string (e.g., aspirin, InChI=1S/C3H6O/c1-3(2)4/h1-2H3, C1=CC=C(C=C1)C=O, EGFR)",
    ),
    databases: str = typer.Option(
        "all",
        help="Databases to search separated by commas (e.g., pubchem, chembl). Use 'all' to search all available databases.",
    ),
    output: str = typer.Option(..., help="Output file to save results"),
    exact_match: bool = typer.Option(False, help="Use exact match for name searches"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Fetch compound data from chemical databases."""
    logger = log
    try:
        if debug:
            configure_logging(level=logging.DEBUG)
            logger = get_logger(
                "bioseq_dl.cli.uniprot_search_query"
            )  # re-fetch so root handlers pick new level
            logger.debug("Debug logging enabled")
    except Exception as e:
        logger.warning(f"Could not configure logging: {e}")

    if databases.lower() != "all":
        db_list = [db.strip().lower() for db in databases.split(",")]
    else:
        db_list = AVAILABLE_DATABASES

    # Create folder for output if it does not exist
    Path(output).mkdir(parents=True, exist_ok=True)

    for db in db_list:
        if db == "pubchem":
            log.info(f"Searching PubChem for query: {query}")
            result, metadata = pubchem_search_query(query, exact_match=exact_match)
            if isinstance(result, pd.DataFrame) and not result.empty:
                result.to_csv(f"{output}/pubchem_results.csv", index=False)
                with (Path(output) / "pubchem_metadata.json").open("w") as f:
                    json.dump(metadata, f, indent=2, default=str)
                log.info(f"Results saved to {output}/pubchem_results.csv")

        elif db == "chembl":
            log.info(f"Searching ChEMBL for query: {query}")
            result, metadata = chembl_search_query(query, exact_match=exact_match)
            if isinstance(result, pd.DataFrame) and not result.empty:
                result.to_csv(f"{output}/chembl_results.csv", index=False)
                with (Path(output) / "chembl_metadata.json").open("w") as f:
                    json.dump(metadata, f, indent=2, default=str)
                log.info(f"Results saved to {output}/chembl_results.csv")
        elif db == "chebi":
            log.info(f"Searching ChEBI for query: {query}")
            result, metadata = chebi_search_query(query)
            if isinstance(result, pd.DataFrame) and not result.empty:
                result.to_csv(f"{output}/chebi_results.csv", index=False)
                with (Path(output) / "chebi_metadata.json").open("w") as f:
                    json.dump(metadata, f, indent=2, default=str)
                log.info(f"Results saved to {output}/chebi_results.csv")
        else:
            log.warning(f"Database '{db}' is not supported.")
