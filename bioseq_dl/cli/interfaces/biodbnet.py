"""BioDBNet CLI commands."""

import pandas as pd
import typer

from bioseq_dl import BioDBNetInterface
from bioseq_dl.cli._shared import format_option, output_option, save_or_print
from bioseq_dl.constants.biodbnet import inputs as biodbnet_inputs
from bioseq_dl.constants.biodbnet import outputs as biodbnet_outputs

app = typer.Typer(help="Fetch data from BioDBNet database.")


@app.command("db2db")
def run_db2db(
    input_type: str = typer.Option(
        "genesymbol", "--input", "-i", help=f"Type of input identifier. Options: {', '.join(biodbnet_inputs)}"
    ),
    value: str = typer.Option(
        ..., "--value", "-v", help="Identifier value(s), comma-separated for multiple values."
    ),
    outputs: str = typer.Option(
        "affyid,genesymbol,go-biologicalprocess",
        "--outputs",
        "-o",
        help=f"Type of output identifier(s). Options: {', '.join(biodbnet_outputs)}",
    ),
    taxon_id: int = typer.Option(
        None, "--taxon_id", "-t", help="NCBI Taxonomy ID to filter results by organism."
    ),
    output: str = output_option(help="Output file to save the fetched data."),
    output_format: str = format_option(),
) -> None:
    """Convert identifiers between databases using BioDBnet db2db."""
    instance = BioDBNetInterface()

    df, _ = instance.fetch_single(
        query={"input": input_type, "inputValues": value.split(","), "outputs": outputs, "taxonId": taxon_id},
        method="db2db",
        parse=True,
        format="dataframe",
    )
    if isinstance(df, pd.DataFrame):
        df = df.dropna(axis=1, how="all")

    save_or_print(df, output, output_format=output_format)


@app.command("pathways")
def run_pathways(
    pathways: str = typer.Option(
        None, "--pathways", "-p", help="Filter results by specific pathway(s), comma-separated."
    ),
    taxon_id: int = typer.Option(
        None, "--taxon_id", "-t", help="NCBI Taxonomy ID to filter results by organism."
    ),
    output: str = output_option(help="Output file to save the fetched data."),
    output_format: str = format_option(),
) -> None:
    """Fetch pathway annotations for genes via BioDBnet."""
    instance = BioDBNetInterface()

    df, _ = instance.fetch_single(
        query={"pathways": pathways, "taxonId": taxon_id},
        method="getpathways",
        parse=True,
        format="dataframe",
    )
    if isinstance(df, pd.DataFrame):
        df = df.dropna(axis=1, how="all")

    save_or_print(df, output, output_format=output_format)
