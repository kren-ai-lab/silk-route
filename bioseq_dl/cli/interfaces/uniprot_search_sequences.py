import json
import logging
import shutil
from pathlib import Path
from typing import Literal, cast

import pandas as pd
import typer

from bioseq_dl import UniprotInterface
from bioseq_dl.constants.uniprot import DATABASES, VALID_FIELDS, XREF_MAPPING
from bioseq_dl.core.export import (
    USER_EXPORT_FORMATS,
    export_dataframe,
    normalize_export_format,
    normalize_parse_format,
    normalize_user_export_format,
)
from bioseq_dl.core.utils.blast_search import (
    check_blast,
    download_uniprot_database,
    make_blast_database,
    parse_blast_results,
    run_blast,
)
from bioseq_dl.core.utils.crossref_enrichment import run_crossref_enrichment
from bioseq_dl.logging import configure_logging, get_logger

log = get_logger("bioseq_dl.cli.uniprot_search_sequences")

app = typer.Typer(
    help="Run BLAST alignment on sequences and [optionaly] download matching sequences from UniProt."
)


@app.command()
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
    input: str = typer.Option(..., "--input", "-i", help="File with sequences to run BLAST on."),
    seq_column: str = typer.Option("sequences", "--seq-column", "-c", help="Column name with sequences."),
    output: str = typer.Option(..., "-o", "--output", help="Output directory for results"),
    evalue: float = typer.Option(0.001, "--evalue", "-v", help="E-value threshold for BLAST search."),
    blast_type: str = typer.Option(
        "blastp", "--blast-type", "-b", help="Type of BLAST to run. Default is 'blastp'."
    ),
    no_download: bool = typer.Option(
        False, "--no-download", "-u", help="If set, will not download information from UniProt after BLAST."
    ),
    fields: str = typer.Option(
        ",".join(VALID_FIELDS), "-f", "--fields", help="Fields to include in the output"
    ),
    crossref_fields: str = typer.Option(
        "",
        "-xr",
        "--crossref_fields",
        help="Cross reference fields to include in the output, options: "
        + ", ".join([xref[1] for xref in XREF_MAPPING.values()]),
    ),
    min_identity: float = typer.Option(
        90.0, "--min_identity", help="Minimum identity threshold for BLAST search."
    ),
    min_coverage: float = typer.Option(
        0.0, "--min_coverage", help="Minimum coverage threshold for BLAST search."
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
    export_format: str = typer.Option(
        "csv",
        "-ef",
        "--export_format",
        help="Export format: csv, json, xml, parquet. Default is csv.",
    ),
):
    logger = log
    raw_export_format = export_format
    try:
        export_format = normalize_user_export_format(export_format)
        if export_format is None:
            raise ValueError(
                f"Unsupported export format '{raw_export_format}'. Supported formats are: {', '.join(USER_EXPORT_FORMATS)}."
            )
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

    if seq_column not in df.columns:
        raise ValueError(f"Column '{seq_column}' not found in input file.")

    sequences = df[seq_column].dropna().unique().tolist()

    download_uniprot_database(database, extension)

    blastp_path = check_blast()
    log.info(f"Using blastp at: {blastp_path}")

    make_blast_database(database, extension=extension)

    run_blast(sequences, database, blast_type=blast_type, evalue=evalue)

    results = parse_blast_results("tmp/blast_results.txt")

    # Convert to DataFrame
    sequences_df = pd.DataFrame(sequences, columns=[seq_column])
    sequences_df["id"] = sequences_df.index

    df_blast = pd.DataFrame(results)

    df_blast = df_blast.rename(columns={"query": "id", "subject": "subject_id"})
    df_blast["id"] = df_blast["id"].astype(int)
    df_blast = df_blast.merge(sequences_df, on="id", how="left")
    df_blast = df_blast.drop(columns=["id"])
    df_blast = df_blast.rename(columns={seq_column: "sequence"})

    # Filter by identity threshold before exporting or enriching
    if "identity" in df_blast.columns:
        df_blast["identity"] = pd.to_numeric(df_blast["identity"], errors="coerce")
        df_blast = df_blast[df_blast["identity"] >= min_identity]

    # Filter by coverage threshold before exporting or enriching
    if "coverage" in df_blast.columns:
        df_blast["coverage"] = pd.to_numeric(df_blast["coverage"], errors="coerce")
        df_blast = df_blast[df_blast["coverage"] >= min_coverage]

    # Separate subject into source, accession, entry_name
    df_blast["source"] = df_blast["subject_id"].apply(lambda x: x.split("|")[0])
    df_blast["accession"] = df_blast["subject_id"].apply(lambda x: x.split("|")[1])
    df_blast["entry_name"] = df_blast["subject_id"].apply(lambda x: x.split("|")[2])
    df_blast = df_blast.drop(columns=["subject_id"])

    # Create folder for output if it does not exist
    Path(output).mkdir(parents=True, exist_ok=True)

    # Save to CSV
    blast_path = export_dataframe(df_blast, Path(output) / "blast_results.csv")
    log.info(f"BLAST results saved to {blast_path}")

    # Clean up temporary files
    Path("tmp/blast_results.txt").unlink()
    shutil.rmtree("tmp")

    if not no_download:
        metadata = {}
        log.info("Downloading additional UniProt data...")
        instance = UniprotInterface()
        logger.debug(
            f"Downloading data using blast results\nfields {fields}\ncrossref_fields {crossref_fields}\n"
        )

        response, fetch_metadata = instance.download_batch(
            df_blast, "accession", True, "UniProtKB_AC-ID", "UniProtKB", 5000
        )
        metadata["fetch"] = fetch_metadata

        # Save raw results
        with (Path(output) / "raw_response.json").open("w") as f:
            json.dump(response, f, indent=2, default=str)

        logger.info("Parsing results...")
        parse_format = normalize_parse_format(export_format) or "dataframe"
        export_data, parsed_metadata = instance.parse(
            results=response,
            extract_fields=None,
            format=cast("Literal['json', 'dataframe', 'xml']", parse_format),
        )
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
                        json.dump(
                            value, (Path(output) / f"{key}_results.json").open("w"), indent=2, default=str
                        )

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
