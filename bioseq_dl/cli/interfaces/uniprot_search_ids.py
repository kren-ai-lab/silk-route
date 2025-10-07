import pandas as pd 
import argparse
import typer
from bioseq_dl import UniprotInterface
from bioseq_dl.constants.databases import DATABASES
from bioseq_dl.constants.uniprot import VALID_FIELDS, VALID_CROSS_REF_FIELDS

app = typer.Typer(help="Search and download sequences from UniProt using IDs.")

@app.command()

def run(
        input: str = typer.Option(
            ..., "-i", "--input", 
            help="CSV file with UniProt IDs"
        ),
        column: str = typer.Option(
            "accession", "-c", "--column", 
            help="Column name with UniProt IDs"
        ),
        output: str = typer.Option(
            ..., "-o", "--output", 
            help="Output file"
        ),
        from_db: str = typer.Option(
            'UniProtKB_AC-ID', "--from_db", 
            help="Database to convert from. Default is UniProtKB_AC-ID (UniProtKB_AC-ID, PDB)"
        ),
        to_db: str = typer.Option(
            'UniProtKB', "--to_db", 
            help="Database to convert to"
        ),
        fields: str = typer.Option(
            ",".join(VALID_FIELDS), "-f", "--fields", 
            help="Fields to include in the output"
        ),
        crossref_fields: str = typer.Option(
            ",".join(VALID_CROSS_REF_FIELDS), "-xr", "--crossref_fields", 
            help="Cross reference fields to include in the output"
        ),
        batch_size: int = typer.Option(
            5000, "-b", "--batch_size", 
            help="Batch size for downloading"
        ),
        auto_db: bool = typer.Option(
            False, "-a", "--auto_db", 
            help="Automatically detect database type"
        ),
        min_identity: float = typer.Option(
            90.0, "--min_identity", 
            help="Minimum identity threshold for BLAST search."
        )
    ):
    df = pd.read_csv(input)

    # Filter by identity
    df = df[df['identity'] >= min_identity]

    print("Downloading data in batches of", batch_size)
    instance = UniprotInterface()
    results = instance.download_batch(df, column, auto_db, from_db, to_db, batch_size)

    # Save raw results
    with open(output + ".json", 'w') as f:
        for result in results:
            f.write(str(result) + '\n')

    xref = [VALID_CROSS_REF_FIELDS[c] for c in crossref_fields.split(",") if c in VALID_CROSS_REF_FIELDS]

    export_df = instance.parse_results(results, fields.split(",") + xref)
    export_df.to_csv(output, index=False)
