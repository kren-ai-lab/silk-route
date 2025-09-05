import typer
from typing import Optional

from bioseq_dl import PDBInterface

app = typer.Typer(help="Collect data from Protein Data Bank (PDB).")
@app.command("entry")
def run_fetch_entry(
    pdb_id: str = typer.Argument(
        ..., 
        help="PDB ID of the entry to fetch."
    ),
    download_structures: bool = typer.Option(
        False, "--download-structures",
        help="Whether to download the structure files."
    ),
    output_file: Optional[str] = typer.Option(
        None, "--output-file",
        help="File to save the results."
    )
):
    """
    Fetch a PDB entry by its ID.
    """
    interface = PDBInterface(
        download_structures=download_structures,
        return_data_list=["rcsb_entry_info", "struct_ref", "pdbx_audit_revision_history"],
        output_dir="/".join(output_file.split("/")[:-1]) if output_file else None
    )

    if len(pdb_id.split(",")) > 1:
        results = interface.fetch_batch(
            queries=pdb_id.split(","),
            method="entry",
            parse=True,
            to_dataframe=True
        )
    else:
        results = interface.fetch_single(
            query=pdb_id,
            method="entry",
            parse=True,
            to_dataframe=True
        )

    if output_file:
        results.to_csv(output_file, index=False)
        typer.echo(f"Results saved to {output_file}")
    else:
        typer.echo(results.head(5))