"""Offline tests for the workflow graph-payload externalization guards.

Path-traversal / reserved-name filename guards, digest stability, collision-free
selection, and atomic refuse-to-clobber — the only path writing attacker-influenced
strings (``source_accession``) to disk.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from bioseq_dl.cli.workflows import (
    GRAPH_JSON_COLUMN,
    externalize_graph_payloads,
    graph_payload_digest,
    safe_graph_file_path,
    safe_graph_filename_part,
    select_graph_file_path,
    write_graph_payload_atomically,
)


def _graph_row(accession="P12345", payload=None):
    return {
        "source_accession": accession,
        "source_query": "P12345",
        "source_database": "pathwaycommons",
        "source_endpoint": "fetch",
        "graph_format": "json",
        "graph_record_count": 1,
        GRAPH_JSON_COLUMN: json.dumps(payload if payload is not None else {"nodes": [1]}),
    }


class TestSafeGraphFilenamePart:
    def test_strips_path_separators_and_traversal(self):
        assert "/" not in safe_graph_filename_part("../../etc/passwd")
        assert "\\" not in safe_graph_filename_part("..\\..\\windows")
        assert ".." not in safe_graph_filename_part("../../etc")

    def test_windows_reserved_name_is_prefixed(self):
        # CON: Windows reserved device name.
        assert safe_graph_filename_part("CON").upper().startswith("GRAPH_")
        assert safe_graph_filename_part("con.txt").lower().startswith("graph_")

    def test_empty_after_sanitizing_returns_empty(self):
        assert safe_graph_filename_part("///") == ""
        assert safe_graph_filename_part(None) == ""

    def test_normal_accession_preserved(self):
        assert safe_graph_filename_part("P12345") == "P12345"


class TestSafeGraphFilePath:
    def test_traversal_filename_rejected(self, tmp_path):
        graph_dir = Path("graphs") / "label"
        for bad in ("../evil.json", "a/b.json", "a\\b.json", "..", ".", "c:evil.json"):
            with pytest.raises(ValueError, match="Unsafe graph payload filename"):
                safe_graph_file_path(tmp_path, graph_dir, bad)

    def test_trailing_space_or_dot_rejected(self, tmp_path):
        graph_dir = Path("graphs") / "label"
        with pytest.raises(ValueError, match="Unsafe graph payload filename"):
            safe_graph_file_path(tmp_path, graph_dir, "ok.json ")
        with pytest.raises(ValueError, match="Unsafe graph payload filename"):
            safe_graph_file_path(tmp_path, graph_dir, "ok.json.")

    def test_safe_filename_stays_below_graph_dir(self, tmp_path):
        graph_dir = Path("graphs") / "label"
        path = safe_graph_file_path(tmp_path, graph_dir, "P12345__label__abcd.json")
        assert path.is_relative_to((tmp_path / graph_dir).resolve())


class TestGraphPayloadDigest:
    def test_stable_and_order_independent(self):
        row = _graph_row()
        text_a = json.dumps({"a": 1, "b": 2}, sort_keys=True, separators=(",", ":"))
        text_b = json.dumps({"b": 2, "a": 1}, sort_keys=True, separators=(",", ":"))
        assert graph_payload_digest(row, text_a) == graph_payload_digest(row, text_b)

    def test_differs_on_payload_change(self):
        row = _graph_row()
        d1 = graph_payload_digest(row, json.dumps({"x": 1}))
        d2 = graph_payload_digest(row, json.dumps({"x": 2}))
        assert d1 != d2

    def test_differs_on_provenance_change(self):
        text = json.dumps({"x": 1})
        d1 = graph_payload_digest(_graph_row(accession="P00001"), text)
        d2 = graph_payload_digest(_graph_row(accession="P00002"), text)
        assert d1 != d2


class TestSelectGraphFilePath:
    def test_distinct_payloads_get_distinct_files(self, tmp_path):
        graph_dir = Path("graphs") / "label"
        used: set[str] = set()
        p1 = select_graph_file_path(
            _graph_row(),
            output_dir=tmp_path,
            graph_dir=graph_dir,
            export_label="label",
            digest="a" * 64,
            payload_bytes=b"one",
            used_file_names=used,
        )
        p2 = select_graph_file_path(
            _graph_row(),
            output_dir=tmp_path,
            graph_dir=graph_dir,
            export_label="label",
            digest="a" * 64,
            payload_bytes=b"two",
            used_file_names=used,
        )
        # Same digest+label, different bytes -> must not reuse a name.
        p1.parent.mkdir(parents=True, exist_ok=True)
        p1.write_bytes(b"one")
        assert p1 != p2


class TestWriteGraphPayloadAtomically:
    def test_writes_and_reports(self, tmp_path):
        path = tmp_path / "graphs" / "label" / "g.json"
        size, sha, written = write_graph_payload_atomically(path, b"payload")
        assert written is True
        assert size == len(b"payload")
        assert path.read_bytes() == b"payload"
        assert len(sha) == 64

    def test_identical_existing_is_noop(self, tmp_path):
        path = tmp_path / "graphs" / "label" / "g.json"
        write_graph_payload_atomically(path, b"payload")
        _size, _sha, written = write_graph_payload_atomically(path, b"payload")
        assert written is False

    def test_refuses_to_overwrite_divergent(self, tmp_path):
        path = tmp_path / "graphs" / "label" / "g.json"
        write_graph_payload_atomically(path, b"payload")
        with pytest.raises(FileExistsError, match="Refusing to overwrite"):
            write_graph_payload_atomically(path, b"different")


class TestExternalizeGraphPayloads:
    def test_traversal_accession_stays_within_graph_dir(self, tmp_path):
        content = pl.DataFrame([_graph_row(accession="../../../etc/passwd")])
        export_df, _artifacts, meta = externalize_graph_payloads(
            content, output_dir=tmp_path, export_label="label"
        )
        assert meta["graph_payload_files_written"] == 1
        written = list((tmp_path / "graphs" / "label").glob("*.json"))
        assert len(written) == 1
        assert all(p.is_relative_to((tmp_path / "graphs" / "label").resolve()) for p in written)
        # Inline payload replaced by file reference.
        assert GRAPH_JSON_COLUMN not in export_df.columns
        assert "graph_sha256" in export_df.columns

    def test_no_graph_column_is_passthrough(self, tmp_path):
        content = pl.DataFrame({"accession": ["P1"]})
        export_df, artifacts, _meta = externalize_graph_payloads(
            content, output_dir=tmp_path, export_label="label"
        )
        assert artifacts == []
        assert export_df.equals(content)
