"""BioSeqDownloader main CLI app."""

import typer

from bioseq_dl import __version__
from bioseq_dl.cli.collect_data import fetch_app, search_app
from bioseq_dl.cli.helper_commands import app as cache_app
from bioseq_dl.cli.workflows import workflow_app
from bioseq_dl.logging import setup_logging

app = typer.Typer(name="bioseq-dl", help="Fetch sequences from multiple biological databases")
app.add_typer(fetch_app, name="fetch", help="Fetch data using API nomenclature.")
app.add_typer(search_app, name="search", help="Fetch data using general search interfaces.")
app.add_typer(workflow_app, name="workflow", help="Run or validate data-fetching workflows.")
app.add_typer(cache_app, name="cache", help="Cache management commands.")


def _version_callback(value: bool) -> None:
    """Print the package version and exit when ``value`` is true."""
    if value:
        typer.echo(f"bioseq-dl {__version__}")
        raise typer.Exit


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(  # noqa: ARG001  # consumed by eager callback
        False, "--version", callback=_version_callback, is_eager=True, help="Show version and exit."
    ),
    log: str = typer.Option(
        "info", "--log", "-l", help="Logging level: debug, info, warning, error, critical."
    ),
) -> None:
    """BioSeqDownloader CLI entry point."""
    setup_logging(log)
    if ctx.invoked_subcommand is None:
        typer.echo("Welcome to BioSeqDownloader! Use --help to see available commands.")


if __name__ == "__main__":
    app()
