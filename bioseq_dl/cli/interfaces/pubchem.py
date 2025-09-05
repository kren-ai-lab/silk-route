import typer

from bioseq_dl import PubChemInterface
from bioseq_dl.constants.pubchem import OPTIONS

app = typer.Typer(help="Collect data from PubChem database.")

@app.command("compound")
def run_compound(
    cid: str = typer.Option(None, help="Compound ID (CID)"),
    name: str = typer.Option(None, help="Compound name"),
    smiles: str = typer.Option(None, help="SMILES representation of the compound"),
    property: str = typer.Option(None, help="Specific property to fetch, e.g., molecularformula, smiles, hbonddonorcount"),
    option: str = typer.Option("default", help=f"Fetch option (e.g., {', '.join(OPTIONS['compound'])})"),
    output_file: str = typer.Option(None, help="Output file to save results")
):
    """
    Fetch compound data from PubChem.
    """
    interface = PubChemInterface()

    query = {}

    if cid:
        query["cid"] = [cid.strip() for cid in cid.split(",")]
    if name:
        query["name"] = name
    if smiles:
        query["smiles"] = smiles
    if property:
        query["property"] = [prop.strip() for prop in property.split(",")]

    result = interface.fetch_single(
        query, 
        method="compound", 
        option=option,
        parse=True,
        to_dataframe=True
    )

    if output_file:
        result.to_csv(output_file, index=False)
        typer.echo(f"Results saved to {output_file}")
    else:
        typer.echo(result.head(5))

@app.command("protein")
def run_protein(
    accession: str = typer.Argument(..., help="Protein accession number"),
    option: str = typer.Option("summary", help=f"Fetch option (e.g., {', '.join(OPTIONS['protein'])})"),
    output_file: str = typer.Option(None, help="Output file to save results")
):
    """
    Fetch protein data from PubChem.
    """
    interface = PubChemInterface()

    if len(accession.split(",")) > 1:
        result = interface.fetch_batch(
            queries=[acc.strip() for acc in accession.split(",")],
            method="protein",
            option=option,
            parse=True,
            to_dataframe=True
        )
    else:
        result = interface.fetch_single(
            accession,
            method="protein",
            option=option,
            parse=True,
            to_dataframe=True
        )
    
    if output_file:
        result.to_csv(output_file, index=False)
        typer.echo(f"Results saved to {output_file}")
    else:
        typer.echo(result.head(5))

@app.command("gene")
def run_gene(
    genesymbol: str = typer.Option(None, help="Gene symbol"),
    geneid: str = typer.Option(None, help="Gene ID"),
    synonym: str = typer.Option(None, help="Gene synonym"),
    taxid: str = typer.Option(None, help="Taxonomy ID"),
    option: str = typer.Option("summary", help=f"Fetch option (e.g., {', '.join(OPTIONS['gene'])})"),
    output_file: str = typer.Option(None, help="Output file to save results")
):
    """
    Fetch gene data from PubChem.
    """
    interface = PubChemInterface()

    query = {}

    if genesymbol:
        query["genesymbol"] = [gs.strip() for gs in genesymbol.split(",")]
    if geneid:
        query["geneid"] = [gid.strip() for gid in geneid.split(",")]
    if synonym:
        query["synonym"] = synonym
    if taxid:
        query["taxid"] = taxid

    result = interface.fetch_single(
        query,
        method="gene",
        option=option,
        parse=True,
        to_dataframe=True
    )

    if output_file:
        result.to_csv(output_file, index=False)
        typer.echo(f"Results saved to {output_file}")
    else:
        typer.echo(result.head(5))