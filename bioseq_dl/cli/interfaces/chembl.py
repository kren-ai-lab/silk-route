import typer

from bioseq_dl import ChEMBLInterface

app = typer.Typer(help="Collect data from the ChEMBL database.")

@app.command("activity")
def run_activity(
    chembl_id: str = typer.Argument(..., help="ChEMBL ID of the compound (e.g., CHEMBL25)"),
    p_value: float = typer.Option(None, "--p-value", help="Minimum p-value threshold for filtering activities (optional)"),
    output: str = typer.Option(None, help="Output file to save the results (optional)")
):
    """Fetch activity information by ChEMBL ID."""
    interface = ChEMBLInterface()

    query = {}
    query["target_chembl_id"] = chembl_id
    if p_value is not None:
        query["p_value"] = p_value
    result = interface.fetch_single(
        method="activity",
        query=query,
        pages_to_fetch=1,
        parse=True,
        to_dataframe=True
    )

    if output:
        result.to_csv(output, index=False)
    else:
        typer.echo(result)

@app.command("binding_site")
def run_binding_site(
    chembl_id: str = typer.Argument(..., help="ChEMBL ID of the compound (e.g., CHEMBL25)"),
    output: str = typer.Option(None, help="Output file to save the results (optional)")
):
    """Fetch binding site information by ChEMBL ID."""
    interface = ChEMBLInterface()

    query = {}
    query["target_chembl_id"] = chembl_id
    result = interface.fetch_single(
        method="binding_site",
        query=query,
        pages_to_fetch=1,
        parse=True,
        to_dataframe=True
    )

    if output:
        result.to_csv(output, index=False)
    else:
        typer.echo(result.head(5))