"""UniProt ID search CLI commands."""

import json
import logging
from pathlib import Path
from typing import Literal, cast

import pandas as pd
import typer

from bioseq_dl import UniprotInterface
from bioseq_dl.cli._shared import save_uniprot_results
from bioseq_dl.constants.uniprot import VALID_CROSS_REF_FIELDS, VALID_FIELDS
from bioseq_dl.core.export import (
    USER_EXPORT_FORMATS,
    normalize_parse_format,
    normalize_user_export_format,
)
from bioseq_dl.core.utils.crossref_enrichment import run_crossref_enrichment
from bioseq_dl.logging import configure_logging, get_logger

app = typer.Typer(help="Search and download sequences from UniProt using IDs.")

log = get_logger("bioseq_dl.cli.uniprot_search_ids")


@app.command()
def run(
    input_file: str = typer.Option(..., "-i", "--input", help="CSV file with UniProt IDs"),
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
    """Run UniProt search from a list of accession IDs."""
    logger = log
    raw_export_format = export_format
    try:
        normalized_format = normalize_user_export_format(export_format)
        if normalized_format is None:
            msg = (
                f"Unsupported export format '{raw_export_format}'. Supported formats are: "
                f"{', '.join(USER_EXPORT_FORMATS)}."
            )
            raise ValueError(msg)  # noqa: TRY301  # validate-then-Exit CLI idiom
        export_format = normalized_format
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
    except Exception as e:  # noqa: BLE001  # defensive catch-all
        logger.warning("Could not configure logging: %s", e)

    df = pd.read_csv(input_file)

    # Filter by identity if present
    if min_identity is not None and "identity" in df.columns:
        df = df[df["identity"] >= min_identity]

    metadata = {}
    log.info("Downloading additional UniProt data...")
    instance = UniprotInterface()
    logger.debug(
        "Downloading data using blast results\nfields %s\ncrossref_fields %s\n", fields, crossref_fields
    )

    response, fetch_metadata = instance.download_batch(df, column, auto_db, from_db, to_db, batch_size)
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
        fmt=cast("Literal['json', 'dataframe', 'xml']", parse_format),
    )
    print(f"type of export_data: {type(export_data)}")
    metadata["parsing"] = parsed_metadata

    enriched_data = None
    if crossref_fields:
        logger.info("Running cross-reference enrichment...")
        enriched_data, enriched_metadata = run_crossref_enrichment(
            export_data,
            crossref_fields.split(","),
            fmt=cast("Literal['json', 'dataframe', 'xml']", parse_format),
        )
        metadata["enrichment"] = enriched_metadata

    save_uniprot_results(export_data, enriched_data, metadata, output, export_format, logger)
