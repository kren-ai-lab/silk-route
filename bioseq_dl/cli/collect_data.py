"""CLI commands for batch data collection."""

import typer

from .interfaces.alphafold import app as alphafold_app
from .interfaces.biodbnet import app as biodbnet_app
from .interfaces.biogrid import app as biogrid_app
from .interfaces.brenda import app as brenda_app
from .interfaces.chebi import app as chebi_app
from .interfaces.chembl import app as chembl_app
from .interfaces.chemical_search_query import app as chemical_search_query_app
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

general_section = typer.Typer(
    help="Collect data from various biological databases using general search interfaces."
)
general_section.add_typer(
    chemical_search_query_app,
    name="chemical-search",
    help="General chemical search interface to query compounds by name, CID, SMILES, InChI, or gene ID.",
)
general_section.add_typer(uniprot_app, name="uniprot")

api_section = typer.Typer(help="Collect data from various biological databases using API nomenclature.")
api_section.add_typer(alphafold_app, name="alphafold")
api_section.add_typer(biodbnet_app, name="biodbnet")
api_section.add_typer(biogrid_app, name="biogrid")
api_section.add_typer(brenda_app, name="brenda")
api_section.add_typer(chebi_app, name="chebi")
api_section.add_typer(chembl_app, name="chembl")
api_section.add_typer(geneontology_app, name="geneontology")
api_section.add_typer(interpro_app, name="interpro")
api_section.add_typer(kegg_app, name="kegg")
api_section.add_typer(pathwaycommons_app, name="pathwaycommons")
api_section.add_typer(panther_app, name="panther")
api_section.add_typer(pride_app, name="pride")
api_section.add_typer(proteindatabank_app, name="pdb")
api_section.add_typer(pubchem_app, name="pubchem")
api_section.add_typer(reactome_app, name="reactome")
api_section.add_typer(rhea_app, name="rhea")
api_section.add_typer(refseq_app, name="refseq")
api_section.add_typer(stringdb_app, name="stringdb")
