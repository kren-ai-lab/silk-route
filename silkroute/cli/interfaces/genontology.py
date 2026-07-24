"""Gene Ontology CLI commands."""

import typer

from silkroute import GenOntologyInterface
from silkroute.cli._shared import fetch_auto, format_option, output_option, save_or_print

app = typer.Typer(help="Fetch data from Gene Ontology database.")


def _register(command: str, method: str) -> None:
    """Register a GO fetch command dispatching to ``method`` under ``command``."""

    @app.command(command)
    def _command(
        goid: str = typer.Argument(..., help="Gene Ontology ID (e.g., GO:0008150)."),
        output: str = output_option(help="Output file to save the fetched data."),
        output_format: str = format_option(),
    ) -> None:
        """Fetch data from Gene Ontology database."""
        instance = GenOntologyInterface()
        df = fetch_auto(instance, goid.split(","), method=method, parse=True, format="dataframe")
        save_or_print(df, output, output_format=output_format)


for _name in ("ontology-term", "go", "bioentity-function"):
    _register(_name, _name)
