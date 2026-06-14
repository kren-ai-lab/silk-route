import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Literal
from urllib.request import urlopen

from bioseq_dl.constants.databases import BASE_BLAST_DB_DIR as DB_DIR
from bioseq_dl.constants.uniprot import BASE_URL, DATABASES
from bioseq_dl.logging import get_logger

log = get_logger("bioseq_dl.core.utils.blast_search")

BLAST_BASE_URL = "https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/LATEST/"
BLAST_DIR = Path("blast_bin")


def download_uniprot_database(
    db_name: Literal["uniprotkb_reviewed", "uniprotkb_unreviewed", "uniref100", "uniref90", "uniref50"],
    extension: str = "xml",
):
    """Download a Uniprot database from the Uniprot FTP server.

    Args:
        db_name (str): Name of the database to download.
        extension (str): File extension of the database. Default is "xml".

    """
    if db_name not in DATABASES:
        msg = f"Database {db_name} is not supported. Supported databases are: {', '.join(DATABASES.keys())}."
        raise ValueError(msg)

    db_path = DB_DIR / f"{db_name}.{extension}"

    if not db_path.exists():
        DB_DIR.mkdir(parents=True, exist_ok=True)
        url = f"{BASE_URL}/{DATABASES[db_name]}.{extension}.gz"
        os.system(f"wget {url} -O {db_path}.gz")
        log.info(f"Unzipping {db_path}...")
        subprocess.run(["gunzip", db_path], check=True)
    else:
        log.info(f"Database {db_name} already exists at {db_path}.")


def get_latest_version_url():
    """Retrieve the latest BLAST+ tarball URL from the NCBI FTP site."""
    with urlopen(BLAST_BASE_URL) as response:
        html = response.read().decode("utf-8")
    # Look for something like: ncbi-blast-2.16.0+-x64-linux.tar.gz
    match = re.search(r"ncbi-blast-(\d+\.\d+\.\d+\+)-x64-linux\.tar\.gz", html)
    if match:
        version = match.group(1)
        tar_name = f"ncbi-blast-{version}-x64-linux.tar.gz"
        return version, BLAST_BASE_URL + tar_name
    msg = "Could not find the latest BLAST version from NCBI."
    raise RuntimeError(msg)


def is_blast_installed():
    """Check if 'blastp' is available in the system PATH."""
    try:
        subprocess.run(["blastp", "-version"], check=True, stdout=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    else:
        return True


def download_and_extract_blast(version: str, url: str):
    """Download and extract the BLAST+ tarball."""
    tarball_name = url.rsplit("/", maxsplit=1)[-1]
    if not Path(tarball_name).exists():
        log.info(f"Downloading BLAST+ {version}...")
        subprocess.run(["wget", url], check=True)

    log.info("Extracting BLAST+...")
    with tarfile.open(tarball_name, "r:gz") as tar:
        tar.extractall(BLAST_DIR)
    log.info(f"BLAST extracted to: {BLAST_DIR.resolve()}")


def get_local_blastp_path(version: str):
    """Return the path to local blastp binary."""
    return BLAST_DIR / f"ncbi-blast-{version}" / "bin" / "blastp"


def check_blast():
    """Ensure BLAST is installed. Return path to `blastp` binary."""
    if is_blast_installed():
        log.info("System-wide BLAST is installed.")
        return shutil.which("blastp")
    version, url = get_latest_version_url()
    local_blastp = get_local_blastp_path(version)
    if not local_blastp.exists():
        log.info(f"BLAST {version} not found locally. Installing...")
        BLAST_DIR.mkdir(exist_ok=True)
        download_and_extract_blast(version, url)
    else:
        log.info(f"Using already downloaded BLAST {version}.")
    return str(local_blastp)


def make_blast_database(db_name: str, db_type: str = "prot", extension: str = "xml"):
    """Create a BLAST database from the Uniprot database."""
    db_path = DB_DIR / f"{db_name}.{extension}"
    if not db_path.exists():
        msg = f"Database {db_name} not found at {db_path}. Please download it first."
        raise FileNotFoundError(msg)

    # Check if the database is already created
    blast_db_path = DB_DIR / db_name
    extensions = [".pdb", ".phr", ".pin", ".psq", ".pot", ".psq", ".ptf", ".pto"]
    makedb = False
    # For all extensions check if exists if there is one failing makedb again
    for ext in extensions:
        if not (blast_db_path / f"db{ext}").exists():
            makedb = True
            break
    if makedb:
        log.info(f"Creating BLAST database for {db_name}...")
        blast_db_cmd = [
            "makeblastdb",
            "-in",
            str(db_path),
            "-dbtype",
            db_type,
            "-out",
            str(blast_db_path / "db"),
        ]

        subprocess.run(blast_db_cmd, check=True)
        log.info(f"BLAST database created at: {DB_DIR / DATABASES[db_name]}")
    else:
        log.info(f"BLAST database already exists at {blast_db_path}. No need to create it again.")


def run_blast(sequences: list[str], db_name: str, blast_type: str = "blastp", evalue: float = 0.001):
    """Run BLAST search."""
    blast_db_path = DB_DIR / db_name
    if not blast_db_path.exists():
        msg = f"Database {db_name} not found at {blast_db_path}. Please download it first."
        raise FileNotFoundError(msg)

    # Make tmp directory if it does not exist
    Path("tmp").mkdir(parents=True, exist_ok=True)

    # Write sequences to a temporary file
    with Path("tmp/sequences.fasta").open("w") as f:
        f.writelines(f">{i}\n{seq}\n" for i, seq in enumerate(sequences))

    blast_cmd = [
        blast_type,
        "-query",
        "tmp/sequences.fasta",
        "-db",
        str(blast_db_path / "db"),
        "-outfmt",
        "6 qseqid sseqid pident length evalue bitscore qcovs",
        "-evalue",
        str(evalue),
    ]

    log.info("Running BLAST search...")
    with Path("tmp/blast_results.txt").open("w") as f:
        subprocess.run(blast_cmd, stdout=f, check=True)

    # Clean up temporary file
    Path("tmp/sequences.fasta").unlink()


def parse_blast_results(file_path: str, identity_threshold: float = 90.0):
    """Parse BLAST results from a file."""
    with Path(file_path).open() as f:
        results = f.readlines()

    parsed_results = []
    for line in results:
        fields = line.strip().split("\t")
        identity = float(fields[2])
        if identity >= identity_threshold:
            parsed_results.append(
                {
                    "query": fields[0],
                    "subject": fields[1],
                    "identity": fields[2],
                    "alignment_length": fields[3],
                    "evalue": fields[4],
                    "bit_score": fields[5],
                    "coverage": fields[6],
                }
            )

    return parsed_results
