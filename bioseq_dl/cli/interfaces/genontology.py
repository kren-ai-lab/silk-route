import typer

from bioseq_dl import GenOntologyInterface
from bioseq_dl.cli._shared import save_or_print

app = typer.Typer(help="Fetch data from Gene Ontology database.")


@app.command("ontology-term")
def run_ontology_term(
    goid: str = typer.Argument(..., help="Gene Ontology ID (e.g., GO:0008150)."),
    output: str = typer.Option(None, "--output", "-o", help="Output file to save the fetched data."),
) -> None:
    """Fetch data from Gene Ontology database."""
    instance = GenOntologyInterface()

    if len(goid.split(",")) > 1:
        goids = goid.split(",")
        df = instance.fetch_batch(queries=goids, method="ontology-term", parse=True, format="dataframe")
    else:
        df = instance.fetch_single(query=goid, method="ontology-term", parse=True, format="dataframe")

    save_or_print(df, output)


@app.command("go")
def run_go(
    goid: str = typer.Argument(..., help="Gene Ontology ID (e.g., GO:0008150)."),
    output: str = typer.Option(None, "--output", "-o", help="Output file to save the fetched data."),
) -> None:
    """Fetch data from Gene Ontology database."""
    instance = GenOntologyInterface()

    if len(goid.split(",")) > 1:
        goids = goid.split(",")
        df = instance.fetch_batch(queries=goids, method="go", parse=True, format="dataframe")
    else:
        df = instance.fetch_single(query=goid, method="go", parse=True, format="dataframe")

    save_or_print(df, output)


@app.command("bioentity-function")
def run_bioentity_function(
    goid: str = typer.Argument(..., help="Gene Ontology ID (e.g., GO:0008150)."),
    output: str = typer.Option(None, "--output", "-o", help="Output file to save the fetched data."),
) -> None:
    """Fetch data from Gene Ontology database."""
    instance = GenOntologyInterface()

    if len(goid.split(",")) > 1:
        goids = goid.split(",")
        df = instance.fetch_batch(queries=goids, method="bioentity-function", parse=True, format="dataframe")
    else:
        df = instance.fetch_single(query=goid, method="bioentity-function", parse=True, format="dataframe")

    save_or_print(df, output)
