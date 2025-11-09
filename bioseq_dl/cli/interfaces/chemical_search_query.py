import typer, logging

from bioseq_dl import PubChemInterface, ChEMBLInterface, ChEBIInterface
from bioseq_dl.constants.pubchem import OPTIONS

# Pending: Uniprot ID

# ----- Optional logging (fallback to stdlib) -----
try:
    from bioseq_dl.logging import get_logger
except Exception:
    def get_logger(name: str) -> logging.Logger:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        return logging.getLogger(name)

log = get_logger("bioseq_dl.cli.chemical_search_query")
# -------------------------------------------------

app = typer.Typer(help="Collect data from chemical databases. A general search interface is provided to query compounds by name, CID, SMILES, InChI, or gene ID.")

AVAILABLE_DATABASES = ["pubchem", "chembl", "chebi"]

def detect_query_type(query: str) -> str:
    """
    Detect the type of the query string.
    """
    query = query.strip()

    if query.startswith("InChI="):
        return "inchi"
    elif any(c in query for c in "=#[]" ) and query.count("C") >= 1 and len(query) > 6:
        return "smiles"
    elif query.isupper() and len(query) <= 6:
        return "gene"
    else:
        return "name"
    
def pubchem_search_query(query: str):
    """
    Fetch compound data from PubChem.
    """
    
    instance = PubChemInterface()

    query_type = detect_query_type(query)

    if query_type == "name" or query_type == "inchi" or query_type == "smiles":
        query_dict = [{query_type: query.strip()} for query in query.split(",")]
        log.info(f"Getting CIDs for {query_type.upper()}s: {query_dict}")
        cids_df = instance.fetch_batch(
            queries=query_dict,
            method="pug/compound",
            parse=True,
            to_dataframe=True
        )
        cids = cids_df["cid"].astype(str).tolist()
        log.info(f"Found CIDs: {cids}")
        query_dict = [{"cid": cid} for cid in cids]
        df = instance.fetch_batch(
            queries=query_dict,
            method="pug_view/compound",
            parse=True,
            to_dataframe=True
        )
    elif query_type == "gene":
        query_dict = [{"geneid": query.strip()} for query in query.split(",")]
        log.info(f"Fetching data for Gene IDs: {query_dict}")
        df = instance.fetch_batch(
            queries=query_dict,
            method="pug_view/gene",
            parse=True,
            to_dataframe=True
        )
    else:
        log.error(f"Unsupported query type: {query_type}")
        return

    return df

def chembl_search_query(query: str):
    """
    Fetch compound data from ChEMBL.
    """
    instance = ChEMBLInterface()
    
    query_type = detect_query_type(query)

    if query_type == "name":
        query_dict = {
            "filters": [
                {
                    "field": "molecule_name",
                    "filter_type": "icontains",
                    "value": query.strip()
                }
            ]
        }
        log.info(f"Fetching data for molecule names: {query_dict}")
        df = instance.fetch_single(
            query=query_dict,
            method="molecule",
            parse=True,
            to_dataframe=True
        )
    elif query_type == "smiles":
        query_dict = {
            "filters": [
                {
                    "field": "molecule_structures__canonical_smiles",
                    "filter_type": "icontains",
                    "value": query.strip()
                }
            ]
        }
        log.info(f"Fetching data for SMILES: {query_dict}")
        df = instance.fetch_single(
            query=query_dict,
            method="molecule",
            parse=True,
            to_dataframe=True
        )
    elif query_type == "gene":
        query_dict = {
            "filters": [
                {
                    "field": "gene_symbol",
                    "filter_type": "icontains",
                    "value": query.strip()
                }
            ]
        }
        log.info(f"Fetching data for Gene IDs: {query_dict}")
        df = instance.fetch_single(
            query=query_dict,
            method="target",
            parse=True,
            to_dataframe=True
        )
    elif query_type == "inchi":
        log.error("ChEMBL does not support InChI-based searches yet.")
        return
    else:
        log.error(f"Unsupported query type for ChEMBL: {query_type}")
        return
    
    return df


def chebi_search_query(query: str):
    """
    Fetch compound data from ChEBI.
    """
    instance = ChEBIInterface()
    
    query_type = detect_query_type(query)

    log.info(f"Fetching data for query: {query.strip()}")
    query = {"term": query.strip()}
    df = instance.fetch_single(
        query=query,
        method="es_search",
        parse=True,
        to_dataframe=True
    )
    # Make query for every found chebi_id
    chebi_ids = df["chebi_accession"].tolist()
    query = {"chebi_ids": chebi_ids}
    df = instance.fetch_single(
        query=query,
        method="compounds",
        parse=True,
        to_dataframe=True
    )

    return df


@app.command("run")
def run_compound(
    query: str = typer.Argument(..., help="Search query string (e.g., aspirin, InChI=1S/C3H6O/c1-3(2)4/h1-2H3, C1=CC=C(C=C1)C=O, EGFR)"),
    databases: str = typer.Option("all", help="Databases to search separated by commas (e.g., pubchem, chembl). Use 'all' to search all available databases."),
    output_file: str = typer.Option(None, help="Output file to save results")
):
    """
    Fetch compound data from chemical databases.
    """

    if databases.lower() != "all":
        db_list = [db.strip().lower() for db in databases.split(",")]
    else:
        db_list = AVAILABLE_DATABASES
    

    for db in db_list:
        if db == "pubchem":
            log.info(f"Searching PubChem for query: {query}")
            result = pubchem_search_query(query)
            if result is not None:
                if output_file:
                    result.to_csv(f"pubchem_{output_file}", index=False)
                    log.info(f"Results saved to pubchem_{output_file}")
                else:
                    typer.echo(result.head(5))
        elif db == "chembl":
            log.info(f"Searching ChEMBL for query: {query}")
            result = chembl_search_query(query)
            if result is not None:
                if output_file:
                    result.to_csv(f"chembl_{output_file}", index=False)
                    log.info(f"Results saved to chembl_{output_file}")
                else:
                    typer.echo(result.head(5))
        elif db == "chebi":
            log.info(f"Searching ChEBI for query: {query}")
            result = chebi_search_query(query)
            if result is not None:
                if output_file:
                    result.to_csv(f"chebi_{output_file}", index=False)
                    log.info(f"Results saved to chebi_{output_file}")
                else:
                    typer.echo(result.head(5))
        else:
            log.warning(f"Database '{db}' is not supported.")