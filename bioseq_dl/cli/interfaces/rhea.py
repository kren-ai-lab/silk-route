"""Rhea CLI commands."""

import typer

from bioseq_dl import RheaInterface
from bioseq_dl.cli._shared import save_or_print

app = typer.Typer(help="Collect data from Rhea database.")


@app.command("search")
def run_search(
    q: str = typer.Argument(..., help="Rhea reaction ID"),
    columns: str = typer.Option(None, help="Columns to fetch"),
    output_file: str = typer.Option(None, help="Output file to save results"),
) -> None:
    """Fetch reaction data from Rhea."""
    interface = RheaInterface()

    query = {}

    query["query"] = q

    if columns:
        query["columns"] = columns

    result = interface.fetch_single(query=query, method="rhea", parse=True, format="dataframe")

    save_or_print(result, output_file)
