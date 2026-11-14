"""Offline tests for bounded UniProt acquisitions."""

from __future__ import annotations

import hashlib
import json
import tracemalloc
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

import polars as pl
import pyarrow.parquet as pq
import pytest
from niquests.exceptions import ConnectionError as NiquestsConnectionError
from niquests_mock import build_response, startswith

from silkroute.core.exceptions import RequestError
from silkroute.core.interfaces import uniprot as uniprot_module
from silkroute.core.interfaces.uniprot import API_URL, UniprotInterface
from silkroute.core.workflow import incremental_uniprot as incremental_module
from silkroute.core.workflow.incremental_uniprot import acquire_uniprot_parts


def _record(number: int) -> dict:
    return {
        "primaryAccession": f"P{number:05d}",
        "organism": {"taxonId": 9606, "lineage": ["Eukaryota", "Metazoa"] if number % 2 else None},
        "sequence": {"length": number, "value": f"M{number}"},
    }


def _pages(total: int, page_size: int, *, fail_after: int | None = None):
    for start in range(1, total + 1, page_size):
        if fail_after is not None and start > fail_after:
            raise RuntimeError("page unavailable")
        yield {
            "payload": {"results": [_record(i) for i in range(start, min(start + page_size, total + 1))]},
            "page_number": (start - 1) // page_size + 1,
            "attempts": 1,
            "next_url": None,
            "total_results": str(total),
        }


