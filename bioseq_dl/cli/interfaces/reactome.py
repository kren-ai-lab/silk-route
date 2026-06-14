import typer

from bioseq_dl import ReactomeInterface
from bioseq_dl.cli._shared import save_or_print

app = typer.Typer(help="Collect data from Reactome database.")


@app.command("discover")
def run_discover(
    id: str = typer.Argument(
        ..., help="Identifier to discover (comma-separated for several), e.g., R-DME-1834941"
    ),
    output_file: str = typer.Option(None, help="Output file to save results"),
) -> None:
    """Discover data in Reactome using one or more identifiers."""
    interface = ReactomeInterface()

    ids = [i.strip() for i in id.split(",") if i.strip()]
    if not ids:
        msg = "No valid identifier provided."
        raise typer.BadParameter(msg)

    # data-discover is a single-id endpoint (no group_queries), so each id is its
    # own request: fetch_batch for several, fetch_single for one.
    if len(ids) > 1:
        result = interface.fetch_batch(ids, method="data-discover", parse=True, format="dataframe")
    else:
        result = interface.fetch_single(
            {"id": ids[0]}, method="data-discover", parse=True, format="dataframe"
        )

    save_or_print(result, output_file)
