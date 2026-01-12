import os
import typer
import pandas as pd
from typing import List

from bioseq_dl import BioDBNetInterface
from bioseq_dl.constants.biodbnet import inputs as biodbnet_inputs, outputs as biodbnet_outputs

app = typer.Typer(help="Fetch data from BioDBNet database.")

@app.command("db2db")
def run_db2db(
    input: str = typer.Option(
        "genesymbol", "--input", "-i",
        help=f"Type of input identifier. Options: {', '.join(biodbnet_inputs)}"
    ),
    value: str = typer.Option(
        ..., "--value", "-v",
        help="Identifier value(s), comma-separated for multiple values."
    ),
    outputs: str = typer.Option(
        "affyid,genesymbol,go-biologicalprocess", "--outputs", "-o",
        help=f"Type of output identifier(s). Options: {', '.join(biodbnet_outputs)}"
    ),
    taxon_id: int = typer.Option(
        None, "--taxon_id", "-t",
        help="NCBI Taxonomy ID to filter results by organism."
    ),
    output: str = typer.Option(
        None, "--output", "-out",
        help="Output file to save the fetched data.",
    )
):
    """Fetch interaction data from BioGRID database."""
    instance = BioDBNetInterface()

    df = pd.DataFrame(instance.fetch_single(

        query={
            "input": input,
            "inputValues": value.split(","),
            "outputs": outputs,
            "taxonId": taxon_id
        },
        method="db2db",
        parse=True,
        format="dataframe"
    )).dropna(axis=1, how='all')

    if output:
        df.to_csv(output, index=False)
    else:
        print(df.head(5))



@app.command("pathways")
def run_pathways(
    pathways: str = typer.Option(
        None, "--pathways", "-p",
        help="Filter results by specific pathway(s), comma-separated."
    ),
    taxon_id: int = typer.Option(
        None, "--taxon_id", "-t",
        help="NCBI Taxonomy ID to filter results by organism."
    ),
    output: str = typer.Option(
        None, "--output", "-out",
        help="Output file to save the fetched data.",
    )

):
    """Fetch interaction data from BioGRID database."""
    instance = BioDBNetInterface()

    df = pd.DataFrame(instance.fetch_single(

        query={
            "input": input,
            "pathways": pathways,
            "taxonId": taxon_id
        },
        method="getpathways",
        parse=True,
        format="dataframe"
    )).dropna(axis=1, how='all')

    if output:
        df.to_csv(output, index=False)
    else:
        print(df.head(5))

