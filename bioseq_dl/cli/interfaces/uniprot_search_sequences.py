import os
import typer
import shutil
import logging
import json

import pandas as pd

from bioseq_dl.constants.databases import BASE_BLAST_DB_DIR as DB_DIR
from bioseq_dl.constants.uniprot import DATABASES, VALID_FIELDS, VALID_CROSS_REF_FIELDS, XREF_MAPPING
from bioseq_dl import UniprotInterface

from bioseq_dl.core.utils.blast_search import (
    download_uniprot_database,
    check_blast,
    make_blast_database,
    run_blast,
    parse_blast_results
)
from bioseq_dl.logging import configure_logging
from bioseq_dl.core.utils.crossref_enrichment import run_crossref_enrichment

# ----- Optional logging (fallback to stdlib) -----
try:
    from bioseq_dl.logging import get_logger
except Exception:
    def get_logger(name: str) -> logging.Logger:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        return logging.getLogger(name)

log = get_logger("bioseq_dl.cli.uniprot_search_sequences")
# -------------------------------------------------

app = typer.Typer(help="Run BLAST alignment on sequences and [optionaly] download matching sequences from UniProt.")

@app.command()
def run(
    database: str = typer.Option(
        ..., "--database", "-d",
        help="Database to download. Supported databases: " + ", ".join(DATABASES.keys())
    ),
    extension: str = typer.Option(
        "fasta", "--extension", "-e",
        help="File extension of the database. Default is 'fasta'."
    ),
    input: str = typer.Option(
        ..., "--input", "-i",
        help="File with sequences to run BLAST on."
    ),
    seq_column: str = typer.Option(
        "sequences", "--seq-column", "-c",
        help="Column name with sequences."
    ),
    output: str = typer.Option(
        ..., "-o", "--output", 
        help="Output directory for results"
    ),
    evalue: float = typer.Option(
        0.001, "--evalue", "-v",
        help="E-value threshold for BLAST search."
    ),
    blast_type: str = typer.Option(
        "blastp", "--blast-type", "-b",
        help="Type of BLAST to run. Default is 'blastp'."
    ),
    no_download: bool = typer.Option(
        False, "--no-download", "-u",
        help="If set, will not download information from UniProt after BLAST."
    ),  
    fields: str = typer.Option(
        ",".join(VALID_FIELDS), "-f", "--fields", 
        help="Fields to include in the output"
    ),
    crossref_fields: str = typer.Option(
        "", "-xr", "--crossref_fields", 
        help="Cross reference fields to include in the output, options: " + ", ".join([xref[1] for xref in XREF_MAPPING.values()])
    ),
    min_identity: float = typer.Option(
        90.0, "--min_identity", 
        help="Minimum identity threshold for BLAST search."
    ),
    debug: bool = typer.Option(
        False, "--debug",
        help="Enable debug logging"
    )
):
    logger = log
    try:
        if debug:
            configure_logging(level=logging.DEBUG)
            logger = get_logger("bioseq_dl.cli.uniprot_search_query")  # re-fetch so root handlers pick new level
            logger.debug("Debug logging enabled")
    except Exception as e:
        logger.warning(f"Could not configure logging: {e}")

    df = pd.read_csv(input)

    if seq_column not in df.columns:
        raise ValueError(f"Column '{seq_column}' not found in input file.")

    sequences = df[seq_column].dropna().unique().tolist()

    download_uniprot_database(database, extension)

    blastp_path = check_blast()
    log.info(f"Using blastp at: {blastp_path}")

    make_blast_database(database, extension=extension)

    run_blast(sequences, database, blast_type=blast_type, evalue=evalue)

    results = parse_blast_results("tmp/blast_results.txt")

    # Convert to DataFrame
    sequences_df = pd.DataFrame(sequences, columns=[seq_column])
    sequences_df["id"] = sequences_df.index

    df_blast = pd.DataFrame(results)

    df_blast = df_blast.rename(columns={"query": "id", "subject": "subject_id"})
    df_blast["id"] = df_blast["id"].astype(int)
    df_blast = df_blast.merge(sequences_df, on="id", how="left")
    df_blast = df_blast.drop(columns=["id"])
    df_blast = df_blast.rename(columns={seq_column: "sequence"})

    # Filter by identity threshold before exporting or enriching
    df_blast["identity"] = pd.to_numeric(df_blast["identity"], errors="coerce")
    df_blast = df_blast[df_blast["identity"] >= min_identity]

    # Separate subject into source, accession, entry_name
    df_blast["source"] = df_blast["subject_id"].apply(lambda x: x.split("|")[0])
    df_blast["accession"] = df_blast["subject_id"].apply(lambda x: x.split("|")[1])
    df_blast["entry_name"] = df_blast["subject_id"].apply(lambda x: x.split("|")[2])
    df_blast = df_blast.drop(columns=["subject_id"])

    # Create folder for output if it does not exist
    os.makedirs(output, exist_ok=True)

    # Save to CSV
    df_blast.to_csv(f"{output}/blast_results.csv", index=False)
    log.info(f"BLAST results saved to {output}/blast_results.csv")

    # Clean up temporary files
    os.remove("tmp/blast_results.txt")
    shutil.rmtree("tmp")

    if not no_download:
        metadata = {}
        log.info("Downloading additional UniProt data...")
        instance = UniprotInterface()
        logger.debug(f"Downloading data using blast results\nfields {fields}\ncrossref_fields {crossref_fields}\n")

        response, fetch_metadata = instance.download_batch(
            df_blast, 
            "accession", 
            True, 
            "UniProtKB_AC-ID", 
            "UniProtKB", 
            5000
        )
        metadata["fetch"] = fetch_metadata

        # Save raw results
        with open(f"{output}/raw_response.json", "w") as f:
            json.dump(response, f, indent=2, default=str)

        logger.info("Parsing results...")
        export_df, parsed_metadata = instance.parse_results(
            results=response,
            extract_fields=None,
            to_dataframe=True
        )
        metadata["parsing"] = parsed_metadata
        
        if isinstance(export_df, pd.DataFrame) and not export_df.empty:
            if crossref_fields:
                logger.info("Running cross-reference enrichment...")
                enriched_data, enriched_metadata = run_crossref_enrichment(export_df, crossref_fields.split(","), concat_results=False, to_dataframe=True)
                metadata["enrichement"] = enriched_metadata

                if isinstance(enriched_data, pd.DataFrame) and not enriched_data.empty:
                    export_df = enriched_data
                elif isinstance(enriched_data, dict):
                    for key, value in enriched_data.items():
                        logger.info(f"Saving {key} results into {output} directory")
                        value.to_csv(f"{output}/{key}_results.csv", index=False)
                
            export_df.to_csv(f"{output}/uniprot_results.csv", index=False)
            with open(f"{output}/metadata.json", "w") as f:
                json.dump(metadata, f, indent=2, default=str)
            logger.info(f"Results saved to {output}/uniprot_results.csv")
        else:
            logger.warning("No UniProt data found for the BLAST results.")



        #xref = [VALID_CROSS_REF_FIELDS[c] for c in crossref_fields.split(",") if c in VALID_CROSS_REF_FIELDS]

        #export_df,  = instance.parse_results(results, fields.split(",") + xref)
        #export_df.to_csv(f"{output}/uniprot_results.csv", index=False)
