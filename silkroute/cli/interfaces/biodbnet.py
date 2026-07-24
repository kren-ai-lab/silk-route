"""BioDBNet CLI commands."""

import polars as pl
import typer

from silkroute import BioDBNetInterface
from silkroute.cli._shared import format_option, output_option, save_or_print
from silkroute.constants.biodbnet import inputs as biodbnet_inputs
from silkroute.constants.biodbnet import outputs as biodbnet_outputs
from silkroute.core.utils.frames import drop_all_null_columns

app = typer.Typer(help="Fetch data from BioDBNet database.")


@app.command("db2db")
def run_db2db(
    value: str = typer.Argument(..., help="Identifier value(s), comma-separated for multiple values."),
    input_type: str = typer.Option(
        "genesymbol", "--input", "-i", help=f"Type of input identifier. Options: {', '.join(biodbnet_inputs)}"
    ),
    outputs: str = typer.Option(
        "affyid,genesymbol,go-biologicalprocess",
        "--outputs",
        "-o",
        help=f"Type of output identifier(s). Options: {', '.join(biodbnet_outputs)}",
    ),
    taxon_id: int = typer.Option(
        None, "--taxon-id", "-t", help="NCBI Taxonomy ID to filter results by organism."
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
    if isinstance(df, pl.DataFrame):
        df = drop_all_null_columns(df)

    save_or_print(df, output, output_format=output_format)


@app.command("pathways")
def run_pathways(
    pathways: str = typer.Option(
        None, "--pathways", "-p", help="Filter results by specific pathway(s), comma-separated."
    ),
    taxon_id: int = typer.Option(
        None, "--taxon-id", "-t", help="NCBI Taxonomy ID to filter results by organism."
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
    if isinstance(df, pl.DataFrame):
        df = drop_all_null_columns(df)

    save_or_print(df, output, output_format=output_format)
