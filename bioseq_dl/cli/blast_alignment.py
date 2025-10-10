import os
import typer
import shutil

from bioseq_dl.constants.databases import BASE_BLAST_DB_DIR as DB_DIR
from bioseq_dl.constants.uniprot import DATABASES, VALID_FIELDS, VALID_CROSS_REF_FIELDS, BASE_URL
from bioseq_dl import UniprotInterface

from bioseq_dl.core.utils.blast_search import (
    download_uniprot_database,
    check_blast,
    make_blast_database,
    run_blast,
    parse_blast_results
)

import pandas as pd

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
        help="Output file"
    ),
    evalue: float = typer.Option(
        0.001, "--evalue", "-v",
        help="E-value threshold for BLAST search."
    ),
    blast_type: str = typer.Option(
        "blastp", "--blast-type", "-b",
        help="Type of BLAST to run. Default is 'blastp'."
    ),
    do_uniprot_search: bool = typer.Option(
        False, "--do-uniprot-search", "-u",
        help="If set, will perform a UniProt search to get additional information for the BLAST hits."
    ),
    fields: str = typer.Option(
        ",".join(VALID_FIELDS), "-f", "--fields", 
        help="Fields to include in the output"
    ),
    crossref_fields: str = typer.Option(
        ",".join(VALID_CROSS_REF_FIELDS), "-xr", "--crossref_fields", 
        help="Cross reference fields to include in the output"
    ),
    min_identity: float = typer.Option(
        90.0, "--min_identity", 
        help="Minimum identity threshold for BLAST search."
    )
):

    df = pd.read_csv(input)

    if seq_column not in df.columns:
        raise ValueError(f"Column '{seq_column}' not found in input file.")

    sequences = df[seq_column].dropna().unique().tolist()

    download_uniprot_database(database, extension)

    blastp_path = check_blast()
    print(f"Using blastp at: {blastp_path}")

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

    # Separate subject into source, accession, entry_name
    df_blast["source"] = df_blast["subject_id"].apply(lambda x: x.split("|")[0])
    df_blast["accession"] = df_blast["subject_id"].apply(lambda x: x.split("|")[1])
    df_blast["entry_name"] = df_blast["subject_id"].apply(lambda x: x.split("|")[2])
    df_blast = df_blast.drop(columns=["subject_id"])

    # Save to CSV
    df_blast.to_csv(output, index=False)
    print(f"BLAST results saved to {output}")

    # Clean up temporary files
    os.remove("tmp/blast_results.txt")
    shutil.rmtree("tmp")

    if do_uniprot_search:
        # Filter by identity
        df_blast = df_blast[df_blast['identity'].astype(float) >= min_identity]

        print("Downloading additional UniProt data...")
        instance = UniprotInterface()
        results = instance.download_batch(df_blast, "accession", True, "UniProtKB_AC-ID", "UniProtKB", 5000)

        # Save raw results
        with open(output + ".json", 'w') as f:
            for result in results:
                f.write(str(result) + '\n')
        
        xref = [VALID_CROSS_REF_FIELDS[c] for c in crossref_fields.split(",") if c in VALID_CROSS_REF_FIELDS]

        export_df = instance.parse_results(results, fields.split(",") + xref)
        export_df.to_csv(output, index=False)

