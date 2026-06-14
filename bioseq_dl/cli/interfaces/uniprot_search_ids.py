import json
import logging
from pathlib import Path
from typing import Literal, cast

import pandas as pd
import typer

from bioseq_dl import UniprotInterface
from bioseq_dl.constants.uniprot import VALID_CROSS_REF_FIELDS, VALID_FIELDS
from bioseq_dl.core.export import (
    USER_EXPORT_FORMATS,
    export_dataframe,
    normalize_export_format,
    normalize_parse_format,
    normalize_user_export_format,
)
from bioseq_dl.core.utils.crossref_enrichment import run_crossref_enrichment
from bioseq_dl.logging import configure_logging

app = typer.Typer(help="Search and download sequences from UniProt using IDs.")

from bioseq_dl.logging import get_logger

log = get_logger("bioseq_dl.cli.uniprot_search_ids")


@app.command()
def run(
    input: str = typer.Option(..., "-i", "--input", help="CSV file with UniProt IDs"),
    column: str = typer.Option("accession", "-c", "--column", help="Column name with UniProt IDs"),
    output: str = typer.Option(..., "-o", "--output", help="Output file"),
    from_db: str = typer.Option(
        "UniProtKB_AC-ID",
        "--from_db",
        help="Database to convert from. Default is UniProtKB_AC-ID (UniProtKB_AC-ID, PDB)",
    ),
    to_db: str = typer.Option("UniProtKB", "--to_db", help="Database to convert to"),
    fields: str = typer.Option(
        ",".join(VALID_FIELDS), "-f", "--fields", help="Fields to include in the output"
    ),
    crossref_fields: str = typer.Option(
        ",".join(VALID_CROSS_REF_FIELDS),
        "-xr",
        "--crossref_fields",
        help="Cross reference fields to include in the output",
    ),
    batch_size: int = typer.Option(5000, "-b", "--batch_size", help="Batch size for downloading"),
    auto_db: bool = typer.Option(False, "-a", "--auto_db", help="Automatically detect database type"),
    min_identity: float = typer.Option(
        None, "--min_identity", help="Minimum identity threshold for BLAST search."
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
    export_format: str = typer.Option(
        "csv",
        "-ef",
        "--export_format",
        help="Export format: csv, json, xml, parquet. Default is csv.",
    ),
) -> None:
    logger = log
    raw_export_format = export_format
    try:
        export_format = normalize_user_export_format(export_format)
        if export_format is None:
            msg = f"Unsupported export format '{raw_export_format}'. Supported formats are: {', '.join(USER_EXPORT_FORMATS)}."
            raise ValueError(msg)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None

    try:
        if debug:
            configure_logging(level=logging.DEBUG)
            logger = get_logger(
                "bioseq_dl.cli.uniprot_search_query"
            )  # re-fetch so root handlers pick new level
            logger.debug("Debug logging enabled")
    except Exception as e:
        logger.warning(f"Could not configure logging: {e}")

    df = pd.read_csv(input)

    # Filter by identity if present
    if min_identity is not None and "identity" in df.columns:
        df = df[df["identity"] >= min_identity]

    metadata = {}
    log.info("Downloading additional UniProt data...")
    instance = UniprotInterface()
    logger.debug(
        f"Downloading data using blast results\nfields {fields}\ncrossref_fields {crossref_fields}\n"
    )

    response, fetch_metadata = instance.download_batch(
        df, "accession", True, "UniProtKB_AC-ID", "UniProtKB", 5000
    )
    metadata["fetch"] = fetch_metadata

    # Create folder for output if it does not exist
    Path(output).mkdir(parents=True, exist_ok=True)

    # Save raw results
    with (Path(output) / "raw_response.json").open("w") as f:
        json.dump(response, f, indent=2, default=str)
    parse_format = normalize_parse_format(export_format) or "dataframe"
    export_data, parsed_metadata = instance.parse(
        results=response,
        extract_fields=None,
        format=cast("Literal['json', 'dataframe', 'xml']", parse_format),
    )
    print(f"type of export_data: {type(export_data)}")
    metadata["parsing"] = parsed_metadata

    enriched_data = None
    if crossref_fields:
        logger.info("Running cross-reference enrichment...")
        enriched_data, enriched_metadata = run_crossref_enrichment(
            export_data,
            crossref_fields.split(","),
            format=cast("Literal['json', 'dataframe', 'xml']", parse_format),
        )
        metadata["enrichment"] = enriched_metadata

    if export_format in {"csv", "parquet"}:
        if isinstance(export_data, pd.DataFrame) and not export_data.empty:
            tabular_format = normalize_export_format(export_format)
            export_path = Path(output) / f"uniprot_results.{tabular_format}"
            export_dataframe(export_data, export_path, output_format=tabular_format)
            if isinstance(enriched_data, dict):
                for key, value in enriched_data.items():
                    logger.info(f"Saving {key} results into {output} directory")
                    export_dataframe(
                        value,
                        Path(output) / f"{key}_results.{tabular_format}",
                        output_format=tabular_format,
                    )

            with (Path(output) / "metadata.json").open("w") as f:
                json.dump(metadata, f, indent=2, default=str)
            logger.info(f"Results saved to {export_path}")
        else:
            logger.warning("No results to save in %s format.", export_format.upper())
    elif export_format == "json":
        if isinstance(export_data, (dict, list)):
            with (Path(output) / "uniprot_results.json").open("w") as f:
                json.dump(export_data, f, indent=2, default=str)

            if isinstance(enriched_data, dict):
                for key, value in enriched_data.items():
                    logger.info(f"Saving {key} results into {output} directory")
                    json.dump(value, (Path(output) / f"{key}_results.json").open("w"), indent=2, default=str)

            with (Path(output) / "metadata.json").open("w") as f:
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

            with (Path(output) / "metadata.json").open("w") as f:
                json.dump(metadata, f, indent=2, default=str)
            logger.info(f"Results saved to {output}/uniprot_results.xml")
        else:
            logger.warning("No results to save in XML format.")
    else:
        logger.warning(export_format)
        logger.warning("No UniProt data found for the BLAST results.")
