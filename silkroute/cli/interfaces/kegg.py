"""KEGG CLI commands."""

from typing import Any

import typer

from silkroute import KEGGInterface
from silkroute.cli._shared import format_option, output_option, save_or_print

app = typer.Typer(help="Fetch data from KEGG database.")


@app.command("get")
def run_get(
    entries: str = typer.Argument(
        ..., help="Comma-separated KEGG entry IDs to fetch (e.g., hsa:10458,hsa:10459)."
    ),
    db: str = typer.Option(
        None, "--db", "-db", help="Specific KEGG database to query (e.g., genes, pathways)."
    ),
    option: str = typer.Option(
        None, "--option", "-opt", help="Additional option for the 'get' method (e.g., aaseq, ntseq)."
    ),
    output: str = output_option(help="Output file to save the fetched data."),
    output_format: str = format_option(),
) -> None:
    """Fetch data from KEGG database."""
    instance = KEGGInterface()

    query: dict[str, Any] = {}

    if entries:
        query["entries"] = entries.split(",")
    if db:
        query["db"] = db
    if option:
        query["option"] = option

    df = instance.fetch_single(query=query, method="get", parse=True, format="dataframe")

    save_or_print(df, output, output_format=output_format)
