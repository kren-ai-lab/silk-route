"""Unit tests for DataFrame export and format normalization."""

from __future__ import annotations

from typing import Any

import pandas as pd
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
    return pd.DataFrame([{"a": 1, "b": "x"}, {"a": 2, "b": "y"}])


def test_export_csv_roundtrip(df, tmp_path):
    path = export_dataframe(df, tmp_path / "out.csv")
    assert path.exists()
    assert pd.read_csv(path).equals(df)


def test_export_tsv(df, tmp_path):
    path = export_dataframe(df, tmp_path / "out.tsv")
    back = pd.read_csv(path, sep="\t")
    assert back.equals(df)


def test_export_json(df, tmp_path):
    path = export_dataframe(df, tmp_path / "out.json")
    back = pd.read_json(path)
    assert list(back["a"]) == [1, 2]


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
    # Polars-first: list columns are written as native nested (List) types.
    df = pd.DataFrame([{"id": "P1", "xrefs": ["a", "b"]}, {"id": "P2", "xrefs": []}])
    path = export_dataframe(df, tmp_path / "out.parquet")
    back = pd.read_parquet(path)
    assert back.loc[0, "id"] == "P1"
    assert list(back.loc[0, "xrefs"]) == ["a", "b"]
