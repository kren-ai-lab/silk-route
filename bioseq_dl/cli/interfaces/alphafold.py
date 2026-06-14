"""AlphaFold CLI commands."""

import typer

from bioseq_dl import AlphafoldInterface
from bioseq_dl.cli._shared import save_or_print

app = typer.Typer(help="Fetch data from AlphaFold database.")


@app.command("prediction")
def run_prediction(
    identifier: str = typer.Option(
        ..., "--id", "-id", help="UniProt ID of the protein to fetch from AlphaFold."
    ),
    download_structures: bool = typer.Option(
        False,
        "--download-structures",
        "-ds",
        help="Whether to download the predicted structure files (PDB format).",
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file to save the fetched data.",
    ),
) -> None:
    """Fetch data from AlphaFold database."""
    if download_structures:
        instance = AlphafoldInterface(structures=["pdb"], output_dir=output)
    else:
        instance = AlphafoldInterface()

    if len(identifier.split(",")) > 1:
        ids: list[str] = identifier.split(",")
        df = instance.fetch_batch(queries=ids, method="prediction", parse=True, format="dataframe")
    else:
        df = instance.fetch_single(query=identifier, method="prediction", parse=True, format="dataframe")

    save_or_print(df, output)
