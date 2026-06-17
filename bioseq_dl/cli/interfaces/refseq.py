"""RefSeq CLI commands."""

import typer

from bioseq_dl import RefSeqInterface
from bioseq_dl.cli._shared import format_option, output_option, save_or_print

app = typer.Typer(help="Collect data from RefSeq database.")


@app.command("protein")
def run_protein(
    identifier: str = typer.Argument(..., help="Comma-separated list of RefSeq protein IDs"),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch protein data from RefSeq."""
    interface = RefSeqInterface()

    result = interface.fetch_single(
        query=identifier.split(","), method="protein", parse=True, format="dataframe"
    )

    save_or_print(result, output, output_format=output_format)


@app.command("gene")
def run_gene(
    identifier: str = typer.Argument(..., help="Comma-separated list of RefSeq gene IDs"),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch gene data from RefSeq."""
    interface = RefSeqInterface()

    result = interface.fetch_single(
        query=identifier.split(","), method="gene", parse=True, format="dataframe"
    )

    save_or_print(result, output, output_format=output_format)


@app.command("popset")
def run_popset(
    identifier: str = typer.Argument(..., help="Comma-separated list of RefSeq popset IDs"),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch popset data from RefSeq."""
    interface = RefSeqInterface()

    result = interface.fetch_single(
        query=identifier.split(","), method="popset", parse=True, format="dataframe"
    )

    save_or_print(result, output, output_format=output_format)
