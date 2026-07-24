"""Helpers for building Polars DataFrames from heterogeneous API records."""

from __future__ import annotations

import json
from typing import Any

import polars as pl


def _encode_json_series(key: str, values: list) -> pl.Series:
    """JSON-encode a column's values into a String series (nulls preserved)."""
    encoded = [
        None if value is None else json.dumps(value, ensure_ascii=False, default=str) for value in values
    ]
    return pl.Series(key, encoded, dtype=pl.String)


def _frame_per_column(records: list[dict]) -> pl.DataFrame:
    """Build a frame column-by-column, JSON-encoding columns Polars can't unify.

    Each column is first built strictly (no coercion). If the strict build fails
    and the column holds nested values (dicts/lists) with differing shapes across
    rows, it is JSON-encoded losslessly; otherwise it is rebuilt leniently so plain
    scalar widening (e.g. int/float) still works.
    """
    keys = list(dict.fromkeys(key for record in records for key in record))
    series = []
    for key in keys:
        values = [record.get(key) for record in records]
        try:
            series.append(pl.Series(key, values, strict=True))
        except (TypeError, pl.exceptions.PolarsError):
            if any(isinstance(value, (dict, list)) for value in values):
                series.append(_encode_json_series(key, values))
            else:
                series.append(pl.Series(key, values, strict=False))
    return pl.DataFrame(series)


def records_to_frame(records: Any) -> pl.DataFrame:
    """Build a DataFrame from record dicts, tolerating irregular nested values.

    A single dict is treated as one row. Columns are built individually so a value
    whose shape varies across rows (e.g. a scalar in one record and a nested object
    in another) is JSON-encoded losslessly instead of being silently coerced.
    """
    if isinstance(records, dict):
        records = [records]
    if not records:
        return pl.DataFrame()
    return _frame_per_column(records)


def drop_all_null_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Drop columns whose every value is null (no-op on an empty frame)."""
    if df.height == 0:
        return df
    return df.select([col for col in df.columns if df[col].null_count() < df.height])
