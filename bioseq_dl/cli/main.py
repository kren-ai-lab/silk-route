import typer
from bioseq_dl.cli.gui import app as launch_gradio_app
from bioseq_dl.cli.collect_data import app as collect_data_app
from bioseq_dl.cli.blast_alignment import app as blast_alignment_app
from bioseq_dl.init_config import main_init

app = typer.Typer(name="bioseq-dl", help="Download sequences from multiple biological databases")
app.add_typer(launch_gradio_app, name="gui", help="Launch the Gradio GUI for BioSeqDownloader.")
app.add_typer(collect_data_app, name="collect-data", help="Collect data from various biological databases.")
app.add_typer(blast_alignment_app, name="blast-alignment", help="Perform BLAST alignment to retrieve UniProt IDs")

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