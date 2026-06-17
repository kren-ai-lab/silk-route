"""Chemical search query CLI commands."""

import json
import logging
from pathlib import Path
from typing import cast

import pandas as pd
import typer

from bioseq_dl import ChEBIInterface, ChEMBLInterface, PubChemInterface
from bioseq_dl.cli._shared import output_dir_option

# Pending: Uniprot ID
from bioseq_dl.logging import configure_logging, get_logger

log = get_logger("bioseq_dl.cli.chemical_search_query")

AVAILABLE_DATABASES = ["pubchem", "chembl", "chebi"]

# Gene symbols are short; longer SMILES-like strings exceed this length.
_MAX_GENE_QUERY_LEN = 6


def detect_query_type(query: str) -> str:
    """Detect the type of the query string."""
    query = query.strip()

    if query.startswith("InChI="):
        return "inchi"
    if any(c in query for c in "=#[]") and query.count("C") >= 1 and len(query) > _MAX_GENE_QUERY_LEN:
        return "smiles"
    if query.isupper() and len(query) <= _MAX_GENE_QUERY_LEN:
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
        log.info("Getting CIDs for %ss: %s", query_type.upper(), query_dict)
        cids_df, pug_metadata = instance.fetch_batch(
            queries=query_dict, method="pug/compound", parse=True, format="dataframe"
        )
        if not isinstance(cids_df, pd.DataFrame) or cids_df.empty:
            log.warning("No CIDs found for the given %ss.", query_type.upper())
            return pd.DataFrame(), metadata

        cids = cids_df["cid"].astype(str).tolist()
        log.info("Found CIDs: %s", cids)
        query_dict = [{"cid": cid} for cid in cids]
        export_df, pug_view_metadata = instance.fetch_batch(
            queries=query_dict, method="pug_view/compound", parse=True, format="dataframe"
        )
    elif query_type == "gene":
        query_dict = [{"geneid": query.strip()} for query in query.split(",")]
        log.info("Fetching data for Gene IDs: %s", query_dict)
        export_df, pug_view_metadata = instance.fetch_batch(
            queries=query_dict, method="pug_view/gene", parse=True, format="dataframe"
        )
    else:
        log.error("Unsupported query type: %s", query_type)
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
        log.info("Fetching data for molecule names: %s", query_dict)
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
        log.info("Fetching data for SMILES: %s", query_dict)
        export_df, metadata = instance.fetch_single(
            query=query_dict, method="molecule", parse=True, format="dataframe"
        )
    elif query_type == "gene":
        query_dict = {
            "filters": [{"field": "gene_symbol", "filter_type": filter_type, "value": query.strip()}]
        }
        log.info("Fetching data for Gene IDs: %s", query_dict)
        export_df, metadata = instance.fetch_single(
            query=query_dict, method="target", parse=True, format="dataframe"
        )
    elif query_type == "inchi":
        log.error("ChEMBL does not support InChI-based searches yet.")
        return pd.DataFrame(), {}
    else:
        log.error("Unsupported query type for ChEMBL: %s", query_type)
        return pd.DataFrame(), {}

    if isinstance(export_df, pd.DataFrame) and not export_df.empty:
        return export_df, metadata
    log.warning("No ChEMBL data found for the given query.")
    return pd.DataFrame(), metadata


def chebi_search_query(query: str) -> tuple[pd.DataFrame, dict]:
    """Fetch compound data from ChEBI."""
    metadata = {}
    instance = ChEBIInterface()

    log.info("Fetching data for query: %s", query.strip())
    # This search doesnt require exact match parameter
    # Neither requires specifying the query type
    search_query = {"term": query.strip()}
    es_df, es_search_metadata = instance.fetch_single(
        query=search_query, method="es_search", parse=True, format="dataframe"
    )
    # Make query for every found chebi_id
    chebi_ids = cast("pd.DataFrame", es_df)["chebi_accession"].tolist()
    compounds_query = {"chebi_ids": chebi_ids}
    export_df, compounds_metadata = instance.fetch_single(
        query=compounds_query, method="compounds", parse=True, format="dataframe"
    )

    if es_search_metadata and isinstance(es_search_metadata, dict):
        metadata.update(es_search_metadata)
    if compounds_metadata and isinstance(compounds_metadata, dict):
        metadata.update(compounds_metadata)

    if isinstance(export_df, pd.DataFrame) and not export_df.empty:
        return export_df, metadata
    log.warning("No ChEBI data found for the given query.")
    return pd.DataFrame(), metadata


def run_compound(
    query: str = typer.Argument(
        ...,
        help="Search query string (e.g., aspirin, InChI=1S/C3H6O/c1-3(2)4/h1-2H3, C1=CC=C(C=C1)C=O, EGFR)",
    ),
    databases: str = typer.Option(
        "all",
        help=(
            "Databases to search separated by commas (e.g., pubchem, chembl). Use 'all' to search all "
            "available "
            "databases."
        ),
    ),
    output: str = output_dir_option(),
    exact_match: bool = typer.Option(False, help="Use exact match for name searches"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
) -> None:
    """Fetch compound data from chemical databases."""
    logger = log
    try:
        if debug:
            configure_logging(level=logging.DEBUG)
            logger = get_logger(
                "bioseq_dl.cli.chemical_search_query"
            )  # re-fetch so root handlers pick new level
            logger.debug("Debug logging enabled")
    except Exception as e:  # noqa: BLE001  # defensive catch-all
        logger.warning("Could not configure logging: %s", e)

    if databases.lower() != "all":
        db_list = [db.strip().lower() for db in databases.split(",")]
    else:
        db_list = AVAILABLE_DATABASES

    # Create folder for output if it does not exist
    Path(output).mkdir(parents=True, exist_ok=True)

    for db in db_list:
        if db == "pubchem":
            log.info("Searching PubChem for query: %s", query)
            result, metadata = pubchem_search_query(query, exact_match=exact_match)
            if isinstance(result, pd.DataFrame) and not result.empty:
                result.to_csv(f"{output}/pubchem_results.csv", index=False)
                with (Path(output) / "pubchem_metadata.json").open("w") as f:
                    json.dump(metadata, f, indent=2, default=str)
                log.info("Results saved to %s/pubchem_results.csv", output)

        elif db == "chembl":
            log.info("Searching ChEMBL for query: %s", query)
            result, metadata = chembl_search_query(query, exact_match=exact_match)
            if isinstance(result, pd.DataFrame) and not result.empty:
                result.to_csv(f"{output}/chembl_results.csv", index=False)
                with (Path(output) / "chembl_metadata.json").open("w") as f:
                    json.dump(metadata, f, indent=2, default=str)
                log.info("Results saved to %s/chembl_results.csv", output)
        elif db == "chebi":
            log.info("Searching ChEBI for query: %s", query)
            result, metadata = chebi_search_query(query)
            if isinstance(result, pd.DataFrame) and not result.empty:
                result.to_csv(f"{output}/chebi_results.csv", index=False)
                with (Path(output) / "chebi_metadata.json").open("w") as f:
                    json.dump(metadata, f, indent=2, default=str)
                log.info("Results saved to %s/chebi_results.csv", output)
        else:
            log.warning("Database '%s' is not supported.", db)
