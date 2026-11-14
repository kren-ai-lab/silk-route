"""Bounded-memory UniProt query-first acquisition to Parquet parts."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import polars as pl

from silkroute.constants.uniprot import (
    get_effective_uniprot_return_fields,
    get_uniprot_parsed_fields,
    normalize_uniprot_return_fields,
)
from silkroute.core.workflow.query_interpreter import build_default_uniprot_interpreter

if TYPE_CHECKING:
    from silkroute.core.interfaces.uniprot import UniprotInterface

_INTEGER_FIELDS = frozenset({"organism_id", "length", "annotation_score"})
_BOOLEAN_FIELDS = frozenset({"reviewed"})
_REPLACE_ATTEMPTS = 5


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _replace_with_retry(source: Path, target: Path) -> None:
    """Allow transient Windows file scanner locks while keeping atomic rename."""
    for attempt in range(_REPLACE_ATTEMPTS):
        try:
            source.replace(target)
        except PermissionError:
            if attempt == _REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(0.05 * (attempt + 1))
        else:
            return


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
    ) as tmp:
        json.dump(value, tmp, indent=2, ensure_ascii=False, default=str)
        tmp.flush()
        os.fsync(tmp.fileno())
        name = tmp.name
    try:
        _replace_with_retry(Path(name), path)
    finally:
        Path(name).unlink(missing_ok=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _value(value: Any, dtype: type[pl.DataType]) -> Any:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, default=str)
    if dtype == pl.String:
        return str(value)
    return value


def acquire_uniprot_parts(
    interface: UniprotInterface,
    *,
    query: str,
    fields: str | None,
    output_dir: Path,
    chunk_size: int = 2000,
    id_column: str = "record_id",
    include_isoform: bool = False,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Parse pages incrementally and atomically publish fixed-schema Parquet parts.

    The checkpoint is a progress report, not a resumable cursor. An existing
    checkpoint or part blocks a new run so completed data is never overwritten.
    """
    if chunk_size < 1:
        msg = "chunk_size must be a positive integer."
        raise ValueError(msg)
    if not id_column or id_column.isspace():
        msg = "id_column must be non-empty."
        raise ValueError(msg)
    selected = normalize_uniprot_return_fields(fields)
    parsed_fields = get_uniprot_parsed_fields(selected) if selected else list(interface.field_map_base)
    if "accession" not in parsed_fields:
        parsed_fields.append("accession")
    if id_column in parsed_fields and id_column != "accession":
        msg = f"The UniProt result already has a column '{id_column}'; choose another id_column."
        raise ValueError(msg)
    interpreted = build_default_uniprot_interpreter().interpret(query=query)
    if not isinstance(interpreted, str) or not interpreted:
        msg = "Incremental UniProt requires one non-empty interpreted query."
        raise ValueError(msg)
    return_fields = ", ".join(get_effective_uniprot_return_fields(fields))
    schema: dict[str, type[pl.DataType]] = {
        field: (
            pl.Int64 if field in _INTEGER_FIELDS else pl.Boolean if field in _BOOLEAN_FIELDS else pl.String
        )
        for field in parsed_fields
    }
    if id_column != "accession":
        schema = {id_column: pl.String, **schema}
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "uniprot_incremental_checkpoint.json"
    if checkpoint_path.exists() or any(output_dir.glob("uniprot_results_part-*.parquet")):
        msg = (
            "Incremental UniProt output already exists; choose a new output directory. "
            "Automatic resume is unavailable."
        )
        raise ValueError(msg)
    checkpoint: dict[str, Any] = {
        "status": "running",
        "started_at": _utc_now(),
        "finished_at": None,
        "query": query,
        "interpreted_query": interpreted,
        "fields": return_fields,
        "parsed_fields": parsed_fields,
        "sort": "accession asc",
        "include_isoform": include_isoform,
        "chunk_size": chunk_size,
        "page_size": min(chunk_size, 500),
        "id_column": id_column,
        "pages_fetched": 0,
        "attempts": 0,
        "records_acquired": 0,
        "records_written": 0,
        "total_results": None,
        "field_coverage": dict.fromkeys(parsed_fields, 0),
        "files": [],
        "error": None,
    }
    _atomic_json(checkpoint_path, checkpoint)
    buffer: list[dict[str, Any]] = []
    last_id: str | None = None

    def flush() -> None:
        if not buffer:
            return
        number = len(checkpoint["files"]) + 1
        part = output_dir / f"uniprot_results_part-{number:06d}.parquet"
        frame = pl.DataFrame(buffer, schema=schema, strict=True)
        with tempfile.NamedTemporaryFile(dir=output_dir, suffix=".parquet.tmp", delete=False) as tmp:
            temp = Path(tmp.name)
        try:
            frame.write_parquet(temp)
            _replace_with_retry(temp, part)
        finally:
            temp.unlink(missing_ok=True)
        checkpoint["files"].append(
            {
                "path": part.name,
                "rows": len(buffer),
                "size_bytes": part.stat().st_size,
                "sha256": _sha256(part),
            }
        )
        checkpoint["records_written"] += len(buffer)
        buffer.clear()
        _atomic_json(checkpoint_path, checkpoint)

    try:
        for page in interface.iter_search_pages(
            interpreted,
            return_fields,
            include_isoform=include_isoform,
            timeout=timeout,
            page_size=min(chunk_size, 500),
        ):
            payload = page["payload"]
            if payload.get("failedIds"):
                msg = "UniProt returned failed identifiers during incremental search."
                raise ValueError(msg)  # noqa: TRY301
            records, _ = interface.parse(payload, extract_fields=parsed_fields, format="json")
            if not isinstance(records, list):
                msg = "UniProt parser did not return JSON records."
                raise TypeError(msg)  # noqa: TRY301
            checkpoint["pages_fetched"] += 1
            checkpoint["attempts"] += page["attempts"]
            checkpoint["records_acquired"] += len(payload["results"])
            if checkpoint["total_results"] is None and str(page.get("total_results", "")).isdigit():
                checkpoint["total_results"] = int(page["total_results"])
            for record in records:
                if not isinstance(record, dict):
                    msg = "UniProt parser returned an invalid record."
                    raise TypeError(msg)  # noqa: TRY301
                if record.get("status") == "failed":
                    msg = "UniProt returned failed identifiers during incremental search."
                    raise ValueError(msg)  # noqa: TRY301
                accession = record.get("accession")
                if not isinstance(accession, str) or not accession.strip():
                    msg = "UniProt record has no accession; cannot assign a stable identifier."
                    raise ValueError(msg)  # noqa: TRY301
                if last_id is not None and accession <= last_id:
                    msg = f"Duplicate or unsorted UniProt accession: {accession}."
                    raise ValueError(msg)  # noqa: TRY301
                last_id = accession
                row = {
                    field: _value(record.get(field), dtype)
                    for field, dtype in schema.items()
                    if field != id_column or field == "accession"
                }
                if id_column != "accession":
                    row[id_column] = accession
                for field in parsed_fields:
                    if record.get(field) is not None:
                        checkpoint["field_coverage"][field] += 1
                buffer.append(row)
                if len(buffer) >= chunk_size:
                    flush()
            _atomic_json(checkpoint_path, checkpoint)
        flush()
    except Exception as exc:
        # Keep fully parsed rows from successful pages. Never claim success.
        try:
            flush()
        finally:
            checkpoint["status"] = "failed"
            checkpoint["error"] = str(exc)
            checkpoint["finished_at"] = _utc_now()
            _atomic_json(checkpoint_path, checkpoint)
        raise
    checkpoint["status"] = "completed" if checkpoint["records_written"] else "empty_result"
    checkpoint["finished_at"] = _utc_now()
    _atomic_json(checkpoint_path, checkpoint)
    return checkpoint
