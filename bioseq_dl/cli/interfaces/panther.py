"""PANTHER CLI commands."""

import typer

from bioseq_dl import PantherInterface
from bioseq_dl.cli._shared import save_or_print

app = typer.Typer(help="Fetch data from PANTHER database.")


@app.command("geneinfo")
def run_geneinfo(
    gene_list: str = typer.Argument(..., help="Comma-separated list of gene identifiers."),
    taxon_filter: str = typer.Option(
        None,
        "--taxon-filter",
        "-tf",
        help="Taxon filter (e.g., '9606' for human).",
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file to save the data.",
    ),
) -> None:
    """Run PANTHER gene info lookup."""
    interface = PantherInterface()

    query = {"geneInputList": [gene.strip() for gene in gene_list.split(",")], "taxonFltr": taxon_filter}

    result = interface.fetch_single(query=query, method="geneinfo", parse=True, format="dataframe")

    save_or_print(result, output)


@app.command("familyortholog")
def run_familyortholog(
    panther_id: str = typer.Argument(..., help="PANTHER ID (e.g., 'PTHR10000')."),
    taxon_filter: str = typer.Option(
        None,
        "--taxon-filter",
        "-tf",
        help="Taxon filter (e.g., '9606' for human).",
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file to save the data.",
    ),
) -> None:
    """Run PANTHER family ortholog lookup."""
    interface = PantherInterface()

    query = {"family": panther_id, "taxonFltr": taxon_filter}

    result = interface.fetch_single(query=query, method="familyortholog", parse=True, format="dataframe")

    save_or_print(result, output)


@app.command("familymsa")
def run_familymsa(
    panther_id: str = typer.Argument(..., help="PANTHER ID (e.g., 'PTHR10000')."),
    taxon_filter: str = typer.Option(
        ...,
        "--taxon-filter",
        "-tf",
        help="Taxon filter (e.g., '9606' for human).",
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file to save the data.",
    ),
) -> None:
    """Run PANTHER family MSA lookup."""
    interface = PantherInterface()

    query = {"family": panther_id, "taxonFltr": taxon_filter}

    result = interface.fetch_single(query=query, method="familymsa", parse=True, format="dataframe")

    save_or_print(result, output)
