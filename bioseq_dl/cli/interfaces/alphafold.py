import os
import typer
import pandas as pd
from typing import List

from bioseq_dl import AlphafoldInterface


app = typer.Typer(help="Fetch data from AlphaFold database.")

@app.command("prediction")
def run_prediction(
    id: str = typer.Option(
        ..., "--id", "-id",
        help="UniProt ID of the protein to fetch from AlphaFold."
    ),
    download_structures: bool = typer.Option(
        False,
        "--download-structures", "-ds",
        help="Whether to download the predicted structure files (PDB format)."
    ),
    output: str = typer.Option(
        None, "--output", "-o",
        help="Output file to save the fetched data.",
    )
):
    """Fetch data from AlphaFold database."""
    if download_structures:
        instance = AlphafoldInterface(
            structures=['pdb'],
            output_dir=output
        )
    else:
        instance = AlphafoldInterface()

    if len(id.split(",")) > 1:
        ids: List[str] = id.split(",")
        df = pd.DataFrame(instance.fetch_batch(
            queries=ids,
            method="prediction",
            parse=True,
            format="dataframe"
        ))
    else:
        df = pd.DataFrame(instance.fetch_single(
            query=id,
            method="prediction",
            parse=True, 
            format="dataframe"
        ))

    if output:
        df.to_csv(output, index=False)
    else:
        print(df.head(5))