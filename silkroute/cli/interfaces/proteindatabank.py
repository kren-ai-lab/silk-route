"""Protein Data Bank CLI commands."""

from pathlib import Path

import typer

from silkroute import PDBInterface
from silkroute.cli._shared import fetch_auto, format_option, output_option, save_or_print

app = typer.Typer(help="Collect data from Protein Data Bank (PDB).")


@app.command("entry")
def run_fetch_entry(
    pdb_id: str = typer.Argument(..., help="PDB ID of the entry to fetch."),
    download_structures: bool = typer.Option(
        False, "--download-structures", help="Whether to download the structure files."
    ),
    output: str | None = output_option(help="Output file to save the results."),
    output_format: str = format_option(),
) -> None:
    """Fetch a PDB entry by its ID."""
    interface = PDBInterface(
        download_structures=download_structures,
        output_dir=str(Path(output).parent) if output else None,
    )

    results = fetch_auto(interface, pdb_id.split(","), method="entry", parse=True, format="dataframe")

    save_or_print(results, output, output_format=output_format)
