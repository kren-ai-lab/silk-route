"""Rhea CLI commands."""

import typer

from bioseq_dl import RheaInterface
from bioseq_dl.cli._shared import format_option, output_option, save_or_print

app = typer.Typer(help="Collect data from Rhea database.")


@app.command("search")
def run_search(
    q: str = typer.Argument(..., help="Rhea reaction ID"),
    columns: str = typer.Option(None, help="Columns to fetch"),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch reaction data from Rhea."""
    interface = RheaInterface()

    query = {"query": q}
    if columns:
        query["columns"] = columns

    result = interface.fetch_single(query=query, method="rhea", parse=True, format="dataframe")

    save_or_print(result, output, output_format=output_format)
