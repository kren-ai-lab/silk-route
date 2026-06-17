"""PubChem CLI commands."""

from typing import Any

import typer

from bioseq_dl import PubChemInterface
from bioseq_dl.cli._shared import fetch_auto, format_option, output_option, save_or_print
from bioseq_dl.constants.pubchem import OPTIONS

app = typer.Typer(
    help="""
Collect data from PubChem database.\n
Available methods are divided in 2 categories, pug and pug_view.\n
- pug methods provide basic information.\n
- pug_view methods provide detailed information.\n
""",
)


@app.command("pug-compound")
def run_compound(
    cid: str = typer.Option(None, help="Compound ID (CID)"),
    name: str = typer.Option(None, help="Compound name"),
    smiles: str = typer.Option(None, help="SMILES representation of the compound"),
    property_name: str = typer.Option(
        None, "--property", help="Specific property to fetch, e.g., molecularformula, smiles, hbonddonorcount"
    ),
    option: str = typer.Option("default", help=f"Fetch option (e.g., {', '.join(OPTIONS['pug/compound'])})"),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch compound data from PubChem."""
    interface = PubChemInterface()

    query: dict[str, Any] = {}

    if cid:
        query["cid"] = [cid.strip() for cid in cid.split(",")]
    if name:
        query["name"] = name
    if smiles:
        query["smiles"] = smiles
    if property_name:
        query["property"] = [prop.strip() for prop in property_name.split(",")]

    result = interface.fetch_single(query, method="compound", option=option, parse=True, format="dataframe")

    save_or_print(result, output, output_format=output_format)


@app.command("pug-protein")
def run_protein(
    accession: str = typer.Argument(..., help="Protein accession number"),
    option: str = typer.Option("summary", help=f"Fetch option (e.g., {', '.join(OPTIONS['pug/protein'])})"),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch protein data from PubChem."""
    interface = PubChemInterface()

    result = fetch_auto(
        interface,
        [acc.strip() for acc in accession.split(",")],
        method="protein",
        option=option,
        parse=True,
        format="dataframe",
    )

    save_or_print(result, output, output_format=output_format)


@app.command("pug-gene")
def run_gene(
    genesymbol: str = typer.Option(None, help="Gene symbol"),
    geneid: str = typer.Option(None, help="Gene ID"),
    synonym: str = typer.Option(None, help="Gene synonym"),
    taxid: str = typer.Option(None, help="Taxonomy ID"),
    option: str = typer.Option("summary", help=f"Fetch option (e.g., {', '.join(OPTIONS['pug/gene'])})"),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch gene data from PubChem."""
    interface = PubChemInterface()

    query: dict[str, Any] = {}

    if genesymbol:
        query["genesymbol"] = [gs.strip() for gs in genesymbol.split(",")]
    if geneid:
        query["geneid"] = [gid.strip() for gid in geneid.split(",")]
    if synonym:
        query["synonym"] = synonym
    if taxid:
        query["taxid"] = taxid

    result = interface.fetch_single(query, method="gene", option=option, parse=True, format="dataframe")

    save_or_print(result, output, output_format=output_format)


@app.command("pug-view-compound")
def run_compound_view(
    cid: str = typer.Argument(..., help="Compound ID (CID, e.g., 2244)"),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch detailed compound data from PubChem."""
    interface = PubChemInterface()

    result = fetch_auto(
        interface,
        [c.strip() for c in cid.split(",")],
        method="pug_view/compound",
        parse=True,
        format="dataframe",
    )

    save_or_print(result, output, output_format=output_format)


@app.command("pug-view-protein")
def run_protein_view(
    accession: str = typer.Argument(..., help="Protein accession number (e.g., P00533)"),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch detailed protein data from PubChem."""
    interface = PubChemInterface()

    result = fetch_auto(
        interface,
        [acc.strip() for acc in accession.split(",")],
        method="pug_view/protein",
        parse=True,
        format="dataframe",
    )

    save_or_print(result, output, output_format=output_format)


@app.command("pug-view-gene")
def run_gene_view(
    geneid: str = typer.Argument(..., help="Gene ID (e.g., EGFR)"),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch detailed gene data from PubChem."""
    interface = PubChemInterface()

    result = fetch_auto(
        interface,
        [gid.strip() for gid in geneid.split(",")],
        method="pug_view/gene",
        parse=True,
        format="dataframe",
    )

    save_or_print(result, output, output_format=output_format)


@app.command("pug-view-pathway")
def run_pathway_view(
    source: str = typer.Option("Reactome", help="Pathway source (e.g., Reactome)"),
    identifier: str = typer.Option(..., "--id", help="Pathway ID (e.g., R-HSA-5673001)"),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch detailed pathway data from PubChem."""
    interface = PubChemInterface()

    result = fetch_auto(
        interface,
        [{"source": source, "id": pid.strip()} for pid in identifier.split(",")],
        method="pug_view/pathway",
        parse=True,
        format="dataframe",
    )

    save_or_print(result, output, output_format=output_format)


@app.command("pug-view-taxonomy")
def run_taxonomy_view(
    taxid: str = typer.Argument(..., help="Taxonomy ID (e.g., 9606)"),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch detailed taxonomy data from PubChem."""
    interface = PubChemInterface()

    result = fetch_auto(
        interface,
        [tid.strip() for tid in taxid.split(",")],
        method="pug_view/taxonomy",
        parse=True,
        format="dataframe",
    )

    save_or_print(result, output, output_format=output_format)
