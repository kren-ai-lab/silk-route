"""Characterization tests for export_dataframe (pre-Polars-migration golden tests).

These pin the *observable file contents* produced by each export format so the
Polars migration can prove "nothing broke". Assertions read the written file
back through the standard library / pyarrow (see ``read_exported_file``), never
through pandas or polars, so they stay valid regardless of the backend that
wrote the file.

The only backend-specific part is constructing the input frame; when the
migration lands, the ``make_frame`` helper is the single line that flips from
pandas to polars — the assertions below should not change.
"""

from __future__ import annotations

import json

import pandas as pd

from bioseq_dl.core.export import export_dataframe
from tests._helpers import read_exported_file


def make_frame(records: list[dict]) -> pd.DataFrame:
    """Build the input frame. Single migration touch-point (pandas -> polars)."""
    return pd.DataFrame(records)


FLAT = [{"id": "P1", "score": 1}, {"id": "P2", "score": 2}]
NESTED = [{"id": "P1", "xrefs": ["a", "b"]}, {"id": "P2", "xrefs": []}]


def test_csv_content_roundtrip(tmp_path):
    path = export_dataframe(make_frame(FLAT), tmp_path / "out.csv")
    rows = read_exported_file(path)
    assert [r["id"] for r in rows] == ["P1", "P2"]
    # CSV is text: numeric values come back as their string form.
    assert [r["score"] for r in rows] == ["1", "2"]


def test_tsv_content_roundtrip(tmp_path):
    path = export_dataframe(make_frame(FLAT), tmp_path / "out.tsv")
    rows = read_exported_file(path)
    assert [r["id"] for r in rows] == ["P1", "P2"]


def test_json_records_orientation(tmp_path):
    path = export_dataframe(make_frame(FLAT), tmp_path / "out.json")
    data = read_exported_file(path)
    # orient="records": a JSON array of row objects.
    assert isinstance(data, list)
    assert data == [{"id": "P1", "score": 1}, {"id": "P2", "score": 2}]


def test_json_preserves_nested_lists(tmp_path):
    path = export_dataframe(make_frame(NESTED), tmp_path / "out.json")
    data = read_exported_file(path)
    assert data[0]["xrefs"] == ["a", "b"]
    assert data[1]["xrefs"] == []


def test_parquet_nested_list_json_encoded(tmp_path):
    # Object columns holding lists/dicts are JSON-encoded to a string column.
    path = export_dataframe(make_frame(NESTED), tmp_path / "out.parquet")
    rows = read_exported_file(path)
    assert rows[0]["id"] == "P1"
    assert rows[0]["xrefs"] == '["a", "b"]'
    # Empty list also JSON-encoded (not left as a missing value).
    assert json.loads(rows[1]["xrefs"]) == []


def test_parquet_flat_numeric_preserved(tmp_path):
    path = export_dataframe(make_frame(FLAT), tmp_path / "out.parquet")
    rows = read_exported_file(path)
    # Numeric columns keep their type through Parquet (not stringified).
    assert rows[0]["score"] == 1
    assert rows[1]["score"] == 2


def test_xml_row_structure(tmp_path):
    path = export_dataframe(make_frame(FLAT), tmp_path / "out.xml")
    rows = read_exported_file(path)
    assert rows[0]["id"] == "P1"
    assert rows[0]["score"] == "1"
