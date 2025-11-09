import typer

from bioseq_dl import PubChemInterface
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
    property: str = typer.Option(None, help="Specific property to fetch, e.g., molecularformula, smiles, hbonddonorcount"),
    option: str = typer.Option("default", help=f"Fetch option (e.g., {', '.join(OPTIONS['pug/compound'])})"),
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

@app.command("pug-protein")
def run_protein(
    accession: str = typer.Argument(..., help="Protein accession number"),
    option: str = typer.Option("summary", help=f"Fetch option (e.g., {', '.join(OPTIONS['pug/protein'])})"),
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

@app.command("pug-gene")
def run_gene(
    genesymbol: str = typer.Option(None, help="Gene symbol"),
    geneid: str = typer.Option(None, help="Gene ID"),
    synonym: str = typer.Option(None, help="Gene synonym"),
    taxid: str = typer.Option(None, help="Taxonomy ID"),
    option: str = typer.Option("summary", help=f"Fetch option (e.g., {', '.join(OPTIONS['pug/gene'])})"),
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

@app.command("pug_view-compound")
def run_compound_view(
    cid: str = typer.Argument(..., help="Compound ID (CID, e.g., 2244)"),
    output_file: str = typer.Option(None, help="Output file to save results")
):
    """
    Fetch detailed compound data from PubChem.
    """
    interface = PubChemInterface()

    if len(cid.split(",")) > 1:
        result = interface.fetch_batch(
            queries=[c.strip() for c in cid.split(",")],
            method="pug_view/compound",
            parse=True,
            to_dataframe=True
        )
    else:
        result = interface.fetch_single(
            cid.strip(),
            method="pug_view/compound",
            parse=True,
            to_dataframe=True
        )
    
    if output_file:
        result.to_csv(output_file, index=False)
        typer.echo(f"Results saved to {output_file}")
    else:
        typer.echo(result.head(5))

@app.command("pug_view-protein")
def run_protein_view(
    accession: str = typer.Argument(..., help="Protein accession number (e.g., P00533)"),
    output_file: str = typer.Option(None, help="Output file to save results")
):
    """
    Fetch detailed protein data from PubChem.
    """
    interface = PubChemInterface()

    if len(accession.split(",")) > 1:
        result = interface.fetch_batch(
            queries=[acc.strip() for acc in accession.split(",")],
            method="pug_view/protein",
            parse=True,
            to_dataframe=True
        )
    else:
        result = interface.fetch_single(
            accession,
            method="pug_view/protein",
            parse=True,
            to_dataframe=True
        )
    
    if output_file:
        result.to_csv(output_file, index=False)
        typer.echo(f"Results saved to {output_file}")
    else:
        typer.echo(result.head(5))
    

@app.command("pug_view-gene")
def run_gene_view(
    geneid: str = typer.Argument(..., help="Gene ID (e.g., EGFR)"),
    output_file: str = typer.Option(None, help="Output file to save results")
):
    """
    Fetch detailed gene data from PubChem.
    """
    interface = PubChemInterface()

    if len(geneid.split(",")) > 1:
        result = interface.fetch_batch(
            queries=[gid.strip() for gid in geneid.split(",")],
            method="pug_view/gene",
            parse=True,
            to_dataframe=True
        )
    else:
        result = interface.fetch_single(
            geneid.strip(),
            method="pug_view/gene",
            parse=True,
            to_dataframe=True
        )
    
    if output_file:
        result.to_csv(output_file, index=False)
        typer.echo(f"Results saved to {output_file}")
    else:
        typer.echo(result.head(5))

@app.command("pug_view-pathway")
def run_pathway_view(
    source: str = typer.Option("Reactome", help="Pathway source (e.g., Reactome)"),
    id: str = typer.Option(None, help="Pathway ID (e.g., R-HSA-5673001)"),
    output_file: str = typer.Option(None, help="Output file to save results")
):
    """
    Fetch detailed pathway data from PubChem.
    """
    interface = PubChemInterface()

    if len(id.split(",")) > 1:
        result = interface.fetch_batch(
            queries=[{"source": source, "id": pid.strip()} for pid in id.split(",")],
            method="pug_view/pathway",
            parse=True,
            to_dataframe=True
        )
    else:
        result = interface.fetch_single(
            query={"source": source, "id": id.strip()},
            method="pug_view/pathway",
            parse=True,
            to_dataframe=True
        )

    if output_file:
        result.to_csv(output_file, index=False)
        typer.echo(f"Results saved to {output_file}")
    else:
        typer.echo(result.head(5))

@app.command("pug_view-taxonomy")
def run_taxonomy_view(
    taxid: str = typer.Argument(..., help="Taxonomy ID (e.g., 9606)"),
    output_file: str = typer.Option(None, help="Output file to save results")
):
    """
    Fetch detailed taxonomy data from PubChem.
    """
    interface = PubChemInterface()

    if len(taxid.split(",")) > 1:
        result = interface.fetch_batch(
            queries=[tid.strip() for tid in taxid.split(",")],
            method="pug_view/taxonomy",
            parse=True,
            to_dataframe=True
        )
    else:
        result = interface.fetch_single(
            taxid.strip(),
            method="pug_view/taxonomy",
            parse=True,
            to_dataframe=True
        )
    
    if output_file:
        result.to_csv(output_file, index=False)
        typer.echo(f"Results saved to {output_file}")
    else:
        typer.echo(result.head(5))