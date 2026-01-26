import os
import json
import logging
import typer
from typing import Literal, cast, Tuple, List, Dict
import re

import pandas as pd 

from bioseq_dl import UniprotInterface
from bioseq_dl.constants.uniprot import VALID_FIELDS, XREF_MAPPING
from bioseq_dl.core.utils.crossref_enrichment import run_crossref_enrichment
from bioseq_dl.logging import configure_logging

from .query_interpreter import build_default_uniprot_interpreter

from bioseq_dl import ChEMBLInterface

app = typer.Typer(help="Search and download proteins.")

# ----- Optional logging (fallback to stdlib) -----
try:
    from bioseq_dl.logging import get_logger
except Exception:
    def get_logger(name: str) -> logging.Logger:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        return logging.getLogger(name)

    def configure_logging(level: int = logging.INFO, **kwargs: object) -> None:
        logging.basicConfig(level=level, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")

log = get_logger("bioseq_dl.cli.protein")
# -------------------------------------------------

app = typer.Typer(name="uniprot-search-query", help="Search and download sequences from UniProt using queries.")   

def chembl_search(query: str, method: str, format: str) -> Tuple[str, pd.DataFrame | List | Dict, Dict]:

    output_query = ""
    log.debug(f"Performing a ChEMBL search using query=\"{query}\" and method=\"{method}\"")
    instance = ChEMBLInterface()

    result, metadata = instance.fetch_single(
        query=query,
        method=method,
        parse=True,
        format=format
    )

    if format == "dataframe" and isinstance(result, pd.DataFrame):
        target_ids = result['target_chembl_id'].unique().tolist()
        output_query = f"(xref:chembl-{' OR ' .join(target_ids)})" if target_ids else ""
    elif format == "json" and isinstance(result, list) and result:
        target_ids = [item.get('target_chembl_id') for item in result if 'target_chembl_id' in item]
        output_query = f"(xref:chembl-{' OR '.join(target_ids)})" if target_ids else ""
    elif format == "json" and isinstance(result, dict) and 'target_chembl_id' in result:
        target_id = result['target_chembl_id']
        output_query = f"(xref:chembl-{' OR '.join([target_id])})" if target_id else ""
    elif format == "xml" and isinstance(result, str):
        target_ids = re.findall(r'<target_chembl_id>(CHEMBL\d+)</target_chembl_id>', result)
        output_query = f"(xref:chembl-{' OR '.join(target_ids)})" if target_ids else ""
    else:
        output_query = ""
    
    log.debug(f"ChEMBL search produced output_query=\"{output_query}\"")

    return output_query, result, metadata

def resolve_search(searches: dict, format: str) -> dict:
    search_results = {}
    # Check if query and method are present
    if "database" in searches and "query" in searches and "method" in searches:
        match searches["database"]:
            case "chembl":
                output_query, chembl_result, metadata = chembl_search(
                    query=searches["query"],
                    method=searches["method"],
                    format=format
                )
                search_results = {
                    "output_query": output_query,
                    "result": chembl_result,
                    "metadata": metadata
                }

            case _:
                pass

    return search_results


def _check_enriched_data(enriched_data: tuple, desired_format: str) -> bool:
    if isinstance(enriched_data[0], dict):
        if desired_format == "dataframe":
            return all([isinstance(df, pd.DataFrame) for df in enriched_data[0].values()])
        elif desired_format == "json":
            return all([isinstance(val, (dict, list)) for val in enriched_data[0].values()])
        elif desired_format == "xml":
            return all([hasattr(val, "getroot") for val in enriched_data[0].values()])
    
    return False

def save_enriched_data(data: pd.DataFrame | list | dict | bytes | str, enriched_data: tuple, metadata: dict, output: str, export_format: str, logger) -> None:
    if export_format == "dataframe" and _check_enriched_data(enriched_data, "dataframe"):
        # Save main results
        if isinstance(data, pd.DataFrame) and not data.empty:
            data.to_csv(f"{output}/uniprot_results.csv", index=False)
        # Save each DataFrame separately
        for key, df in enriched_data[0].items():
            logger.info(f"Saving {key} results into {output} directory")
            df.to_csv(f"{output}/{key}_results.csv", index=False)

    elif export_format == "json" and _check_enriched_data(enriched_data, "json"):
        # Save main results
        if isinstance(data, (dict, list)) and data:
            logger.info(f"Saving UniProt results into {output}/uniprot_results.json")
            json.dump(data, open(f"{output}/uniprot_results.json", "w"), indent=2, default=str)
        # Save each JSON separately
        for key, val in enriched_data[0].items():
            logger.info(f"Saving {key} results into {output} directory")
            json.dump(val, open(f"{output}/{key}_results.json", "w"), indent=2, default=str)

    elif export_format == "xml" and _check_enriched_data(enriched_data, "xml"):
        # Save main results
        if hasattr(data, "getroot"):
            logger.info(f"Saving UniProt results into {output}/uniprot_results.xml")
            data.write(f"{output}/uniprot_results.xml", encoding="utf-8", xml_declaration=True)

        # Save each XML separately
        for key, val in enriched_data[0].items():
            logger.info(f"Saving {key} results into {output} directory")
            val.write(f"{output}/{key}_results.xml", encoding="utf-8", xml_declaration=True)
    else:
        logger.error("Enriched data format does not match the expected export format or is invalid.")
        return
    
    # Concatenate metadata and save
    if not metadata:
        metadata = {}
    metadata["enrichment"] = enriched_data[1]["metadata"] if "metadata" in enriched_data[1] else {}
    with open(f"{output}/metadata.json", "w") as f:
        json.dump(metadata, f, indent=2, default=str)
        logger.info(f"Enriched results metadata saved to {output}/metadata.json")

    
@app.command()
def run(
    output: str = typer.Option(
        ..., "-o", "--output", 
        help="Output directory for results"
    ),
    query: str = typer.Option(
        ..., "-q", "--query", 
        help="Query to search for"
    ),
    fields: str = typer.Option(
        ",".join(VALID_FIELDS), "-f", "--fields", 
        help="Fields to include in the output"
    ),
    sort: str = typer.Option(
        "accession asc", "-s", "--sort", 
        help="Sort order for the results"
    ),
    include_isoform: bool = typer.Option(
        False, "--include_isoform", 
        help="Include isoforms in the results"
    ),
    debug: bool = typer.Option(
        False, "--debug",
        help="Enable debug logging"
    ),
    export_format: str = typer.Option(
        "dataframe", "-ef", "--export_format", 
        help="Export format: dataframe, xml, json",
    )
):
    logger = log
    try:
        if debug:
            configure_logging(level=logging.DEBUG)
            logger = get_logger("bioseq_dl.cli.uniprot_search_query")  # re-fetch so root handlers pick new level
            logger.debug("Debug logging enabled")
    except Exception as e:
        logger.warning(f"Could not configure logging: {e}")
    
    metadata = {
        "cli": {
            "output": output,
            "query": query,
            "fields": fields,
            "export_format": export_format,
            "interpreted_query": None
        }
    }


    ###############################
    # Query Interpretation Step #
    ###############################
    interpreter = build_default_uniprot_interpreter()
    interpreted_query = interpreter.interpret(query)
    metadata["cli"]["interpreted_query"] = interpreted_query
    metadata["fetch"] = {}

    # Get crossref fields
    crossref_fields = interpreter.extract_databases(query)

    # Get possible additional searches and do if needed
    additional_searches = interpreter.extract_additional_searches(query)
    search_results = []

    if additional_searches:
        logger.info("Resolving additional searches...")
        search_results = [
            (search["database"], resolve_search(search, export_format)) for search in additional_searches
        ]
        for db, result in search_results:
            if result.get("output_query"):
                interpreted_query += f" AND {result['output_query']}" if interpreted_query else result['output_query']
                logger.debug(f"Updated interpreted_query to: {interpreted_query}")
                metadata_key = f"{db}_search"
                metadata["fetch"][metadata_key] = result.get("metadata", {})
    
    #print("Final interpreted query:", interpreted_query)
    #exit(0)

    ################################
    # UniProt Data Retrieval Step #
    ################################
    logger.info(f"Starting UniProt search with query: {query} with parameters fields={fields}, sort={sort}, include_isoform={include_isoform}")
    instance = UniprotInterface()

    logger.debug(f"Downloading data using\nquery {query}\nfields {fields}\ncrossref_fields {crossref_fields}\nformat {format}\nsort {sort}\ninclude_isoform {include_isoform}")
    xref_mapping = {v[1]: v[0] for k, v in XREF_MAPPING.items() if v[0] is not None}
    xref = ",".join([xref_mapping[c] for c in crossref_fields.split(",") if c in xref_mapping])

    response, fetch_metadata = instance.submit_stream(
        query=interpreted_query,
        fields=fields + "," + xref,
        sort=sort,
        include_isoform=include_isoform,
    )
    metadata["fetch"]["uniprot"] = fetch_metadata

    # Create folder for output if it does not exist
    os.makedirs(output, exist_ok=True)

    with open(f"{output}/raw_response.json", "w") as f:
        json.dump(response, f, indent=2, default=str)

    logger.info("Parsing results...")
    export_data, parsed_metadata = instance.parse(
        results=response,
        extract_fields=None,
        format=cast(Literal["json", "dataframe", "xml"], export_format)
    )

    if isinstance(parsed_metadata, dict):
        metadata["parsing"] = parsed_metadata
    else:
        metadata["parsing"] = {}

    ###################################
    # Cross-reference Enrichment Step #
    ###################################
    enriched_data = tuple()
    if crossref_fields and isinstance(export_data, (pd.DataFrame, dict, list)):
        logger.info("Running cross-reference enrichment...")
        enriched_data = run_crossref_enrichment(
            data=export_data,
            crossref_fields=crossref_fields.split(","),
            format=cast(Literal["json", "dataframe", "xml"], export_format)
        )



    #######################
    # Export Results Step #
    #######################
    save_enriched_data(export_data, enriched_data, metadata, output, export_format, logger)