import typer

from bioseq_dl import KEGGInterface

app = typer.Typer(help="Fetch data from KEGG database.")
@app.command("get")
def run_get(
    entries: str = typer.Argument(
        ...,
        help="Comma-separated KEGG entry IDs to fetch (e.g., hsa:10458,hsa:10459)."
    ),
    db: str = typer.Option(
        None, "--db", "-db",
        help="Specific KEGG database to query (e.g., genes, pathways)."
    ),
    option: str = typer.Option(
        None, "--option", "-opt",
        help="Additional option for the 'get' method (e.g., aaseq, ntseq)."
    ),
    output: str = typer.Option(
        None, "--output", "-o",
        help="Output file to save the fetched data.",
    )
):
    """Fetch data from KEGG database."""
    instance = KEGGInterface()

    query = {}

    if entries:
        query['entries'] = entries.split(',')
    if db:
        query['db'] = db
    if option:
        query['option'] = option

    df = instance.fetch_single(
        query=query,
        method="get",
        parse=True,
        format="dataframe"
    )

    if output:
        df.to_csv(output, index=False)
    else:
        typer.echo(df.head(5))