"""CLI entry points for BioSeqDownloader."""

import typer

app = typer.Typer(name="bioseq_dl", add_completion=False, help="Description")

if __name__ == "__main__":
    app()
