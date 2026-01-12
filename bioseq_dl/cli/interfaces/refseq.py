import typer

from bioseq_dl import RefSeqInterface

app = typer.Typer(help="Collect data from RefSeq database.")

@app.command("protein")
def run_protein(
    id: str = typer.Argument(..., help="Comma-separated list of RefSeq protein IDs"),
    output_file: str = typer.Option(None, help="Output file to save results")
):
    """
    Fetch protein data from RefSeq.
    """
    interface = RefSeqInterface()

    result = interface.fetch_single(
        query=id.split(","),
        method="protein",
        parse=True,
        format="dataframe"
    )

    if output_file:
        result.to_csv(output_file, index=False)
        typer.echo(f"Results saved to {output_file}")
    else:
        typer.echo(result.head(5))

@app.command("gene")
def run_gene(
    id: str = typer.Argument(..., help="Comma-separated list of RefSeq gene IDs"),
    output_file: str = typer.Option(None, help="Output file to save results")
):
    """
    Fetch gene data from RefSeq.
    """
    interface = RefSeqInterface()

    result = interface.fetch_single(
        query=id.split(","),
        method="gene",
        parse=True,
        format="dataframe"
    )

    if output_file:
        result.to_csv(output_file, index=False)
        typer.echo(f"Results saved to {output_file}")
    else:
        typer.echo(result.head(5))

@app.command("popset")
def run_popset(
    id: str = typer.Argument(..., help="Comma-separated list of RefSeq popset IDs"),
    output_file: str = typer.Option(None, help="Output file to save results")
):
    """
    Fetch popset data from RefSeq.
    """
    interface = RefSeqInterface()

    result = interface.fetch_single(
        query=id.split(","),
        method="popset",
        parse=True,
        format="dataframe"
    )

    if output_file:
        result.to_csv(output_file, index=False)
        typer.echo(f"Results saved to {output_file}")
    else:
        typer.echo(result.head(5))
