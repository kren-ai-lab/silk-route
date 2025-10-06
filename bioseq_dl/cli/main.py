import typer
from bioseq_dl.cli.uniprot_crossref import app as uniprot_crossref_app
from bioseq_dl.cli.uniprot_search_ids import app as uniprot_search_ids_app
from bioseq_dl.cli.uniprot_search_query import app as uniprot_search_query_app
from bioseq_dl.cli.uniprot_search_alignment import app as run_blast
from bioseq_dl.cli.gui import app as launch_gradio_app
from bioseq_dl.cli.collect_data import app as collect_data_app
from bioseq_dl.init_config import main_init

app = typer.Typer(name="bioseq-dl", help="Download sequences from multiple biological databases")

app.add_typer(uniprot_crossref_app, name="uniprot-crossref", help="Search and download cross-references from UniProt.")
app.add_typer(uniprot_search_ids_app, name="uniprot-search-ids", help="Search and download sequences from UniProt using IDs.")
app.add_typer(uniprot_search_query_app, name="uniprot-search-query", help="Search and download sequences from UniProt using queries.")
app.add_typer(run_blast, name="uniprot-search-alignment", help="Run BLAST alignment on sequences and [optionaly] download matching sequences from UniProt.")
app.add_typer(launch_gradio_app, name="gui", help="Launch the Gradio GUI for BioSeqDownloader.")
app.add_typer(collect_data_app, name="collect-data", help="Collect data from various biological databases.")

@app.callback(invoke_without_command=True)
def check_config(ctx: typer.Context) -> None:
    """
    Check and initialize configuration on first run.
    """
    if ctx.invoked_subcommand is None:
        typer.echo("Welcome to BioSeqDownloader!")
        typer.echo("Checking configuration availability...")
        main_init()
        typer.echo("Configuration initialized. Use --help to see available commands.")

if __name__ == "__main__":
    app()