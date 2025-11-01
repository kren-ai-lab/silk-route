import typer, logging

from bioseq_dl import PubChemInterface
from bioseq_dl.constants.pubchem import OPTIONS

# ----- Optional logging (fallback to stdlib) -----
try:
    from bioseq_dl.logging import get_logger
except Exception:
    def get_logger(name: str) -> logging.Logger:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        return logging.getLogger(name)

log = get_logger("bioseq_dl.cli.pubchem_search_query")
# -------------------------------------------------

app = typer.Typer(help="Collect data from PubChem database.")

def detect_query_type(query: str) -> str:
    """
    Detect the type of the query string.
    """
    query = query.strip()
    if query.isdigit():
        return "cid"
    elif query.startswith("InChI="):
        return "inchi"
    elif any(c in query for c in "=#[]" ) and query.count("C") >= 1 and len(query) > 6:
        return "smiles"
    elif query.isupper() and len(query) <= 6:
        return "gene"
    else:
        return "name"

@app.command()
def run_compound(
    query: str = typer.Argument(..., help="Search query string (e.g., aspirin, 2244, C1=CC=C(C=C1)C=O, InChI=1S/C3H6O/c1-3(2)4/h1-2H3, C1=CC=C(C=C1)C=O, EGFR)"),
    output_file: str = typer.Option(None, help="Output file to save results")
):
    """
    Fetch compound data from PubChem.
    """
    instance = PubChemInterface()

    query_type = detect_query_type(query)

    if query_type == "cid":
        query_dict = {"cid": [query.strip() for query in query.split(",")]}
        df = instance.fetch_single(
            query=query_dict,
            method="pug_view/compound",
            parse=True,
            to_dataframe=True
        )
    elif query_type == "name":
        query_dict = {"name": [query.strip() for query in query.split(",")]}
    elif query_type == "smiles":
        query_dict = {"smiles": [query.strip() for query in query.split(",")]}
    else:
        log.error(f"Unsupported query type: {query_type}")
        return

    if output_file:
        df.to_csv(output_file, index=False)
        typer.echo(f"Results saved to {output_file}")
    else:
        typer.echo(df.head(5))
