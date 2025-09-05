import typer

from bioseq_dl import StringInterface

app = typer.Typer(help="Collect data from STRING database.")

@app.command("get-string-ids")
def run_get_string_ids(
    identifiers: str = typer.Argument(..., help="Comma-separated list of gene/protein identifiers"),
    species: int = typer.Option(None, help="NCBI taxonomy identifier of the species"),
    output_file: str = typer.Option(None, help="Output file to save results")
):
    """
    Fetch STRING IDs for given gene/protein identifiers.
    """
    interface = StringInterface()

    query = {}

    query["identifiers"] = identifiers.split(",")
    if species:
        query["species"] = species
    
    result = interface.fetch_single(
        query=query,
        method="get_string_ids",
        parse=True,
        to_dataframe=True
    )

    if output_file:
        result.to_csv(output_file, index=False)
        typer.echo(f"Results saved to {output_file}")
    else:
        typer.echo(result.head(5))
    
@app.command("interaction-partners")
def run_interaction_partners(
    identifiers: str = typer.Argument(..., help="Comma-separated list of STRING IDs"),
    species: int = typer.Option(None, help="NCBI taxonomy identifier of the species"),
    output_file: str = typer.Option(None, help="Output file to save results")
):
    """
    Fetch interaction partners for given STRING IDs.
    """
    interface = StringInterface()

    query = {}

    query["identifiers"] = identifiers.split(",")
    if species:
        query["species"] = species
    
    result = interface.fetch_single(
        query=query,
        method="interaction_partners",
        parse=True,
        to_dataframe=True
    )

    if output_file:
        result.to_csv(output_file, index=False)
        typer.echo(f"Results saved to {output_file}")
    else:
        typer.echo(result.head(5))