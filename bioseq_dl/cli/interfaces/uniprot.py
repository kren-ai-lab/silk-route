import typer

from .uniprot_crossref import app as uniprot_crossref_app
from .uniprot_search_ids import app as uniprot_search_ids_app
from .uniprot_search_query import app as uniprot_search_query_app
from .uniprot_search_alignment import app as uniprot_search_alignment_app

app = typer.Typer(help="Collect data from UniProt database.")

app.add_typer(uniprot_crossref_app, name="search-crossreferences")
app.add_typer(uniprot_search_ids_app, name="search-by-ids")
app.add_typer(uniprot_search_query_app, name="search-by-query")
app.add_typer(uniprot_search_alignment_app, name="search-by-alignment")