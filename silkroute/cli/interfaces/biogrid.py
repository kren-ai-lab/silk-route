"""BioGRID CLI commands."""

from typing import Any

import typer

from silkroute import BioGRIDInterface
from silkroute.cli._shared import format_option, output_option, save_or_print

app = typer.Typer(help="Fetch data from BioGRID database.")


@app.command("interactions")
def run_interactions(
    gene_list: str = typer.Argument(
        ..., help="Comma-separated list of gene symbols to fetch interactions for."
    ),
    taxon_id: int = typer.Option(
        None, "--taxon-id", "-t", help="NCBI Taxonomy ID to filter results by organism."
    ),
    access_key: str = typer.Option(
        None, "--access-key", "-ak", help="BioGRID API key to make authenticated requests"
    ),
    output: str = output_option(help="Output file to save the fetched data."),
    output_format: str = format_option(),
) -> None:
    """Fetch interaction data from BioGRID database."""
    instance = BioGRIDInterface(api_key=access_key)

    query: dict[str, Any] = {}

    if gene_list:
        query["geneList"] = gene_list.split(",")
    if taxon_id:
        query["taxId"] = taxon_id

    df = instance.fetch_single(query=query, method="interactions", parse=True, format="dataframe")

    save_or_print(df, output, output_format=output_format)
