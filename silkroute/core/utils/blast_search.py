"""BLAST sequence search utilities.

BLAST+ is treated as an external dependency: this module never installs it. Use
your environment manager (pixi/conda/apt) to provide ``blastp``/``makeblastdb``
on PATH; ``check_blast`` only locates and validates them.
"""

import csv
import gzip
import shutil
import subprocess
import urllib.request
from pathlib import Path

from silkroute.constants.databases import BASE_BLAST_DB_DIR as DB_DIR
from silkroute.constants.uniprot import BASE_URL, DATABASES
from silkroute.logging import get_logger

log = get_logger("silkroute.core.utils.blast_search")

# Surfaced when BLAST+ is not available on PATH.
BLAST_INSTALL_HINT = (
    "BLAST+ was not found on PATH. Install it with your environment manager, e.g.:\n"
    "  pixi global add blast\n"
    "  conda install -c bioconda blast\n"
    "  apt install ncbi-blast+"
)

# Columns emitted by the CSV output (outfmt 10), in order.
BLAST_OUTPUT_COLUMNS = ("qseqid", "sseqid", "pident", "length", "evalue", "bitscore", "qcovs")


def download_uniprot_database(
    db_name: str,
    extension: str = "xml",
) -> None:
    """Download a Uniprot database from the Uniprot FTP server.

    Args:
        db_name (str): Name of the database to download.
        extension (str): File extension of the database. Default is "xml".

    """
    if db_name not in DATABASES:
        msg = f"Database {db_name} is not supported. Supported databases are: {', '.join(DATABASES.keys())}."
        raise ValueError(msg)

    db_path = DB_DIR / f"{db_name}.{extension}"
    if db_path.exists():
        log.info("Database %s already exists at %s.", db_name, db_path)
        return

    DB_DIR.mkdir(parents=True, exist_ok=True)
    url = f"{BASE_URL}/{DATABASES[db_name]}.{extension}.gz"
    gz_path = db_path.with_name(f"{db_path.name}.gz")
    log.info("Downloading %s...", url)
    urllib.request.urlretrieve(url, gz_path)  # noqa: S310  # trusted UniProt URL constant
    log.info("Unzipping %s...", gz_path)
    with gzip.open(gz_path, "rb") as f_in, db_path.open("wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    gz_path.unlink()


def check_blast(program: str = "blastp") -> str:
    """Locate a BLAST+ executable, requiring it to be installed on PATH.

    BLAST+ is an external dependency and is never installed by this library.

    Args:
        program (str): BLAST+ program to locate (e.g. ``blastp``). Default is "blastp".

    Returns:
        str: Absolute path to the resolved executable.

    Raises:
        RuntimeError: If ``program`` is not found on PATH, with installation hints.

    """
    path = shutil.which(program)
    if path is None:
        raise RuntimeError(BLAST_INSTALL_HINT)
    log.info("Using %s at: %s", program, path)
    return path


def make_blast_database(db_name: str, db_type: str = "prot", extension: str = "xml") -> None:
    """Create a BLAST database from a downloaded Uniprot database.

    Skips creation if all expected BLAST index files already exist.

    Args:
        db_name (str): Name of the database to build.
        db_type (str): BLAST database type passed to ``makeblastdb``. Default is "prot".
        extension (str): File extension of the source database. Default is "xml".

    Raises:
        FileNotFoundError: If the source database file does not exist.

    """
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
        log.info("Creating BLAST database for %s...", db_name)
        blast_db_cmd = [
            "makeblastdb",
            "-in",
            str(db_path),
            "-dbtype",
            db_type,
            "-out",
            str(blast_db_path / "db"),
        ]

        subprocess.run(blast_db_cmd, check=True)  # noqa: S603  # trusted local BLAST tool, dev tooling
        log.info("BLAST database created at: %s", DB_DIR / DATABASES[db_name])
    else:
        log.info("BLAST database already exists at %s. No need to create it again.", blast_db_path)


def run_blast(
    sequences: list[str], db_name: str, blast_executable: str = "blastp", evalue: float = 0.001
) -> None:
    """Run a BLAST search and write CSV results (outfmt 10) to ``tmp/blast_results.txt``.

    Writes the input sequences to a temporary FASTA file, runs BLAST, and removes
    the temporary FASTA file afterward.

    Args:
        sequences (list[str]): Query sequences to search.
        db_name (str): Name of the local BLAST database to query.
        blast_executable (str): Path to (or name of) the BLAST program to run, as
            resolved by :func:`check_blast`. Default is "blastp".
        evalue (float): E-value threshold for reported hits. Default is 0.001.

    Raises:
        FileNotFoundError: If the BLAST database does not exist.

    """
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
        blast_executable,
        "-query",
        "tmp/sequences.fasta",
        "-db",
        str(blast_db_path / "db"),
        "-outfmt",
        f"10 {' '.join(BLAST_OUTPUT_COLUMNS)}",
        "-evalue",
        str(evalue),
    ]

    log.info("Running BLAST search...")
    with Path("tmp/blast_results.txt").open("w") as f:
        subprocess.run(blast_cmd, stdout=f, check=True)  # noqa: S603  # trusted local BLAST tool, dev tooling

    # Clean up temporary file
    Path("tmp/sequences.fasta").unlink()


def parse_blast_results(file_path: str, identity_threshold: float = 90.0) -> list[dict]:
    """Parse CSV BLAST results (outfmt 10), keeping hits above an identity threshold.

    Args:
        file_path (str): Path to the BLAST CSV output file.
        identity_threshold (float): Minimum percent identity to keep a hit. Default is 90.0.

    Returns:
        list[dict]: One dict per retained hit with query, subject, identity,
            alignment length, e-value, bit score, and coverage.

    """
    parsed_results = []
    with Path(file_path).open(newline="") as f:
        for row in csv.reader(f):
            if len(row) < len(BLAST_OUTPUT_COLUMNS):
                # Skip blank or malformed rows (e.g. a trailing newline).
                continue
            fields = dict(zip(BLAST_OUTPUT_COLUMNS, row, strict=False))
            if float(fields["pident"]) >= identity_threshold:
                parsed_results.append(
                    {
                        "query": fields["qseqid"],
                        "subject": fields["sseqid"],
                        "identity": fields["pident"],
                        "alignment_length": fields["length"],
                        "evalue": fields["evalue"],
                        "bit_score": fields["bitscore"],
                        "coverage": fields["qcovs"],
                    }
                )

    return parsed_results
