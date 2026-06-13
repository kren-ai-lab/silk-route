import typer

from bioseq_dl.cli.collect_data import api_section as api_app
from bioseq_dl.cli.collect_data import general_section as general_app
from bioseq_dl.cli.helper_commands import app as clear_cache_app
from bioseq_dl.cli.workflows import app as workflow_app

app = typer.Typer(name="bioseq-dl", help="Download sequences from multiple biological databases")
app.add_typer(api_app, name="api-collect", help="Collect data using API nomenclature.")
app.add_typer(general_app, name="general-collect", help="Collect data using general search interfaces.")
app.add_typer(workflow_app, name="workflow", help="Run predefined data collection workflows.")
app.add_typer(clear_cache_app, name="cache", help="Cache management commands.")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """BioSeqDownloader CLI entry point."""
    if ctx.invoked_subcommand is None:
        typer.echo("Welcome to BioSeqDownloader! Use --help to see available commands.")


if __name__ == "__main__":
    app()
