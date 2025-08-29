import os, re
from typing import List
import typer
import shutil
import subprocess
import tarfile
from pathlib import Path
from urllib.request import urlopen
from bioseq_dl.constants.databases import BASE_BLAST_DB_DIR as DB_DIR

import pandas as pd

app = typer.Typer(help="Tools for sequence alignment and database management.")

BLAST_BASE_URL = "https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/LATEST/"
UNIPROT_BASE_URL = "https://ftp.uniprot.org/pub/databases/uniprot/current_release"
BLAST_DIR = Path("blast_bin")

databases = {
    "uniprotkb_reviewed": "knowledgebase/complete/uniprot_sprot",
    "uniprotkb_unreviewed": "knowledgebase/complete/uniprot_trembl",
    "uniref100": "uniref/niref100/uniref100",
    "uniref90": "uniref/uniref90/uniref90",
    "uniref50": "uniref/uniref50/uniref50",
}

def download_uniprot_database(db_name: str, extension: str = "xml"):
    """ Download a Uniprot database from the Uniprot FTP server.
    Args:
        db_name (str): Name of the database to download.
        extension (str): File extension of the database. Default is "xml".
    """

    if db_name not in databases:
        raise ValueError(f"Database {db_name} is not supported. Supported databases are: {', '.join(databases.keys())}.")
    
    db_path = os.path.join(DB_DIR, f"{db_name}.{extension}")
    
    if not os.path.exists(db_path):
        os.makedirs(DB_DIR, exist_ok=True)
        url = f"{UNIPROT_BASE_URL}/{databases[db_name]}.{extension}.gz"
        os.system(f"wget {url} -O {db_path}.gz")
        print(f"Unzipping {db_path}...")
        subprocess.run(["gunzip", db_path], check=True)
    else:
        print(f"Database {db_name} already exists at {db_path}.")

def get_latest_version_url():
    """Retrieve the latest BLAST+ tarball URL from the NCBI FTP site."""
    with urlopen(BLAST_BASE_URL) as response:
        html = response.read().decode("utf-8")
    # Look for something like: ncbi-blast-2.16.0+-x64-linux.tar.gz
    match = re.search(r'ncbi-blast-(\d+\.\d+\.\d+\+)-x64-linux\.tar\.gz', html)
    if match:
        version = match.group(1)
        tar_name = f"ncbi-blast-{version}-x64-linux.tar.gz"
        return version, BLAST_BASE_URL + tar_name
    else:
        raise RuntimeError("Could not find the latest BLAST version from NCBI.")

def is_blast_installed():
    """Check if 'blastp' is available in the system PATH."""
    try:
        subprocess.run(["blastp", "-version"], check=True, stdout=subprocess.DEVNULL)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def download_and_extract_blast(version: str, url: str):
    """Download and extract the BLAST+ tarball."""
    tarball_name = url.split("/")[-1]
    if not Path(tarball_name).exists():
        print(f"Downloading BLAST+ {version}...")
        subprocess.run(["wget", url], check=True)

    print("Extracting BLAST+...")
    with tarfile.open(tarball_name, "r:gz") as tar:
        tar.extractall(BLAST_DIR)
    print(f"BLAST extracted to: {BLAST_DIR.resolve()}")


def get_local_blastp_path(version: str):
    """Return the path to local blastp binary."""
    return BLAST_DIR / f"ncbi-blast-{version}" / "bin" / "blastp"


def check_blast():
    """Ensure BLAST is installed. Return path to `blastp` binary."""
    if is_blast_installed():
        print("System-wide BLAST is installed.")
        return shutil.which("blastp")
    else:
        version, url = get_latest_version_url()
        local_blastp = get_local_blastp_path(version)
        if not local_blastp.exists():
            print(f"BLAST {version} not found locally. Installing...")
            BLAST_DIR.mkdir(exist_ok=True)
            download_and_extract_blast(version, url)
        else:
            print(f"Using already downloaded BLAST {version}.")
        return str(local_blastp)

def make_blast_database(db_name: str, db_type: str = "prot", extension: str = "xml"):
    """Create a BLAST database from the Uniprot database."""
    db_path = os.path.join(DB_DIR, f"{db_name}.{extension}")
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database {db_name} not found at {db_path}. Please download it first.")
    
    # Check if the database is already created
    blast_db_path = os.path.join(DB_DIR, db_name)
    extensions = [".pdb", ".phr", ".pin", ".psq", ".pot", ".psq", ".ptf", ".pto"]
    makedb = False
    # For all extensions check if exists if there is one failing makedb again
    for ext in extensions:
        if not os.path.exists(blast_db_path + "/db" + ext):
            makedb = True
            break
    if makedb:
        print(f"Creating BLAST database for {db_name}...")
        blast_db_cmd = [
            "makeblastdb",
            "-in", db_path,
            "-dbtype", db_type,
            "-out", os.path.join(DB_DIR, db_name) + "/db",
        ]
    
        subprocess.run(blast_db_cmd, check=True)
        print(f"BLAST database created at: {os.path.join(DB_DIR, databases[db_name])}")
    else:
        print(f"BLAST database already exists at {blast_db_path}. No need to create it again.")

def run_blast(sequences: List[str], db_name: str, blast_type: str = "blastp", evalue: float = 0.001):
    """Run BLAST search."""
    blast_db_path = os.path.join(DB_DIR, db_name)
    if not os.path.exists(blast_db_path):
        raise FileNotFoundError(f"Database {db_name} not found at {blast_db_path}. Please download it first.")

    # Make tmp directory if it does not exist
    os.makedirs("tmp", exist_ok=True)

    # Write sequences to a temporary file
    with open("tmp/sequences.fasta", "w") as f:
        for i, seq in enumerate(sequences):
            f.write(f">{i}\n{seq}\n")
    
    blast_cmd = [
        blast_type,
        "-query", "tmp/sequences.fasta",
        "-db", blast_db_path + "/db",
        "-outfmt", "6",
        "-evalue", str(evalue),
    ]
    
    print(f"Running BLAST search...")
    with open("tmp/blast_results.txt", "w") as f:
        subprocess.run(blast_cmd, stdout=f, check=True)

    # Clean up temporary file
    os.remove("tmp/sequences.fasta")

def parse_blast_results(file_path: str, identity_threshold: float = 90.0):
    """Parse BLAST results from a file."""
    with open(file_path, "r") as f:
        results = f.readlines()
    
    parsed_results = []
    for line in results:
        fields = line.strip().split("\t")
        identity = float(fields[2])
        if identity >= identity_threshold:
            parsed_results.append({
                "query": fields[0],
                "subject": fields[1],
                "identity": fields[2],
                "alignment_length": fields[3],
                "evalue": fields[4],
                "bit_score": fields[5],
            })
    
    return parsed_results

@app.command()
def run(
    database: str = typer.Option(
        ..., "--database", "-d",
        help="Database to download. Supported databases: " + ", ".join(databases.keys())
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
        ..., "--output", "-o",
        help="Output file for BLAST results."
    ),
    evalue: float = typer.Option(
        0.001, "--evalue", "-v",
        help="E-value threshold for BLAST search."
    ),
    blast_type: str = typer.Option(
        "blastp", "--blast-type", "-b",
        help="Type of BLAST to run. Default is 'blastp'."
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