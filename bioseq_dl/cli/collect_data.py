import typer

from .interfaces.alphafold import app as alphafold_app
from .interfaces.biodbnet import app as biodbnet_app
from .interfaces.biogrid import app as biogrid_app
from .interfaces.brenda import app as brenda_app
from .interfaces.chebi import app as chebi_app
from .interfaces.chembl import app as chembl_app
from .interfaces.genontology import app as geneontology_app
from .interfaces.interpro import app as interpro_app
from .interfaces.kegg import app as kegg_app
from .interfaces.pathwaycommons import app as pathwaycommons_app
from .interfaces.panther import app as panther_app
from .interfaces.pride import app as pride_app
from .interfaces.proteindatabank import app as proteindatabank_app
from .interfaces.pubchem import app as pubchem_app
from .interfaces.reactome import app as reactome_app
from .interfaces.rhea import app as rhea_app
from .interfaces.refseq import app as refseq_app
from .interfaces.stringdb import app as stringdb_app



app = typer.Typer(help="Collect data from various biological databases.")
app.add_typer(alphafold_app, name="alphafold")
app.add_typer(biodbnet_app, name="biodbnet")
app.add_typer(biogrid_app, name="biogrid")
app.add_typer(brenda_app, name="brenda")
app.add_typer(chebi_app, name="chebi")
app.add_typer(chembl_app, name="chembl")
app.add_typer(geneontology_app, name="geneontology")
app.add_typer(interpro_app, name="interpro")
app.add_typer(kegg_app, name="kegg")
app.add_typer(pathwaycommons_app, name="pathwaycommons")
app.add_typer(panther_app, name="panther")
app.add_typer(pride_app, name="pride")
app.add_typer(proteindatabank_app, name="pdb")
app.add_typer(pubchem_app, name="pubchem")
app.add_typer(reactome_app, name="reactome")
app.add_typer(rhea_app, name="rhea")
app.add_typer(refseq_app, name="refseq")
app.add_typer(stringdb_app, name="stringdb")