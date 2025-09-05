import typer

from bioseq_dl import ReactomeInterface

app = typer.Typer(help="Collect data from Reactome database.")
@app.command("discover")
def run_discover(
    id: str = typer.Argument(..., help="Identifier to discover, e.g., R-DME-1834941"),
    output_file: str = typer.Option(None, help="Output file to save results"),
):
    """
    Discover data in Reactome using an identifier.
    """
    interface = ReactomeInterface()

    query = {"id": identifier.strip() for identifier in id.split(",")}

    result = interface.fetch_single(
        query,
        method="data-discover",
        parse=True,
        to_dataframe=True
    )

    if output_file:
        result.to_csv(output_file, index=False)
        typer.echo(f"Results saved to {output_file}")
    else:
        typer.echo(result.head(5))