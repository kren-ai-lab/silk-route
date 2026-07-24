"""UniProt sequence search CLI commands."""

import shutil
from pathlib import Path
from typing import Any

import polars as pl
import typer

from silkroute import UniprotInterface
from silkroute.cli._shared import output_dir_option, parse_and_save_uniprot, validate_export_format
from silkroute.constants.uniprot import DATABASES, XREF_MAPPING
from silkroute.core.export import export_dataframe
from silkroute.core.utils.blast_search import (
    check_blast,
    download_uniprot_database,
    make_blast_database,
    parse_blast_results,
    run_blast,
)
from silkroute.core.utils.frames import records_to_frame
from silkroute.logging import get_logger

log = get_logger("silkroute.cli.uniprot_search_sequences")


def run(
    database: str = typer.Option(
        ...,
        "--database",
        "-d",
        help="Database to download. Supported databases: " + ", ".join(DATABASES.keys()),
    ),
    extension: str = typer.Option(
        "fasta", "--extension", "-e", help="File extension of the database. Default is 'fasta'."
    ),
    input_file: str = typer.Option(..., "--input", "-i", help="File with sequences to run BLAST on."),
    seq_column: str = typer.Option("sequences", "--seq-column", "-c", help="Column name with sequences."),
    output: str = output_dir_option(),
    evalue: float = typer.Option(0.001, "--evalue", "-v", help="E-value threshold for BLAST search."),
    blast_type: str = typer.Option(
        "blastp", "--blast-type", "-b", help="Type of BLAST to run. Default is 'blastp'."
    ),
    no_download: bool = typer.Option(
        False, "--no-download", "-u", help="If set, will not download information from UniProt after BLAST."
    ),
    crossref_fields: str = typer.Option(
        "",
        "-xr",
        "--crossref-fields",
        help="Cross reference fields to include in the output, options: "
        + ", ".join([xref[1] for xref in XREF_MAPPING.values()]),
    ),
    min_identity: float = typer.Option(
        90.0, "--min-identity", help="Minimum identity threshold for BLAST search."
    ),
    min_coverage: float = typer.Option(
        0.0, "--min-coverage", help="Minimum coverage threshold for BLAST search."
    ),
    export_format: str = typer.Option(
        "csv",
        "-ef",
        "--export-format",
        help="Export format: csv, json, xml, parquet. Default is csv.",
    ),
) -> None:
    """Run UniProt BLAST-based sequence search."""
    export_format = validate_export_format(export_format)

    df = pl.read_csv(input_file)

    if seq_column not in df.columns:
        msg = f"Column '{seq_column}' not found in input file."
        raise ValueError(msg)

    sequences = df[seq_column].drop_nulls().unique(maintain_order=True).to_list()

    download_uniprot_database(database, extension)

    blast_path = check_blast(blast_type)

    make_blast_database(database, extension=extension)

    run_blast(sequences, database, blast_path, evalue=evalue)

    results = parse_blast_results("tmp/blast_results.txt")

    # Convert to DataFrame
    sequences_df = (
        pl.DataFrame({seq_column: sequences}).with_row_index("id").with_columns(pl.col("id").cast(pl.Int64))
    )

    df_blast = records_to_frame(results)

    if df_blast.is_empty():
        log.warning("No BLAST hits found; writing empty results.")
        Path(output).mkdir(parents=True, exist_ok=True)
        blast_path = export_dataframe(df_blast, Path(output) / "blast_results.csv")
        log.info("BLAST results saved to %s", blast_path)
        Path("tmp/blast_results.txt").unlink()
        shutil.rmtree("tmp")
        return

    df_blast = df_blast.rename({"query": "id", "subject": "subject_id"})
    df_blast = df_blast.with_columns(pl.col("id").cast(pl.Int64))
    df_blast = df_blast.join(sequences_df, on="id", how="left")
    df_blast = df_blast.drop("id")
    df_blast = df_blast.rename({seq_column: "sequence"})

    # Cast then filter numeric thresholds before exporting or enriching
    for col, threshold in (("identity", min_identity), ("coverage", min_coverage)):
        if col in df_blast.columns:
            df_blast = df_blast.with_columns(pl.col(col).cast(pl.Float64, strict=False)).filter(
                pl.col(col) >= threshold
            )

    # Separate subject into source, accession, entry_name
    parts = pl.col("subject_id").str.split("|")
    df_blast = df_blast.with_columns(
        parts.list.get(0).alias("source"),
        parts.list.get(1).alias("accession"),
        parts.list.get(2).alias("entry_name"),
    ).drop("subject_id")

    # Create folder for output if it does not exist
    Path(output).mkdir(parents=True, exist_ok=True)

    # Save to CSV
    blast_path = export_dataframe(df_blast, Path(output) / "blast_results.csv")
    log.info("BLAST results saved to %s", blast_path)

    # Clean up temporary files
    Path("tmp/blast_results.txt").unlink()
    shutil.rmtree("tmp")

    if not no_download:
        metadata: dict[str, Any] = {}
        log.info("Downloading additional UniProt data...")
        instance = UniprotInterface()
        log.debug("Downloading data using blast results\ncrossref_fields %s\n", crossref_fields)

        response, fetch_metadata = instance.download_batch(
            df_blast, "accession", True, "UniProtKB_AC-ID", "UniProtKB", 5000
        )
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