def test_incremental_parts_have_stable_schema_ids_checksums_and_legacy_data(tmp_path, monkeypatch):
    interface = UniprotInterface()
    monkeypatch.setattr(interface, "iter_search_pages", lambda *args, **kwargs: _pages(7, 2))
    checkpoint = acquire_uniprot_parts(
        interface,
        query="kinase",
        fields="accession,organism_id,lineage,length,sequence",
        output_dir=tmp_path,
        chunk_size=3,
    )
    assert checkpoint["status"] == "completed"
    assert checkpoint["records_acquired"] == checkpoint["records_written"] == 7
    assert [item["rows"] for item in checkpoint["files"]] == [3, 3, 1]
    parts = [tmp_path / item["path"] for item in checkpoint["files"]]
    assert len({tuple(pl.read_parquet(path).schema.items()) for path in parts}) == 1
    for item, path in zip(checkpoint["files"], parts, strict=True):
        assert item["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    rows = pl.concat([pl.read_parquet(path) for path in parts]).to_dicts()
    assert [row["record_id"] for row in rows] == [f"P{i:05d}" for i in range(1, 8)]
    legacy, _ = interface.parse(
        {"results": [_record(i) for i in range(1, 8)]},
        extract_fields=["accession", "organism_id", "lineage", "length", "sequence"],
        format="json",
    )
    for row, expected in zip(rows, cast("list[dict[str, Any]]", legacy), strict=True):
        assert {key: row[key] for key in ("accession", "organism_id", "length", "sequence")} == {
            key: expected[key] for key in ("accession", "organism_id", "length", "sequence")
        }
        assert (json.loads(row["lineage"]) if row["lineage"] else None) == expected["lineage"]


def test_failure_preserves_parts_and_marks_checkpoint_failed(tmp_path, monkeypatch):
    interface = UniprotInterface()
    monkeypatch.setattr(interface, "iter_search_pages", lambda *args, **kwargs: _pages(7, 2, fail_after=4))
    with pytest.raises(RuntimeError, match="page unavailable"):
        acquire_uniprot_parts(
            interface,
            query="kinase",
            fields="accession,sequence",
            output_dir=tmp_path,
            chunk_size=3,
        )
    checkpoint = json.loads((tmp_path / "uniprot_incremental_checkpoint.json").read_text())
    assert checkpoint["status"] == "failed"
    assert checkpoint["records_written"] == 4
    assert len(checkpoint["files"]) == 2
    assert not list(tmp_path.glob("*.tmp"))
    with pytest.raises(ValueError, match="Automatic resume is unavailable"):
        acquire_uniprot_parts(interface, query="kinase", fields="accession,sequence", output_dir=tmp_path)


def test_duplicate_accession_across_parts_fails_without_overwriting_first_part(tmp_path, monkeypatch):
    interface = UniprotInterface()

    def pages(*args, **kwargs):
        yield {"payload": {"results": [_record(1)]}, "attempts": 1, "total_results": "2"}
        yield {"payload": {"results": [_record(1)]}, "attempts": 1, "total_results": "2"}

    monkeypatch.setattr(interface, "iter_search_pages", pages)
    with pytest.raises(ValueError, match="Duplicate or unsorted"):
        acquire_uniprot_parts(
            interface,
            query="kinase",
            fields="accession,sequence",
            output_dir=tmp_path,
            chunk_size=1,
        )
    checkpoint = json.loads((tmp_path / "uniprot_incremental_checkpoint.json").read_text())
    assert checkpoint["status"] == "failed"
    assert checkpoint["records_written"] == 1
    assert len(checkpoint["files"]) == 1


def test_iterator_retries_current_page_and_uses_exact_cursor_url(niquests_mock, monkeypatch):
    interface = UniprotInterface(total_retries=2)
    cursor_url = f"{API_URL}/uniprotkb/search?cursor=two&format=json&size=2"
    calls = []

    def serve(request):
        calls.append(request.url)
        if "cursor=two" in request.url:
            if calls.count(cursor_url) == 1:
                raise NiquestsConnectionError("transient")
            return build_response(request, json={"results": [_record(2)]})
        return build_response(
            request,
            json={"results": [_record(1)]},
            headers={"Link": f'<{cursor_url}>; rel="next"'},
        )

    monkeypatch.setattr(uniprot_module.time, "sleep", lambda _: None)
    niquests_mock.get(url=startswith(f"{API_URL}/uniprotkb/search")).mock(side_effect=serve)
    pages = list(interface.iter_search_pages("kinase", "accession", page_size=2))
    assert [p["payload"]["results"][0]["primaryAccession"] for p in pages] == ["P00001", "P00002"]
    assert [p["attempts"] for p in pages] == [1, 2]
    assert calls[1:] == [cursor_url, cursor_url]
    assert parse_qs(urlparse(calls[0]).query)["size"] == ["2"]


def test_exhausted_page_retry_keeps_first_part_and_failed_status(tmp_path, niquests_mock, monkeypatch):
    interface = UniprotInterface(total_retries=2)
    cursor_url = f"{API_URL}/uniprotkb/search?cursor=broken&format=json&size=1"

    def serve(request):
        if "cursor=broken" in request.url:
            raise NiquestsConnectionError("connection reset")
        return build_response(
            request,
            json={"results": [_record(1)]},
            headers={"Link": f'<{cursor_url}>; rel="next"'},
        )

    monkeypatch.setattr(uniprot_module.time, "sleep", lambda _: None)
    niquests_mock.get(url=startswith(f"{API_URL}/uniprotkb/search")).mock(side_effect=serve)
    with pytest.raises(RequestError, match="search page 2 failed after 2 attempts"):
        acquire_uniprot_parts(
            interface,
            query="kinase",
            fields="accession,sequence",
            output_dir=tmp_path,
            chunk_size=1,
        )
    checkpoint = json.loads((tmp_path / "uniprot_incremental_checkpoint.json").read_text())
    assert checkpoint["status"] == "failed"
    assert checkpoint["records_acquired"] == checkpoint["records_written"] == 1
    assert len(checkpoint["files"]) == 1


def test_synthetic_dataset_peak_python_memory_is_bounded(tmp_path, monkeypatch):
    interface = UniprotInterface()
    peaks = []
    for total in (1000, 10000):
        destination = tmp_path / str(total)
        monkeypatch.setattr(
            interface, "iter_search_pages", lambda *args, total=total, **kwargs: _pages(total, 100)
        )
        tracemalloc.start()
        acquire_uniprot_parts(
            interface,
            query="kinase",
            fields="accession,sequence",
            output_dir=destination,
            batch_size=5_000_000,
        )
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peaks.append(peak)
        assert (
            len(json.loads((destination / "uniprot_incremental_checkpoint.json").read_text())["files"]) == 1
        )
    assert peaks[1] < peaks[0] * 4


def test_multiple_buffers_share_a_partition_and_rotate_at_batch_size(tmp_path, monkeypatch):
    interface = UniprotInterface()
    monkeypatch.setattr(incremental_module, "_PROCESSING_BUFFER_SIZE", 2)
    monkeypatch.setattr(interface, "iter_search_pages", lambda *args, **kwargs: _pages(7, 3))
    checkpoint = acquire_uniprot_parts(
        interface,
        query="kinase",
        fields="accession,sequence",
        output_dir=tmp_path,
        batch_size=5,
    )
    assert checkpoint["page_size"] == 500
    assert checkpoint["processing_buffer_size"] == 2
    assert [part["rows"] for part in checkpoint["files"]] == [5, 2]
    first = tmp_path / checkpoint["files"][0]["path"]
    assert pq.read_metadata(first).num_row_groups == 3
    assert pl.read_parquet(first)["accession"].to_list() == [f"P{i:05d}" for i in range(1, 6)]


def test_annotation_score_is_float_and_nulls_are_preserved(tmp_path, monkeypatch):
    interface = UniprotInterface()
    payload = {
        "results": [
            {"primaryAccession": "P00001", "annotationScore": 3.5, "organism": {"lineage": ["A"]}},
            {"primaryAccession": "P00002", "organism": {"lineage": None}},
        ]
    }
    monkeypatch.setattr(
        interface,
        "iter_search_pages",
        lambda *args, **kwargs: iter([{"payload": payload, "attempts": 1, "total_results": "2"}]),
    )
    checkpoint = acquire_uniprot_parts(
        interface,
        query="kinase",
        fields="accession,annotation_score,lineage",
        output_dir=tmp_path,
        batch_size=5,
    )
    frame = pl.read_parquet(tmp_path / checkpoint["files"][0]["path"])
    assert frame.schema["annotation_score"] == pl.Float64
    assert frame["annotation_score"].to_list() == [3.5, None]
    assert frame["lineage"].to_list() == ['["A"]', None]


def test_premature_end_marks_failed_even_when_partial_part_is_valid(tmp_path, monkeypatch):
    interface = UniprotInterface()

    def pages(*args, **kwargs):
        yield {"payload": {"results": [_record(1), _record(2)]}, "attempts": 1, "total_results": "3"}

    monkeypatch.setattr(interface, "iter_search_pages", pages)
    with pytest.raises(RuntimeError, match="pagination ended"):
        acquire_uniprot_parts(
            interface,
            query="kinase",
            fields="accession,sequence",
            output_dir=tmp_path,
            batch_size=5,
        )
    checkpoint = json.loads((tmp_path / "uniprot_incremental_checkpoint.json").read_text())
    assert checkpoint["status"] == "failed"
    assert checkpoint["total_validation"] == "mismatch"
    assert checkpoint["records_acquired"] == checkpoint["records_written"] == 2


def test_changed_total_header_marks_failed(tmp_path, monkeypatch):
    interface = UniprotInterface()

    def pages(*args, **kwargs):
        yield {"payload": {"results": [_record(1)]}, "attempts": 1, "total_results": "2"}
        yield {"payload": {"results": [_record(2)]}, "attempts": 1, "total_results": "3"}

    monkeypatch.setattr(interface, "iter_search_pages", pages)
    with pytest.raises(RuntimeError, match="header changed"):
        acquire_uniprot_parts(
            interface,
            query="kinase",
            fields="accession",
            output_dir=tmp_path,
            batch_size=5,
        )
    checkpoint = json.loads((tmp_path / "uniprot_incremental_checkpoint.json").read_text())
    assert checkpoint["status"] == "failed"
    assert checkpoint["total_validation"] == "changed"
    assert checkpoint["records_written"] == 1


def test_missing_accession_fails_without_final_output(tmp_path, monkeypatch):
    interface = UniprotInterface()

    def pages(*args, **kwargs):
        yield {"payload": {"results": [{"sequence": {"value": "AAA"}}]}, "attempts": 1, "total_results": "1"}

    monkeypatch.setattr(interface, "iter_search_pages", pages)
    with pytest.raises(ValueError, match="no accession"):
        acquire_uniprot_parts(
            interface,
            query="kinase",
            fields="accession,sequence",
            output_dir=tmp_path,
            batch_size=5,
        )
    checkpoint = json.loads((tmp_path / "uniprot_incremental_checkpoint.json").read_text())
    assert checkpoint["status"] == "failed"
    assert checkpoint["records_written"] == 0
    assert not list(tmp_path.glob("*.parquet"))


def test_existing_output_directory_is_untouched(tmp_path):
    interface = UniprotInterface()
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "metadata.json"
    sentinel.write_text("previous run")
    with pytest.raises(ValueError, match="fresh, empty output"):
        acquire_uniprot_parts(
            interface,
            query="kinase",
            fields="accession",
            output_dir=output,
            batch_size=5,
        )
    assert sentinel.read_text() == "previous run"
    assert list(output.iterdir()) == [sentinel]


def test_writer_failure_never_publishes_incomplete_partition(tmp_path, monkeypatch):
    interface = UniprotInterface()
    monkeypatch.setattr(incremental_module, "_PROCESSING_BUFFER_SIZE", 2)
    monkeypatch.setattr(interface, "iter_search_pages", lambda *args, **kwargs: _pages(5, 5))
    real_writer = pq.ParquetWriter

    class FailingWriter:
        def __init__(self, *args, **kwargs):
            self.inner = real_writer(*args, **kwargs)
            self.writes = 0

        def write_table(self, *args, **kwargs):
            self.writes += 1
            if self.writes == 2:
                raise OSError("simulated write interruption")
            self.inner.write_table(*args, **kwargs)

        def close(self):
            self.inner.close()

    monkeypatch.setattr(pq, "ParquetWriter", FailingWriter)
    with pytest.raises(OSError, match="simulated write interruption"):
        acquire_uniprot_parts(
            interface,
            query="kinase",
            fields="accession,sequence",
            output_dir=tmp_path,
            batch_size=5,
        )
    checkpoint = json.loads((tmp_path / "uniprot_incremental_checkpoint.json").read_text())
    assert checkpoint["status"] == "failed"
    assert checkpoint["records_written"] == 0
    assert not list(tmp_path.glob("*.parquet"))
    assert not list(tmp_path.glob("*.incomplete"))


def test_progress_logging_reports_start_pages_parts_and_completion(tmp_path, monkeypatch, caplog):
    interface = UniprotInterface()
    monkeypatch.setattr(interface, "iter_search_pages", lambda *args, **kwargs: _pages(2, 2))
    with caplog.at_level("INFO", logger="silkroute.workflow.incremental_uniprot"):
        acquire_uniprot_parts(
            interface,
            query="kinase",
            fields="accession",
            output_dir=tmp_path,
            batch_size=1,
        )
    messages = [record.message for record in caplog.records]
    assert any("partitioned download started" in message for message in messages)
    assert any("Page 1 received" in message for message in messages)
    assert any("Part 000001 completed" in message for message in messages)
    assert any("Checkpoint updated" in message for message in messages)
    assert any("download completed" in message for message in messages)
