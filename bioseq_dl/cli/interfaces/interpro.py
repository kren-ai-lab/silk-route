import typer

from bioseq_dl import InterproInterface
from bioseq_dl.cli._shared import save_or_print

app = typer.Typer(help="Fetch data from InterPro database.")


@app.command("entry")
def run_entry(
    id: str = typer.Option(None, "--id", "-id", help="InterPro entry ID to fetch."),
    db: str = typer.Option(
        None, "--db", "-db", help="Specific database within InterPro to query (e.g., InterPro)."
    ),
    filter_uniprot_accession: str = typer.Option(
        None, "--filter-uniprot-accession", "-fua", help="Filter results by a specific UniProt accession."
    ),
    filter_taxonomy: str = typer.Option(
        None, "--filter-taxonomy", "-ft", help="Filter results by a specific taxonomy ID."
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file to save the fetched data.",
    ),
):
    """Fetch data from InterPro database."""
    instance = InterproInterface()

    query = {}

    if id:
        query["id"] = id
    if db:
        query["db"] = db
    if filter_uniprot_accession:
        query["filters"] = [{"type": "protein", "db": "reviewed", "value": filter_uniprot_accession}]
    if filter_taxonomy:
        if "filters" not in query:
            query["filters"] = []
        query["filters"].append({"type": "taxonomy", "db": "uniprot", "value": int(filter_taxonomy)})

    df = instance.fetch_single(query=query, method="entry", parse=True, format="dataframe")

    save_or_print(df, output)
