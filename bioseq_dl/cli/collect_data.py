"""CLI commands for batch data collection."""

import typer

from .interfaces.alphafold import app as alphafold_app
from .interfaces.biodbnet import app as biodbnet_app
from .interfaces.biogrid import app as biogrid_app
from .interfaces.brenda import app as brenda_app
from .interfaces.chebi import app as chebi_app
from .interfaces.chembl import app as chembl_app
from .interfaces.chemical_search_query import run_compound as chemical_search_cmd
from .interfaces.genontology import app as geneontology_app
from .interfaces.interpro import app as interpro_app
from .interfaces.kegg import app as kegg_app
from .interfaces.panther import app as panther_app
from .interfaces.pathwaycommons import app as pathwaycommons_app
from .interfaces.pride import app as pride_app
from .interfaces.proteindatabank import app as proteindatabank_app
from .interfaces.pubchem import app as pubchem_app
from .interfaces.reactome import app as reactome_app
from .interfaces.refseq import app as refseq_app
from .interfaces.rhea import app as rhea_app
from .interfaces.stringdb import app as stringdb_app
from .interfaces.uniprot import app as uniprot_app

search_app = typer.Typer(help="Fetch data from various biological databases using general search interfaces.")
search_app.command(
    "chemical",
    help="General chemical search to query compounds by name, CID, SMILES, InChI, or gene ID.",
)(chemical_search_cmd)
search_app.add_typer(uniprot_app, name="uniprot")

fetch_app = typer.Typer(help="Fetch data from various biological databases using API nomenclature.")
fetch_app.add_typer(alphafold_app, name="alphafold")
fetch_app.add_typer(biodbnet_app, name="biodbnet")
fetch_app.add_typer(biogrid_app, name="biogrid")
fetch_app.add_typer(brenda_app, name="brenda")
fetch_app.add_typer(chebi_app, name="chebi")
fetch_app.add_typer(chembl_app, name="chembl")
fetch_app.add_typer(geneontology_app, name="geneontology")
fetch_app.add_typer(interpro_app, name="interpro")
fetch_app.add_typer(kegg_app, name="kegg")
fetch_app.add_typer(pathwaycommons_app, name="pathwaycommons")
fetch_app.add_typer(panther_app, name="panther")
fetch_app.add_typer(pride_app, name="pride")
fetch_app.add_typer(proteindatabank_app, name="pdb")
fetch_app.add_typer(pubchem_app, name="pubchem")
fetch_app.add_typer(reactome_app, name="reactome")
fetch_app.add_typer(rhea_app, name="rhea")
fetch_app.add_typer(refseq_app, name="refseq")
fetch_app.add_typer(stringdb_app, name="stringdb")
