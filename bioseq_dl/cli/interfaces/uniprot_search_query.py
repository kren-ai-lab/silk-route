"""UniProt query search CLI commands."""

import json
import logging
from pathlib import Path
from typing import Any, Literal, cast

import typer

from bioseq_dl import UniprotInterface
from bioseq_dl.cli._shared import output_dir_option, save_uniprot_results
from bioseq_dl.constants.uniprot import VALID_FIELDS, XREF_MAPPING
from bioseq_dl.core.export import (
    USER_EXPORT_FORMATS,
    normalize_parse_format,
    normalize_user_export_format,
)
from bioseq_dl.core.utils.crossref_enrichment import run_crossref_enrichment
from bioseq_dl.logging import configure_logging, get_logger

log = get_logger("bioseq_dl.cli.uniprot_search_query")


def run(
    output: str = output_dir_option(),
    query: str = typer.Option(..., "-q", "--query", help="Query to search for"),
    fields: str = typer.Option(
        ",".join(VALID_FIELDS), "-f", "--fields", help="Fields to include in the output"
    ),
    crossref_fields: str = typer.Option(
        "",
        "-xr",
        "--crossref-fields",
        help="Cross reference fields to include in the output, options: "
        + ", ".join([xref[1] for xref in XREF_MAPPING.values()]),
    ),
    sort: str = typer.Option("accession asc", "-s", "--sort", help="Sort order for the results"),
    include_isoform: bool = typer.Option(False, "--include-isoform", help="Include isoforms in the results"),
    concat_results: bool = typer.Option(
        False, "--concat-results", help="Concatenate cross-reference results into a single DataFrame"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
    export_format: str = typer.Option(
        "csv",
        "-ef",
        "--export-format",
        help="Export format: csv, json, xml, parquet. Default is csv.",
    ),
) -> None:
    """Run a UniProt text search query."""
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

    logger.info(
        "Starting UniProt search with query: %s with parameters "
        "fields=%s, crossref_fields=%s, sort=%s, include_isoform=%s, concat_results=%s",
        query,
        fields,
        crossref_fields,
        sort,
        include_isoform,
        concat_results,
    )
    metadata: dict[str, Any] = {}
    instance = UniprotInterface()
    logger.debug(
        "Downloading data using\nquery %s\nfields %s\ncrossref_fields %s\n"
        "format %s\nsort %s\ninclude_isoform %s",
        query,
        fields,
        crossref_fields,
        format,
        sort,
        include_isoform,
    )
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

    Path(output).mkdir(parents=True, exist_ok=True)

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

    save_uniprot_results(export_data, enriched_data, metadata, output, export_format, logger)
