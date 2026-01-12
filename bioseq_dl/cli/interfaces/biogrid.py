import typer
import os
import pandas as pd

from bioseq_dl import BioGRIDInterface

app = typer.Typer(help="Fetch data from BioGRID database.")


@app.command("interactions")
def run_interactions(
    gene_list: str = typer.Option(
        None, "--gene-list", "-gl",
        help="Comma-separated list of gene symbols to fetch interactions for."
    ),
    taxon_id: str = typer.Option(
        None, "--taxon_id", "-t",
        help="NCBI Taxonomy ID to filter results by organism."
    ),
    access_key: str = typer.Option(
        None, "--access_key", "-ak",
        help="BioGRID API key to make authenticated requests"
    ),
    output: str = typer.Option(
        None, "--output", "-out",
        help="Output file to save the fetched data.",
    )
):
    """Fetch interaction data from BioGRID database."""
    if access_key is None:
        access_key = os.getenv("biogrid_api_key", None)
        if access_key is None:
            raise ValueError("An access key is required. Provide it via --access_key or set the biogrid_api_key environment variable.")

    instance = BioGRIDInterface()

    query = {}

    if gene_list:
        query["geneList"] = gene_list.split(",")
    if taxon_id:
        query["taxId"] = taxon_id

    df = pd.DataFrame(instance.fetch_single(
        query=query,
        method="interactions",
        parse=True,
        format="dataframe"
    ))

    if output:
        df.to_csv(output, index=False)
    else:
        print(df.head(5))