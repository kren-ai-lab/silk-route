"""Bounded-memory UniProt query-first acquisition to Parquet parts."""

from __future__ import annotations

import contextlib
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
from silkroute.logging import get_logger

if TYPE_CHECKING:
    from silkroute.core.interfaces.uniprot import UniprotInterface

_INTEGER_FIELDS = frozenset({"organism_id", "length"})
_BOOLEAN_FIELDS = frozenset({"reviewed"})
_REPLACE_ATTEMPTS = 5
_PROCESSING_BUFFER_SIZE = 2000
_SEARCH_PAGE_SIZE = 500
_PROGRESS_PAGE_INTERVAL = 20
_DEFAULT_BATCH_SIZE = 5_000_000
log = get_logger("silkroute.workflow.incremental_uniprot")


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
    chunk_size: int | None = None,
    batch_size: int | None = None,
    id_column: str = "record_id",
    include_isoform: bool = False,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Parse pages incrementally into persistent, fixed-schema Parquet writers.

    The checkpoint is a progress report, not a resumable cursor. An existing
    checkpoint or part blocks a new run so completed data is never overwritten.
    ``chunk_size`` retains the original part-size and page-size semantics for
    callers of the initial implementation; new callers use ``batch_size``.
    """
    if chunk_size is not None and batch_size is not None:
        msg = "Specify batch_size or legacy chunk_size, not both."
        raise ValueError(msg)
    legacy_chunk_size = chunk_size is not None
    partition_size = chunk_size if legacy_chunk_size else batch_size
    if partition_size is None:
        partition_size = _DEFAULT_BATCH_SIZE
    if not isinstance(partition_size, int) or isinstance(partition_size, bool) or partition_size < 1:
        msg = "batch_size must be a positive integer."
        raise ValueError(msg)
    buffer_size = (
        min(partition_size, _PROCESSING_BUFFER_SIZE) if legacy_chunk_size else _PROCESSING_BUFFER_SIZE
    )
    page_size = min(partition_size, _SEARCH_PAGE_SIZE) if legacy_chunk_size else _SEARCH_PAGE_SIZE
    if not id_column or id_column.isspace():
        msg = "id_column must be non-empty."
        raise ValueError(msg)
    try:
        import pyarrow as pa  # noqa: PLC0415 - load only for partitioned acquisitions
        import pyarrow.parquet as pq  # noqa: PLC0415 - load only for partitioned acquisitions
    except ImportError as exc:
        msg = "Partitioned UniProt downloads require pyarrow. Install SilkRoute with its dependencies."
        raise RuntimeError(msg) from exc
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
            pl.Int64
            if field in _INTEGER_FIELDS
            else pl.Float64
            if field == "annotation_score"
            else pl.Boolean
            if field in _BOOLEAN_FIELDS
            else pl.String
        )
        for field in parsed_fields
    }
    if id_column != "accession":
        schema = {id_column: pl.String, **schema}
    arrow_schema = pa.schema(
        [
            pa.field(
                name,
                pa.int64()
                if dtype == pl.Int64
                else pa.float64()
                if dtype == pl.Float64
                else pa.bool_()
                if dtype == pl.Boolean
                else pa.string(),
            )
            for name, dtype in schema.items()
        ]
    )
    if output_dir.exists() and any(output_dir.iterdir()):
        msg = "Partitioned UniProt requires a fresh, empty output directory. Automatic resume is unavailable."
        raise ValueError(msg)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "uniprot_incremental_checkpoint.json"
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
        "write_mode": "partitioned",
        "batch_size": partition_size,
        "processing_buffer_size": buffer_size,
        "page_size": page_size,
        "legacy_chunk_size": chunk_size,
        "id_column": id_column,
        "pages_fetched": 0,
        "attempts": 0,
        "records_acquired": 0,
        "records_written": 0,
        "total_results": None,
        "total_validation": "pending",
        "parquet_schema": {
            name: str(dtype) for name, dtype in zip(arrow_schema.names, arrow_schema.types, strict=True)
        },
        "field_coverage": dict.fromkeys(parsed_fields, 0),
        "files": [],
        "error": None,
    }
    # Exclusive creation claims the destination even when two processes race.
    with checkpoint_path.open("x", encoding="utf-8") as stream:
        json.dump(checkpoint, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    buffer: list[dict[str, Any]] = []
    last_id: str | None = None
    writer = None
    unfinished_path: Path | None = None
    active_rows = 0
    active_coverage = dict.fromkeys(parsed_fields, 0)
    writer_healthy = True

    log.info(
        "UniProt partitioned download started (batch_size=%s buffer=%s page_size=%s)",
        partition_size,
        buffer_size,
        page_size,
    )
    log.info("Query: %s", interpreted)

    def open_partition() -> None:
        nonlocal writer, unfinished_path
        with tempfile.NamedTemporaryFile(dir=output_dir, suffix=".parquet.incomplete", delete=False) as tmp:
            unfinished_path = Path(tmp.name)
        writer = pq.ParquetWriter(unfinished_path, arrow_schema, compression="zstd")

    def publish_partition() -> None:
        nonlocal writer, unfinished_path, active_rows, active_coverage, writer_healthy
        if writer is None or unfinished_path is None or active_rows == 0:
            return
        try:
            writer.close()
            writer = None
            with unfinished_path.open("r+b") as stream:
                os.fsync(stream.fileno())
            parquet_meta = pq.read_metadata(unfinished_path)
            if parquet_meta.num_rows != active_rows or parquet_meta.schema.to_arrow_schema() != arrow_schema:
                msg = "Parquet partition validation failed; the incomplete file was not published."
                raise RuntimeError(msg)  # noqa: TRY301
            number = len(checkpoint["files"]) + 1
            part = output_dir / f"uniprot_results_part-{number:06d}.parquet"
            size_bytes = unfinished_path.stat().st_size
            checksum = _sha256(unfinished_path)
            _replace_with_retry(unfinished_path, part)
            unfinished_path = None
            checkpoint["files"].append(
                {
                    "path": part.name,
                    "rows": active_rows,
                    "size_bytes": size_bytes,
                    "sha256": checksum,
                }
            )
            checkpoint["records_written"] += active_rows
            for field, count in active_coverage.items():
                checkpoint["field_coverage"][field] += count
            log.info("Part %06d completed (%s records, %.2f GiB)", number, active_rows, size_bytes / 1024**3)
            active_rows = 0
            active_coverage = dict.fromkeys(parsed_fields, 0)
            _atomic_json(checkpoint_path, checkpoint)
            log.info("Checkpoint updated (parts=%s records_saved=%s)", number, checkpoint["records_written"])
        except Exception:
            writer_healthy = False
            raise

    def write_buffer() -> None:
        nonlocal active_rows, writer_healthy
        start = 0
        while start < len(buffer):
            try:
                if writer is None:
                    open_partition()
                if writer is None:
                    msg = "Parquet writer did not open."
                    raise RuntimeError(msg)  # noqa: TRY301
                take = min(len(buffer) - start, partition_size - active_rows)
                rows = buffer[start : start + take]
                table = pa.Table.from_pylist(rows, schema=arrow_schema)
                writer.write_table(table, row_group_size=table.num_rows)
            except Exception:
                writer_healthy = False
                raise
            active_rows += take
            for row in rows:
                for field in parsed_fields:
                    if row.get(field) is not None:
                        active_coverage[field] += 1
            start += take
            if active_rows == partition_size:
                publish_partition()
        buffer.clear()

    try:
        for page in interface.iter_search_pages(
            interpreted,
            return_fields,
            include_isoform=include_isoform,
            timeout=timeout,
            page_size=page_size,
        ):
            payload = page["payload"]
            checkpoint["pages_fetched"] += 1
            checkpoint["attempts"] += page["attempts"]
            checkpoint["records_acquired"] += len(payload["results"])
            reported_total = page.get("total_results")
            if reported_total is not None and str(reported_total).isdigit():
                reported_total = int(reported_total)
                if checkpoint["total_results"] is None:
                    checkpoint["total_results"] = reported_total
                elif checkpoint["total_results"] != reported_total:
                    checkpoint["total_validation"] = "changed"
                    msg = "UniProt total-results header changed during acquisition."
                    raise RuntimeError(msg)  # noqa: TRY301
            if (
                checkpoint["total_results"] is not None
                and checkpoint["records_acquired"] > checkpoint["total_results"]
            ):
                checkpoint["total_validation"] = "mismatch"
                msg = "UniProt returned more records than its total-results header."
                raise RuntimeError(msg)  # noqa: TRY301
            if payload.get("failedIds"):
                msg = "UniProt returned failed identifiers during incremental search."
                raise ValueError(msg)  # noqa: TRY301
            records, _ = interface.parse(payload, extract_fields=parsed_fields, format="json")
            if not isinstance(records, list):
                msg = "UniProt parser did not return JSON records."
                raise TypeError(msg)  # noqa: TRY301
            if len(records) != len(payload["results"]):
                msg = "UniProt parser returned fewer records than the current page."
                raise RuntimeError(msg)  # noqa: TRY301
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
                buffer.append(row)
                if len(buffer) >= buffer_size:
                    write_buffer()
            if checkpoint["pages_fetched"] == 1 or checkpoint["pages_fetched"] % _PROGRESS_PAGE_INTERVAL == 0:
                total = checkpoint["total_results"]
                progress = f" ({checkpoint['records_acquired'] / total:.1%})" if total else ""
                log.info(
                    "Page %s received (%s records); progress: %s acquired%s",
                    checkpoint["pages_fetched"],
                    len(payload["results"]),
                    checkpoint["records_acquired"],
                    progress,
                )
            _atomic_json(checkpoint_path, checkpoint)
        if (
            checkpoint["total_results"] is not None
            and checkpoint["records_acquired"] != checkpoint["total_results"]
        ):
            checkpoint["total_validation"] = "mismatch"
            msg = (
                f"UniProt pagination ended at {checkpoint['records_acquired']} records; "
                f"expected {checkpoint['total_results']}."
            )
            raise RuntimeError(msg)  # noqa: TRY301
        checkpoint["total_validation"] = (
            "matched" if checkpoint["total_results"] is not None else "unavailable"
        )
        write_buffer()
        publish_partition()
    except Exception as exc:
        # Graceful request/parse failures can publish valid rows. A writer failure cannot.
        if writer_healthy:
            try:
                write_buffer()
                publish_partition()
            except Exception as finalization_error:  # noqa: BLE001 - preserve the original failure
                checkpoint["finalization_error"] = str(finalization_error)
        try:
            if writer is not None:
                with contextlib.suppress(Exception):
                    writer.close()
        finally:
            if unfinished_path is not None:
                unfinished_path.unlink(missing_ok=True)
            checkpoint["status"] = "failed"
            checkpoint["error"] = str(exc)
            checkpoint["finished_at"] = _utc_now()
            _atomic_json(checkpoint_path, checkpoint)
            log.exception(
                "UniProt partitioned download failed (acquired=%s saved=%s)",
                checkpoint["records_acquired"],
                checkpoint["records_written"],
            )
        raise
    checkpoint["status"] = "completed" if checkpoint["records_written"] else "empty_result"
    checkpoint["finished_at"] = _utc_now()
    _atomic_json(checkpoint_path, checkpoint)
    log.info(
        "UniProt partitioned download completed (records=%s parts=%s)",
        checkpoint["records_written"],
        len(checkpoint["files"]),
    )
    return checkpoint
