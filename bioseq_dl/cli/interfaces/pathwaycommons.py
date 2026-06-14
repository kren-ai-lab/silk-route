import typer

from bioseq_dl import PathwayCommonsInterface
from bioseq_dl.cli._shared import save_or_print

app = typer.Typer(help="Fetch data from Pathway Commons.")


@app.command("top_pathways")
def run_top_pathways(
    query: str = typer.Argument(..., help="Gene or protein identifier to query."),
    organism: str = typer.Option(
        None,
        "--organism",
        "-org",
        help="Organism name to filter results",
    ),
    databases: str = typer.Option(
        None,
        "--databases",
        "-dbs",
        help="Comma-separated list of databases to filter results (e.g., reactome, uniprot).",
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file to save the top pathways.",
    ),
) -> None:
    """Fetch data from Pathway Commons."""
    instance = PathwayCommonsInterface()

    query_params = {"q": query}
    if organism:
        query_params["organism"] = [organism]
    if databases:
        query_params["datasource"] = [db.strip() for db in databases.split(",")]

    df = instance.fetch_single(query=query_params, method="top_pathways", parse=True, format="dataframe")

    save_or_print(df, output)


@app.command("fetch")
def run_fetch(
    uri: str = typer.Argument(..., help="BioPAX URI to fetch data for."),
    pattern: str = typer.Option(
        None,
        "--pattern",
        "-p",
        help="Pattern to filter the fetched data.",
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file to save the fetched data.",
    ),
) -> None:
    """Fetch data from Pathway Commons using a BioPAX URI."""
    instance = PathwayCommonsInterface()

    data = instance.fetch_single(
        query={
            "uri": [u.strip() for u in uri.split(",")],
            "pattern": [p.strip() for p in pattern.split(",")] if pattern else None,
        },
        method="fetch",
        parse=True,
        format="dataframe",
    )

    save_or_print(data, output)


@app.command("neighborhood")
def run_neighborhood(
    source: str = typer.Argument(..., help="Source gene or protein identifier."),
    limit: int = typer.Option(
        1,
        "--limit",
        "-l",
        help="Limit the number of neighbors to fetch.",
    ),
    organism: str = typer.Option(
        None,
        "--organism",
        "-org",
        help="Organism name to filter results",
    ),
    databases: str = typer.Option(
        None,
        "--databases",
        "-dbs",
        help="Comma-separated list of databases to filter results (e.g., reactome, uniprot).",
    ),
    pattern: str = typer.Option(
        None,
        "--pattern",
        "-p",
        help="Pattern to filter the fetched data.",
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file to save the neighborhood data.",
    ),
) -> None:
    """Fetch neighborhood data from Pathway Commons."""
    instance = PathwayCommonsInterface()

    query_params = {"source": [s.strip() for s in source.split(",")], "limit": limit}
    if organism:
        query_params["organism"] = [organism]
    if databases:
        query_params["datasource"] = [db.strip() for db in databases.split(",")]
    if pattern:
        query_params["pattern"] = [p.strip() for p in pattern.split(",")]

    df = instance.fetch_single(query=query_params, method="neighborhood", parse=True, format="dataframe")

    save_or_print(df, output)
