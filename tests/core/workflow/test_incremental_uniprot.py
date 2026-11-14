"""Offline tests for bounded UniProt acquisitions."""

from __future__ import annotations

import hashlib
import json
import tracemalloc
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

import polars as pl
import pytest
from niquests.exceptions import ConnectionError as NiquestsConnectionError
from niquests_mock import build_response, startswith

from silkroute.core.exceptions import RequestError
from silkroute.core.interfaces import uniprot as uniprot_module
from silkroute.core.interfaces.uniprot import API_URL, UniprotInterface
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
            chunk_size=200,
        )
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peaks.append(peak)
    assert peaks[1] < peaks[0] * 4
