"""Data export utilities."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd
from pandas.api.types import (
    is_bool_dtype,
    is_datetime64_any_dtype,
    is_numeric_dtype,
    is_object_dtype,
    is_scalar,
)

PathLike = str | Path
USER_EXPORT_FORMATS = ("csv", "json", "xml", "parquet")
DATAFRAME_EXPORT_FORMAT_ERROR = "Unsupported export format 'dataframe'. Use 'csv' instead."


def normalize_user_export_format(output_format: str | None) -> str | None:
    """Normalize a user-facing export format."""
    if output_format is None:
        return None

    normalized = str(output_format).lower().lstrip(".")
    if normalized == "dataframe":
        raise ValueError(DATAFRAME_EXPORT_FORMAT_ERROR)
    if normalized in USER_EXPORT_FORMATS:
        return normalized
    return None


def normalize_export_format(output_format: str | None) -> str | None:
    """Normalize an export format to a file format."""
    if output_format is None:
        return None

    normalized = normalize_user_export_format(output_format)
    if normalized is not None:
        return normalized

    normalized = str(output_format).lower().lstrip(".")
    if normalized == "tsv":
        return normalized
    return None


def normalize_parse_format(output_format: str | None) -> str | None:
    """Normalize an export format to the parser format required upstream."""
    if output_format is None:
        return None

    normalized = output_format.lower().lstrip(".")
    if normalized in {"dataframe", "csv", "tsv", "parquet"}:
        return "dataframe"
    if normalized in {"json", "xml"}:
        return normalized
    return None


def is_missing_parquet_value(value: object) -> bool:
    """Return whether a scalar value should remain missing in Parquet output."""
    if value is None:
        return True

    try:
        missing = pd.isna(value)  # type: ignore[no-matching-overload]  # pandas stub: object arg
    except (TypeError, ValueError):
        return False

    if is_scalar(missing):
        try:
            return bool(missing)
        except TypeError:
            return False
    return False


def make_json_safe_parquet_value(value: object) -> object:
    """Convert container values into JSON-compatible structures."""
    if is_missing_parquet_value(value):
        return None
    if isinstance(value, dict):
        return {str(key): make_json_safe_parquet_value(item) for key, item in value.items()}
    if isinstance(value, set):
        return [make_json_safe_parquet_value(item) for item in sorted(value, key=str)]
    if isinstance(value, (list, tuple)):
        return [make_json_safe_parquet_value(item) for item in value]
    return value


def normalize_parquet_value(value: object) -> object:
    """Normalize a single value for safe Parquet export."""
    if is_missing_parquet_value(value):
        return pd.NA
    if isinstance(value, (list, tuple, set, dict)):
        json_value = make_json_safe_parquet_value(value)
        return json.dumps(json_value, ensure_ascii=False, default=str)
    return value


def parquet_scalar_kind(value: object) -> str:
    """Return a coarse scalar kind for object-column Parquet decisions."""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (dt.datetime, dt.date, pd.Timestamp)):
        return "datetime"
    if isinstance(value, str):
        return "str"
    if isinstance(value, (int, float, complex)):
        return "number"
    return type(value).__name__


def object_column_has_only_datetime_values(series: pd.Series) -> bool:
    """Return whether an object column contains only datetime-like values."""
    has_value = False
    for value in series:
        if is_missing_parquet_value(value):
            continue
        if not isinstance(value, (dt.datetime, dt.date, pd.Timestamp)):
            return False
        has_value = True
    return has_value


def object_column_needs_string_dtype(series: pd.Series) -> bool:
    """Return whether an object column should be converted to string dtype."""
    kinds = set()
    for value in series:
        if is_missing_parquet_value(value):
            continue
        if isinstance(value, (list, tuple, set, dict)):
            return True
        kinds.add(parquet_scalar_kind(value))
    return len(kinds) > 1


def prepare_dataframe_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    """Return a Parquet-safe copy of a DataFrame."""
    safe_df = df.copy()

    for column in safe_df.columns:
        series = safe_df[column]
        if is_numeric_dtype(series) or is_bool_dtype(series) or is_datetime64_any_dtype(series):
            continue
        if not is_object_dtype(series):
            continue

        if object_column_has_only_datetime_values(series):
            try:
                safe_df[column] = pd.to_datetime(series)
            except (TypeError, ValueError, OverflowError):
                normalized = series.map(normalize_parquet_value)
                safe_df[column] = pd.Series(normalized, index=series.index, dtype="string")
            continue

        if object_column_needs_string_dtype(series):
            normalized = series.map(normalize_parquet_value)
            safe_df[column] = pd.Series(normalized, index=series.index, dtype="string")

    return safe_df


def export_dataframe(
    df: pd.DataFrame,
    output_path: PathLike,
    output_format: str | None = None,
) -> Path:
    """Export a DataFrame to CSV, TSV, JSON, XML, or Parquet."""
    if not isinstance(df, pd.DataFrame):
        msg = "export_dataframe expects a pandas DataFrame."
        raise TypeError(msg)

    path = Path(output_path)
    normalized_format = normalize_export_format(output_format or path.suffix)
    if normalized_format is None:
        msg = f"Unsupported export format: {output_format or path.suffix}"
        raise ValueError(msg)

    if not path.suffix:
        path = path.with_suffix(f".{normalized_format}")
    path.parent.mkdir(parents=True, exist_ok=True)

    if normalized_format == "csv":
        df.to_csv(path, index=False)
    elif normalized_format == "tsv":
        df.to_csv(path, sep="\t", index=False)
    elif normalized_format == "json":
        df.to_json(path, orient="records", indent=2)
    elif normalized_format == "xml":
        df.to_xml(path, index=False)
    elif normalized_format == "parquet":
        safe_df = prepare_dataframe_for_parquet(df)
        safe_df.to_parquet(path, index=False)

    return path
