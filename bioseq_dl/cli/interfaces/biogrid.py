import typer

from bioseq_dl import BioGRIDInterface
from bioseq_dl.cli._shared import save_or_print

app = typer.Typer(help="Fetch data from BioGRID database.")


@app.command("interactions")
def run_interactions(
    gene_list: str = typer.Option(
        None, "--gene-list", "-gl", help="Comma-separated list of gene symbols to fetch interactions for."
    ),
    taxon_id: str = typer.Option(
        None, "--taxon_id", "-t", help="NCBI Taxonomy ID to filter results by organism."
    ),
    access_key: str = typer.Option(
        None, "--access_key", "-ak", help="BioGRID API key to make authenticated requests"
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-out",
        help="Output file to save the fetched data.",
    ),
):
    """Fetch interaction data from BioGRID database."""
    instance = BioGRIDInterface(api_key=access_key)

    query = {}

    if gene_list:
        query["geneList"] = gene_list.split(",")
    if taxon_id:
        query["taxId"] = taxon_id

    df = instance.fetch_single(query=query, method="interactions", parse=True, format="dataframe")

    save_or_print(df, output)
