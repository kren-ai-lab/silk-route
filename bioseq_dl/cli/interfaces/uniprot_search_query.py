import os
import json
import logging
import typer
from typing import Literal, cast

import pandas as pd 

from bioseq_dl import UniprotInterface
from bioseq_dl.constants.uniprot import VALID_FIELDS, XREF_MAPPING
from bioseq_dl.core.export import export_dataframe, normalize_export_format, normalize_parse_format
from bioseq_dl.core.utils.crossref_enrichment import run_crossref_enrichment
from bioseq_dl.logging import configure_logging

from bioseq_dl.logging import get_logger

log = get_logger("bioseq_dl.cli.uniprot_search_query")

app = typer.Typer(name="uniprot-search-query", help="Search and download sequences from UniProt using queries.")    

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
    crossref_fields: str = typer.Option(
        "", "-xr", "--crossref_fields", 
        help="Cross reference fields to include in the output, options: " + ", ".join([xref[1] for xref in XREF_MAPPING.values()])
    ),
    sort: str = typer.Option(
        "accession asc", "-s", "--sort", 
        help="Sort order for the results"
    ),
    include_isoform: bool = typer.Option(
        False, "--include_isoform", 
        help="Include isoforms in the results"
    ),
    concat_results: bool = typer.Option(
        False, "--concat_results", 
        help="Concatenate cross-reference results into a single DataFrame"
    ),
    debug: bool = typer.Option(
        False, "--debug",
        help="Enable debug logging"
    ),
    export_format: str = typer.Option(
        "dataframe", "-ef", "--export_format", 
        help="Export format: dataframe, xml, json, parquet",
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

    logger.info(f"Starting UniProt search with query: {query} with parameters fields={fields}, crossref_fields={crossref_fields}, sort={sort}, include_isoform={include_isoform}, concat_results={concat_results}")
    metadata = {}
    instance = UniprotInterface()
    logger.debug(f"Downloading data using\nquery {query}\nfields {fields}\ncrossref_fields {crossref_fields}\nformat {format}\nsort {sort}\ninclude_isoform {include_isoform}")
    xref_mapping = {v[1]: v[0] for k, v in XREF_MAPPING.items() if v[0] is not None}
    xref = ",".join([xref_mapping[c] for c in crossref_fields.split(",") if c in xref_mapping])

    response, fetch_metadata = instance.submit_stream(
        query=query,
        fields=fields + "," + xref,
        sort=sort,
        include_isoform=include_isoform,
    )
    metadata["fetch"] = fetch_metadata

    # Create folder for output if it does not exist

    os.makedirs(output, exist_ok=True)

    with open(f"{output}/raw_response.json", "w") as f:
        json.dump(response, f, indent=2, default=str)

    logger.info("Parsing results...")
    parse_format = normalize_parse_format(export_format) or "dataframe"
    export_data, parsed_metadata = instance.parse(
        results=response,
        extract_fields=None,
        format=cast(Literal["json", "dataframe", "xml"], parse_format)
    )
    metadata["parsing"] = parsed_metadata

    enriched_data = None
    if crossref_fields:
        logger.info("Running cross-reference enrichment...")
        enriched_data, enriched_metadata = run_crossref_enrichment(
            export_data, 
            crossref_fields.split(","), 
            format=cast(Literal["json", "dataframe", "xml"], parse_format)
        )
        metadata["enrichment"] = enriched_metadata

    if export_format in {"dataframe", "parquet"}:
        if isinstance(export_data, pd.DataFrame) and not export_data.empty:
            tabular_format = normalize_export_format(export_format)
            export_path = os.path.join(output, f"uniprot_results.{tabular_format}")
            export_dataframe(export_data, export_path, output_format=tabular_format)
            if isinstance(enriched_data, dict):
                for key, value in enriched_data.items():
                    logger.info(f"Saving {key} results into {output} directory")
                    export_dataframe(
                        value,
                        os.path.join(output, f"{key}_results.{tabular_format}"),
                        output_format=tabular_format,
                    )
    
            with open(f"{output}/metadata.json", "w") as f:
                json.dump(metadata, f, indent=2, default=str)
            logger.info(f"Results saved to {export_path}")
        else:
            logger.warning("No results to save in DataFrame format.")
    elif export_format == "json":
        if isinstance(export_data, dict) or isinstance(export_data, list):
            with open(f"{output}/uniprot_results.json", "w") as f:
                json.dump(export_data, f, indent=2, default=str)
            
            if isinstance(enriched_data, dict):
                for key, value in enriched_data.items():
                    logger.info(f"Saving {key} results into {output} directory")
                    json.dump(value, open(f"{output}/{key}_results.json", "w"), indent=2, default=str)

            with open(f"{output}/metadata.json", "w") as f:
                json.dump(metadata, f, indent=2, default=str)
            logger.info(f"Results saved to {output}/uniprot_results.json")
        else:
            logger.warning("No results to save in JSON format.")
    elif export_format == "xml":
        if hasattr(export_data, "getroot"):
            export_data.write(f"{output}/uniprot_results.xml", encoding="utf-8", xml_declaration=True)

            if isinstance(enriched_data, dict):
                for key, value in enriched_data.items():
                    logger.info(f"Saving {key} results into {output} directory")
                    value.write(f"{output}/{key}_results.xml", encoding="utf-8", xml_declaration=True)

            with open(f"{output}/metadata.json", "w") as f:
                json.dump(metadata, f, indent=2, default=str)
            logger.info(f"Results saved to {output}/uniprot_results.xml")
        else:
            logger.warning("No results to save in XML format.")
    else:
        logger.warning(export_format)
        logger.warning("No UniProt data found for the BLAST results.")