"""UniProt cross-reference CLI commands."""

# silkroute/cli/uniprot_crossref.py
from pathlib import Path

import polars as pl
import typer

from silkroute.cli._shared import write_output_provenance
from silkroute.constants.uniprot import XREF_MAPPING
from silkroute.core.crossref_enricher import CrossRefEnricher, specs_for_database
from silkroute.core.export import export_dataframe
from silkroute.core.interfacesconfig import load_packaged_config
from silkroute.logging import get_logger

log = get_logger("silkroute.cli.uniprot_crossref")

CROSS_REF_FIELDS = [xref.lower() for xref in XREF_MAPPING]


def save_to_file(
    df: pl.DataFrame, out_dir: str, filename: str, db: str, endpoint: str, option: str | None
) -> None:
    """Save a cross-reference result DataFrame to a CSV file under ``out_dir/filename``.

    Args:
        df (pl.DataFrame): The results to save.
        out_dir (str): Base output directory.
        filename (str): Subfolder name (typically the input file stem).
        db (str): Database name, used in the output file name.
        endpoint (str): Endpoint name, used in the output file name.
        option (str | None): Optional variant, included in the file name when set.

    """
    # Make folder with filename
    (Path(out_dir) / filename).mkdir(parents=True, exist_ok=True)
    # Save the DataFrame to a CSV file
    if option is None:
        output_file = Path(out_dir) / filename / f"{db}_{endpoint}_results.csv"
    else:
        output_file = Path(out_dir) / filename / f"{db}_{endpoint}_{option}_results.csv"
    export_dataframe(df, output_file, output_format="csv")
    log.info("Results for %s with option %s saved to %s", db, option, output_file)


def run(
    input_file: str = typer.Option(
        ...,
        "--input",
        "-i",
        help="Input file with UniProt IDs.",
        case_sensitive=True,
    ),
    out_dir: str = typer.Option(
        ...,
        "--output-dir",
        "-o",
        help="Output directory for results.",
        case_sensitive=True,
    ),
    databases: str = typer.Option(
        "all",
        "--databases",
        "-d",
        help="List of databases to query separated by commas, or 'all' to query all databases. Options: "
        + ", ".join(CROSS_REF_FIELDS),
        case_sensitive=False,
    ),
) -> None:
    """Run UniProt cross-reference name mapping."""
    if not Path(input_file).exists():
        msg = f"Input file {input_file} does not exist."
        raise typer.BadParameter(msg)

    df = pl.read_csv(input_file)

    endpoints_config = load_packaged_config("uniprot_crossref", "config_endpoints.yml") or {}

    if databases == "all":
        databases = ",".join(CROSS_REF_FIELDS)

    endpoint_specs = []
    # Generate the endpoint specs based on selected crossref fields
    for xref in databases.split(","):
        if xref in CROSS_REF_FIELDS:
            endpoint_specs.extend(specs_for_database(endpoints_config.get(xref), xref))

    if not endpoint_specs:
        msg = "No valid endpoint specifications found. Check your database selections and configuration."
        raise typer.BadParameter(msg)
    log.debug("Endpoint specifications: %s", endpoint_specs)
    enricher = CrossRefEnricher(endpoint_specs)
    enriched_data, enriched_metadata = enricher.enrich(df)

    if isinstance(enriched_data, pl.DataFrame) and not enriched_data.is_empty():
        log.info("Crossref enrichment resulted in %s rows", enriched_data.height)
        # Create output directory if it doesn't exist
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        results_path = Path(out_dir) / f"{Path(input_file).stem}_results.csv"
        export_dataframe(enriched_data, results_path, output_format="csv")
        log.info("Results saved to %s", results_path)
        write_output_provenance(
            results_path, enriched_metadata, n_rows=enriched_data.height, n_cols=enriched_data.width
        )
    else:
        log.info("No results to save.")
