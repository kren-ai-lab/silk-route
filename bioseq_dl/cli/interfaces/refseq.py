import typer

from bioseq_dl import RefSeqInterface
from bioseq_dl.cli._shared import save_or_print

app = typer.Typer(help="Collect data from RefSeq database.")


@app.command("protein")
def run_protein(
    id: str = typer.Argument(..., help="Comma-separated list of RefSeq protein IDs"),
    output_file: str = typer.Option(None, help="Output file to save results"),
):
    """Fetch protein data from RefSeq."""
    interface = RefSeqInterface()

    result = interface.fetch_single(query=id.split(","), method="protein", parse=True, format="dataframe")

    save_or_print(result, output_file)


@app.command("gene")
def run_gene(
    id: str = typer.Argument(..., help="Comma-separated list of RefSeq gene IDs"),
    output_file: str = typer.Option(None, help="Output file to save results"),
):
    """Fetch gene data from RefSeq."""
    interface = RefSeqInterface()

    result = interface.fetch_single(query=id.split(","), method="gene", parse=True, format="dataframe")

    save_or_print(result, output_file)


@app.command("popset")
def run_popset(
    id: str = typer.Argument(..., help="Comma-separated list of RefSeq popset IDs"),
    output_file: str = typer.Option(None, help="Output file to save results"),
):
    """Fetch popset data from RefSeq."""
    interface = RefSeqInterface()

    result = interface.fetch_single(query=id.split(","), method="popset", parse=True, format="dataframe")

    save_or_print(result, output_file)
