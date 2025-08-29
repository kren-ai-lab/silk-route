import typer
from bioseq_dl.cli.uniprot_crossref import app as uniprot_crossref_app
from bioseq_dl.cli.set_biogrid_key import app as set_biogrid_key_app
from bioseq_dl.cli.uniprot_search_ids import app as uniprot_search_ids_app
from bioseq_dl.cli.uniprot_search_query import app as uniprot_search_query_app
from bioseq_dl.cli.download_variants import app as uniprot_search_variants_app
from bioseq_dl.cli.blast_alignment import app as run_blast
from bioseq_dl.cli.gui import app as launch_gradio_app

app = typer.Typer(name="bioseq-dl", help="Download sequences from multiple biological databases")

app.add_typer(uniprot_crossref_app, name="uniprot-crossref", help="Search and download cross-references from UniProt.")
app.add_typer(set_biogrid_key_app, name="set-biogrid-key", help="Set BioGRID API key.")
app.add_typer(uniprot_search_ids_app, name="uniprot-search-ids", help="Search and download sequences from UniProt using IDs.")
app.add_typer(uniprot_search_query_app, name="uniprot-search-query", help="Search and download sequences from UniProt using queries.")
app.add_typer(uniprot_search_variants_app, name="uniprot-search-variants", help="Search and download variants from UniProt using IDs.")
app.add_typer(launch_gradio_app, name="gui", help="Launch the Gradio GUI for BioSeqDownloader.")
app.add_typer(run_blast, name="blast-alignment", help="Run BLAST alignment on sequences.")

if __name__ == "__main__":
    app()