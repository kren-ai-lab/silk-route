"""UniProt ID search CLI commands."""

from typing import Any

import pandas as pd
import typer

from bioseq_dl import UniprotInterface
from bioseq_dl.cli._shared import output_dir_option, parse_and_save_uniprot, validate_export_format
from bioseq_dl.constants.uniprot import VALID_CROSS_REF_FIELDS
from bioseq_dl.logging import get_logger

log = get_logger("bioseq_dl.cli.uniprot_search_ids")


def run(
    input_file: str = typer.Option(..., "-i", "--input", help="CSV file with UniProt IDs"),
    column: str = typer.Option("accession", "-c", "--column", help="Column name with UniProt IDs"),
    output: str = output_dir_option(),
    from_db: str = typer.Option(
        "UniProtKB_AC-ID",
        "--from-db",
        help="Database to convert from. Default is UniProtKB_AC-ID (UniProtKB_AC-ID, PDB)",
    ),
    to_db: str = typer.Option("UniProtKB", "--to-db", help="Database to convert to"),
    crossref_fields: str = typer.Option(
        ",".join(VALID_CROSS_REF_FIELDS),
        "-xr",
        "--crossref-fields",
        help="Cross reference fields to include in the output",
    ),
    batch_size: int = typer.Option(5000, "-b", "--batch-size", help="Batch size for downloading"),
    auto_db: bool = typer.Option(False, "-a", "--auto-db", help="Automatically detect database type"),
    min_identity: float = typer.Option(
        None, "--min-identity", help="Minimum identity threshold for BLAST search."
    ),
    export_format: str = typer.Option(
        "csv",
        "-ef",
        "--export-format",
        help="Export format: csv, json, xml, parquet. Default is csv.",
    ),
) -> None:
    """Run UniProt search from a list of accession IDs."""
    export_format = validate_export_format(export_format)

    df = pd.read_csv(input_file)

    # Filter by identity if present
    if min_identity is not None and "identity" in df.columns:
        df = df[df["identity"] >= min_identity]

    metadata: dict[str, Any] = {}
    log.info("Downloading additional UniProt data...")
    instance = UniprotInterface()
    log.debug("Downloading data using blast results\ncrossref_fields %s\n", crossref_fields)

    response, fetch_metadata = instance.download_batch(df, column, auto_db, from_db, to_db, batch_size)
    metadata["fetch"] = fetch_metadata

    parse_and_save_uniprot(
        instance,
        response,
        metadata,
        crossref_fields=crossref_fields,
        output=output,
        export_format=export_format,
        logger=log,
    )
