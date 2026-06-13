import typer

from bioseq_dl import RheaInterface

app = typer.Typer(help="Collect data from Rhea database.")


@app.command("search")
def run_search(
    q: str = typer.Argument(..., help="Rhea reaction ID"),
    columns: str = typer.Option(None, help="Columns to fetch"),
    output_file: str = typer.Option(None, help="Output file to save results"),
):
    """Fetch reaction data from Rhea."""
    interface = RheaInterface()

    query = {}

    query["query"] = q

    if columns:
        query["columns"] = columns

    result = interface.fetch_single(query=query, method="rhea", parse=True, format="dataframe")

    if output_file:
        result.to_csv(output_file, index=False)
        typer.echo(f"Results saved to {output_file}")
    else:
        typer.echo(result.head(5))
