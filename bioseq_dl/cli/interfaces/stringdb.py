"""STRING CLI commands."""

from typing import Any

import typer

from bioseq_dl import StringInterface
from bioseq_dl.cli._shared import format_option, output_option, save_or_print

app = typer.Typer(help="Collect data from STRING database.")


@app.command("get-string-ids")
def run_get_string_ids(
    identifiers: str = typer.Argument(..., help="Comma-separated list of gene/protein identifiers"),
    species: int = typer.Option(None, help="NCBI taxonomy identifier of the species"),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch STRING IDs for given gene/protein identifiers."""
    interface = StringInterface()

    query: dict[str, Any] = {"identifiers": identifiers.split(",")}
    if species:
        query["species"] = species

    result = interface.fetch_single(query=query, method="get_string_ids", parse=True, format="dataframe")

    save_or_print(result, output, output_format=output_format)


@app.command("interaction-partners")
def run_interaction_partners(
    identifiers: str = typer.Argument(..., help="Comma-separated list of STRING IDs"),
    species: int = typer.Option(None, help="NCBI taxonomy identifier of the species"),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch interaction partners for given STRING IDs."""
    interface = StringInterface()

    query: dict[str, Any] = {"identifiers": identifiers.split(",")}
    if species:
        query["species"] = species

    result = interface.fetch_single(
        query=query, method="interaction_partners", parse=True, format="dataframe"
    )

    save_or_print(result, output, output_format=output_format)
