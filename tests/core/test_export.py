"""Unit tests for DataFrame export and format normalization."""

from __future__ import annotations

from typing import Any

import polars as pl
import pytest

from bioseq_dl.core.export import (
    DATAFRAME_EXPORT_FORMAT_ERROR,
    export_dataframe,
    normalize_export_format,
    normalize_parse_format,
    normalize_user_export_format,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("csv", "csv"),
        (".JSON", "json"),
        ("xml", "xml"),
        ("parquet", "parquet"),
        ("tsv", None),  # tsv is not a user-facing format
        ("weird", None),
        (None, None),
    ],
)
def test_normalize_user_export_format(value, expected):
    assert normalize_user_export_format(value) == expected


def test_normalize_user_export_format_dataframe_raises():
    with pytest.raises(ValueError, match=DATAFRAME_EXPORT_FORMAT_ERROR):
        normalize_user_export_format("dataframe")


def test_normalize_export_format_allows_tsv():
    assert normalize_export_format("tsv") == "tsv"
    assert normalize_export_format(".csv") == "csv"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("csv", "dataframe"),
        ("tsv", "dataframe"),
        ("parquet", "dataframe"),
        ("json", "json"),
        ("xml", "xml"),
        ("nope", None),
    ],
)
def test_normalize_parse_format(value, expected):
    assert normalize_parse_format(value) == expected


@pytest.fixture
def df():
    return pl.DataFrame([{"a": 1, "b": "x"}, {"a": 2, "b": "y"}])


def test_export_csv_roundtrip(df, tmp_path):
    path = export_dataframe(df, tmp_path / "out.csv")
    assert path.exists()
    assert pl.read_csv(path).equals(df)


def test_export_tsv(df, tmp_path):
    path = export_dataframe(df, tmp_path / "out.tsv")
    back = pl.read_csv(path, separator="\t")
    assert back.equals(df)


def test_export_json(df, tmp_path):
    path = export_dataframe(df, tmp_path / "out.json")
    back = pl.read_json(path)
    assert back["a"].to_list() == [1, 2]


def test_export_infers_suffix_from_format(df, tmp_path):
    path = export_dataframe(df, tmp_path / "noext", output_format="csv")
    assert path.suffix == ".csv"
    assert path.exists()


def test_export_unsupported_format_raises(df, tmp_path):
    with pytest.raises(ValueError, match="Unsupported export format"):
        export_dataframe(df, tmp_path / "out.bogus")


def test_export_non_dataframe_raises(tmp_path):
    not_a_df: Any = [1, 2, 3]  # intentionally wrong type for the runtime guard
    with pytest.raises(TypeError):
        export_dataframe(not_a_df, tmp_path / "out.csv")


def test_export_parquet_with_nested_values(tmp_path):
    # List columns are written as native nested (List) types.
    df = pl.DataFrame([{"id": "P1", "xrefs": ["a", "b"]}, {"id": "P2", "xrefs": []}], strict=False)
    path = export_dataframe(df, tmp_path / "out.parquet")
    back = pl.read_parquet(path)
    assert back["id"][0] == "P1"
    assert back["xrefs"][0].to_list() == ["a", "b"]
