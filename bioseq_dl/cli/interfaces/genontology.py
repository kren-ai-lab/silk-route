"""Gene Ontology CLI commands."""

import typer

from bioseq_dl import GenOntologyInterface
from bioseq_dl.cli._shared import fetch_auto, format_option, output_option, save_or_print

app = typer.Typer(help="Fetch data from Gene Ontology database.")


@app.command("ontology-term")
def run_ontology_term(
    goid: str = typer.Argument(..., help="Gene Ontology ID (e.g., GO:0008150)."),
    output: str = output_option(help="Output file to save the fetched data."),
    output_format: str = format_option(),
) -> None:
    """Fetch data from Gene Ontology database."""
    instance = GenOntologyInterface()

    df = fetch_auto(instance, goid.split(","), method="ontology-term", parse=True, format="dataframe")

    save_or_print(df, output, output_format=output_format)


@app.command("go")
def run_go(
    goid: str = typer.Argument(..., help="Gene Ontology ID (e.g., GO:0008150)."),
    output: str = output_option(help="Output file to save the fetched data."),
    output_format: str = format_option(),
) -> None:
    """Fetch data from Gene Ontology database."""
    instance = GenOntologyInterface()

    df = fetch_auto(instance, goid.split(","), method="go", parse=True, format="dataframe")

    save_or_print(df, output, output_format=output_format)


@app.command("bioentity-function")
def run_bioentity_function(
    goid: str = typer.Argument(..., help="Gene Ontology ID (e.g., GO:0008150)."),
    output: str = output_option(help="Output file to save the fetched data."),
    output_format: str = format_option(),
) -> None:
    """Fetch data from Gene Ontology database."""
    instance = GenOntologyInterface()

    df = fetch_auto(instance, goid.split(","), method="bioentity-function", parse=True, format="dataframe")

    save_or_print(df, output, output_format=output_format)
