"""UniProt CLI commands."""

import typer

from .uniprot_crossref import run as run_crossrefs
from .uniprot_search_ids import run as run_by_ids
from .uniprot_search_query import run as run_by_query
from .uniprot_search_sequences import run as run_by_sequences

app = typer.Typer(help="Search and download data from UniProt.")

app.command("by-ids", help="Search and download sequences from UniProt using IDs.")(run_by_ids)
app.command("by-query", help="Search and download sequences from UniProt using queries.")(run_by_query)
app.command(
    "by-sequences",
    help="Run BLAST alignment on sequences and download matching sequences from UniProt.",
)(run_by_sequences)
app.command("crossrefs", help="Search and download cross-references from UniProt.")(run_crossrefs)
