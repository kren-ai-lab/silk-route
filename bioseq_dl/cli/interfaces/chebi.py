import typer

from bioseq_dl import ChEBIInterface

app = typer.Typer(help="Collect data from the ChEBI database.")


@app.command("compound")
def run_compound(
    chebi_id: str = typer.Argument(..., help="ChEBI ID of the compound (e.g., CHEBI:15377)"),
    only_ontology_parents: bool = typer.Option(
        False, "--only-parents", help="If true, only fetch ontology parents"
    ),
    only_ontology_children: bool = typer.Option(
        False, "--only-children", help="If true, only fetch ontology children"
    ),
    output: str = typer.Option(None, help="Output file to save the results (optional)"),
):
    """Fetch compound information by ChEBI ID."""
    interface = ChEBIInterface()

    query = {}

    query["chebi_id"] = chebi_id
    query["only_ontology_parents"] = only_ontology_parents
    query["only_ontology_children"] = only_ontology_children
    result = interface.fetch_single(method="compound", query=query, parse=True, format="dataframe")

    if output:
        result.to_csv(output, index=False)
    else:
        typer.echo(result)


@app.command("compounds")
def run_compounds(
    chebi_ids: str = typer.Argument(
        ..., help="Comma-separated list of ChEBI IDs (e.g., CHEBI:15377,CHEBI:15378)"
    ),
    output: str = typer.Option(None, help="Output file to save the results (optional)"),
):
    """Fetch multiple compounds by ChEBI IDs."""
    interface = ChEBIInterface()

    ids_list = chebi_ids.split(",")

    query = {}
    query["chebi_ids"] = ids_list

    result = interface.fetch_batch(
        method="compounds", queries=ids_list, query=query, parse=True, format="dataframe"
    )

    if output:
        result.to_csv(output, index=False)
    else:
        typer.echo(result)


@app.command("es_search")
def run_es_search(
    term: str = typer.Argument(..., help="Search term for the ChEBI database"),
    page: int = typer.Option(1, "--page", help="Page number for pagination (default: 1)"),
    size: int = typer.Option(15, "--size", help="Number of results per page (default: 15)"),
    output: str = typer.Option(None, help="Output file to save the results (optional)"),
):
    """Perform an Elasticsearch search in the ChEBI database."""
    interface = ChEBIInterface()

    query = {}
    query["term"] = term
    query["page"] = page
    query["size"] = size

    result = interface.fetch_single(method="es_search", query=query, parse=True, format="dataframe")

    if output:
        result.to_csv(output, index=False)
    else:
        typer.echo(result)


@app.command("ontology-children")
def run_ontology_children(
    chebi_id: str = typer.Argument(..., help="ChEBI ID to fetch ontology children for (e.g., CHEBI:15377)"),
    output: str = typer.Option(None, help="Output file to save the results (optional)"),
):
    """Fetch ontology children of a given ChEBI ID."""
    interface = ChEBIInterface()

    query = {}
    query["chebi_id"] = chebi_id

    result = interface.fetch_single(method="ontology-children", query=query, parse=True, format="dataframe")

    if output:
        result.to_csv(output, index=False)
    else:
        typer.echo(result)


@app.command("ontology-parents")
def run_ontology_parents(
    chebi_id: str = typer.Argument(..., help="ChEBI ID to fetch ontology parents for (e.g., CHEBI:15377)"),
    output: str = typer.Option(None, help="Output file to save the results (optional)"),
):
    """Fetch ontology parents of a given ChEBI ID."""
    interface = ChEBIInterface()

    query = {}
    query["chebi_id"] = chebi_id

    result = interface.fetch_single(method="ontology-parents", query=query, parse=True, format="dataframe")

    if output:
        result.to_csv(output, index=False)
    else:
        typer.echo(result)
