import os
import json
import logging
import typer

import pandas as pd 

from bioseq_dl import UniprotInterface
from bioseq_dl.constants.uniprot import VALID_FIELDS, XREF_MAPPING
from bioseq_dl.core.utils.crossref_enrichment import run_crossref_enrichment
from bioseq_dl.logging import configure_logging

# ----- Optional logging (fallback to stdlib) -----
try:
    from bioseq_dl.logging import get_logger
except Exception:
    def get_logger(name: str) -> logging.Logger:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        return logging.getLogger(name)

    def configure_logging(level: int = logging.INFO, **kwargs: object) -> None:
        logging.basicConfig(level=level, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")

log = get_logger("bioseq_dl.cli.uniprot_search_query")
# -------------------------------------------------

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
    export_df, parsed_metadata = instance.parse_results(
        results=response,
        extract_fields=None,
        to_dataframe=True
    )
    metadata["parsing"] = parsed_metadata

    if isinstance(export_df, pd.DataFrame) and not export_df.empty:
        if crossref_fields:
            logger.info("Running cross-reference enrichment...")
            enriched_data, enriched_metadata = run_crossref_enrichment(export_df, crossref_fields.split(","), concat_results=concat_results, to_dataframe=True)
            metadata["enrichement"] = enriched_metadata

            if isinstance(enriched_data, pd.DataFrame) and not enriched_data.empty:
                export_df = enriched_data
            elif isinstance(enriched_data, dict):
                for key, value in enriched_data.items():
                    logger.info(f"Saving {key} results into {output} directory")
                    value.to_csv(f"{output}/{key}_results.csv", index=False)
            
        export_df.to_csv(f"{output}/uniprot_results.csv", index=False)
        with open(f"{output}/metadata.json", "w") as f:
            json.dump(metadata, f, indent=2, default=str)
        logger.info(f"Results saved to {output}/uniprot_results.csv")
    else:
        logger.warning("No results found for the given query.")