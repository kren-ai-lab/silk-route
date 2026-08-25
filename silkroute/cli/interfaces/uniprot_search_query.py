"""UniProt query search CLI commands."""

from typing import Any

import typer

from silkroute import UniprotInterface
from silkroute.cli._shared import output_dir_option, parse_and_save_uniprot, validate_export_format
from silkroute.constants.uniprot import (
    VALID_FIELDS,
    XREF_MAPPING,
    get_effective_uniprot_return_fields,
    normalize_uniprot_return_fields,
)
from silkroute.logging import get_logger

log = get_logger("silkroute.cli.uniprot_search_query")


def run(
    output: str = output_dir_option(),
    query: str = typer.Option(..., "-q", "--query", help="Query to search for"),
    fields: str | None = typer.Option(None, "-f", "--fields", help="Fields to include in the output"),
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
    export_format: str = typer.Option(
        "csv",
        "-ef",
        "--export-format",
        help="Export format: csv, json, xml, parquet. Default is csv.",
    ),
) -> None:
    """Run a UniProt text search query."""
    export_format = validate_export_format(export_format)

    log.info(
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
    request_fields = fields if normalize_uniprot_return_fields(fields) else ",".join(VALID_FIELDS)
    effective_fields = ",".join(get_effective_uniprot_return_fields(request_fields, crossref_fields))

    response, fetch_metadata = instance.submit_search(
        query=query,
        fields=effective_fields,
        sort=sort,
        include_isoform=include_isoform,
    )
    metadata["fetch"] = fetch_metadata

    parse_and_save_uniprot(
        instance,
        response,
        metadata,
        fields=fields,
        crossref_fields=crossref_fields,
        output=output,
        export_format=export_format,
        logger=log,
    )
