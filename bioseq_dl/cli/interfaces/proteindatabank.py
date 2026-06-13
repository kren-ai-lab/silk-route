import typer

from bioseq_dl import PDBInterface
from bioseq_dl.cli._shared import save_or_print

app = typer.Typer(help="Collect data from Protein Data Bank (PDB).")


@app.command("entry")
def run_fetch_entry(
    pdb_id: str = typer.Argument(..., help="PDB ID of the entry to fetch."),
    download_structures: bool = typer.Option(
        False, "--download-structures", help="Whether to download the structure files."
    ),
    output_file: str | None = typer.Option(None, "--output-file", help="File to save the results."),
):
    """Fetch a PDB entry by its ID."""
    interface = PDBInterface(
        download_structures=download_structures,
        output_dir="/".join(output_file.split("/")[:-1]) if output_file else None,
    )

    if len(pdb_id.split(",")) > 1:
        results = interface.fetch_batch(
            queries=pdb_id.split(","), method="entry", parse=True, format="dataframe"
        )
    else:
        results = interface.fetch_single(query=pdb_id, method="entry", parse=True, format="dataframe")

    save_or_print(results, output_file)
