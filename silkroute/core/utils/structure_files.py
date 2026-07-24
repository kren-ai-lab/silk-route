"""Shared helpers for downloading and attaching structure files.

Used by the AlphaFold and PDB interfaces, which both download structure files,
attach a local ``pdb_file`` path to their records, and normalize output paths.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from silkroute.core.utils.frames import records_to_frame
from silkroute.logging import get_logger

log = get_logger("silkroute.utils.structure_files")

WINDOWS_RESERVED_FILENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def display_structure_path(file_path: str | Path, path_base: str | Path | None) -> str:
    """Return a normalized path suitable for interface and workflow output."""
    resolved_path = Path(file_path).resolve()
    if path_base is None:
        return str(resolved_path)
    try:
        return resolved_path.relative_to(Path(path_base).resolve()).as_posix()
    except ValueError:
        log.warning("Structure path is outside workflow output directory: %s", resolved_path)
        return str(resolved_path)


def next_payload_pdb_file_key(record: dict) -> str:
    """Return the next collision-preserving payload key for an incoming pdb_file."""
    if "payload_pdb_file" not in record:
        return "payload_pdb_file"
    index = 2
    while f"payload_{index}_pdb_file" in record:
        index += 1
    return f"payload_{index}_pdb_file"


def attach_pdb_file(record: dict, pdb_file: str | None) -> dict:
    """Attach an authoritative local pdb_file while preserving payload collisions."""
    existing = record.get("pdb_file")
    if "pdb_file" in record and existing != pdb_file:
        record[next_payload_pdb_file_key(record)] = existing
    record["pdb_file"] = pdb_file
    return record


def records_to_structure_frame(records: list[dict]) -> pl.DataFrame:
    """Build a Polars frame with a stable nullable string pdb_file column."""
    frame = records_to_frame(records)
    if "pdb_file" in frame.columns:
        frame = frame.with_columns(pl.col("pdb_file").cast(pl.Utf8))
    return frame
