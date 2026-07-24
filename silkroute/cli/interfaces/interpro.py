"""InterPro CLI commands."""

from typing import Any

import typer

from silkroute import InterproInterface
from silkroute.cli._shared import format_option, output_option, save_or_print

app = typer.Typer(help="Fetch data from InterPro database.")


@app.command("entry")
def run_entry(
    identifier: str = typer.Argument(
        None, help="InterPro entry ID to fetch (optional; omit to filter only)."
    ),
    db: str = typer.Option(
        None, "--db", "-db", help="Specific database within InterPro to query (e.g., InterPro)."
    ),
    filter_uniprot_accession: str = typer.Option(
        None, "--filter-uniprot-accession", "-fua", help="Filter results by a specific UniProt accession."
    ),
    filter_taxonomy: str = typer.Option(
        None, "--filter-taxonomy", "-ft", help="Filter results by a specific taxonomy ID."
    ),
    output: str = output_option(help="Output file to save the fetched data."),
    output_format: str = format_option(),
) -> None:
    """Fetch data from InterPro database."""
    instance = InterproInterface()

    query: dict[str, Any] = {}

    if identifier:
        query["id"] = identifier
    if db:
        query["db"] = db
    if filter_uniprot_accession:
        query["filters"] = [{"type": "protein", "db": "reviewed", "value": filter_uniprot_accession}]
    if filter_taxonomy:
        if "filters" not in query:
            query["filters"] = []
        query["filters"].append({"type": "taxonomy", "db": "uniprot", "value": str(int(filter_taxonomy))})

    df = instance.fetch_single(query=query, method="entry", parse=True, format="dataframe")

    save_or_print(df, output, output_format=output_format)
