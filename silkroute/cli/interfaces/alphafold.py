"""AlphaFold CLI commands."""

import typer

from silkroute import AlphafoldInterface
from silkroute.cli._shared import fetch_auto, format_option, output_option, save_or_print

app = typer.Typer(help="Fetch data from AlphaFold database.")


@app.command("prediction")
def run_prediction(
    identifier: str = typer.Argument(
        ..., help="UniProt ID(s) of the protein to fetch from AlphaFold (comma-separated for batch)."
    ),
    download_structures: bool = typer.Option(
        False,
        "--download-structures",
        "-ds",
        help="Whether to download the predicted structure files (PDB format).",
    ),
    output: str = output_option(
        help="Output file to save the fetched data (also the dir for downloaded structures)."
    ),
    output_format: str = format_option(),
) -> None:
    """Fetch data from AlphaFold database."""
    if download_structures:
        instance = AlphafoldInterface(structures=["pdb"], output_dir=output)
    else:
        instance = AlphafoldInterface()

    df = fetch_auto(instance, identifier.split(","), method="prediction", parse=True, format="dataframe")

    save_or_print(df, output, output_format=output_format)
