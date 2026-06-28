"""Helpers for building Polars DataFrames from heterogeneous API records."""

from __future__ import annotations

import json
from typing import Any

import polars as pl


def _frame_per_column(records: list[dict]) -> pl.DataFrame:
    """Build a frame column-by-column, JSON-encoding columns Polars can't unify.

    Columns whose values share a single dtype are kept native; a column Polars
    cannot represent as one dtype (e.g. nested objects with differing sub-schemas
    across rows) is encoded to JSON strings.
    """
    keys = list(dict.fromkeys(key for record in records for key in record))
    series = []
    for key in keys:
        values = [record.get(key) for record in records]
        try:
            series.append(pl.Series(key, values, strict=False))
        except (TypeError, pl.exceptions.PolarsError):
            encoded = [None if value is None else json.dumps(value, default=str) for value in values]
            series.append(pl.Series(key, encoded, dtype=pl.String))
    return pl.DataFrame(series)


def records_to_frame(records: Any) -> pl.DataFrame:
    """Build a DataFrame from record dicts, tolerating irregular nested values.

    A single dict is treated as one row. Falls back to per-column construction
    when a direct construction fails (e.g. nested objects whose sub-schemas differ
    across rows, which Polars cannot unify into one Struct dtype).
    """
    if isinstance(records, dict):
        records = [records]
    if not records:
        return pl.DataFrame()
    try:
        return pl.DataFrame(records, strict=False, infer_schema_length=None)
    except (TypeError, pl.exceptions.PolarsError):
        return _frame_per_column(records)


def drop_all_null_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Drop columns whose every value is null (no-op on an empty frame)."""
    if df.height == 0:
        return df
    return df.select([col for col in df.columns if df[col].null_count() < df.height])
