"""Data export utilities."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element, ElementTree, SubElement

import polars as pl
import polars.selectors as cs

PathLike = str | Path
USER_EXPORT_FORMATS = ("csv", "json", "xml", "parquet")
DATAFRAME_EXPORT_FORMAT_ERROR = "Unsupported export format 'dataframe'. Use 'csv' instead."

# Dtypes that CSV/TSV cannot represent directly; JSON-encoded to a string column
# before writing.
_NESTED_SELECTOR = cs.by_dtype(pl.List, pl.Array, pl.Struct, pl.Object)


def normalize_user_export_format(output_format: str | None) -> str | None:
    """Normalize a user-facing export format.

    Args:
        output_format (str | None): Format string or file extension to normalize.

    Returns:
        str | None: One of the user export formats, or None if unrecognized.

    Raises:
        ValueError: If the format is ``dataframe``.

    """
    if output_format is None:
        return None

    normalized = str(output_format).lower().lstrip(".")
    if normalized == "dataframe":
        raise ValueError(DATAFRAME_EXPORT_FORMAT_ERROR)
    if normalized in USER_EXPORT_FORMATS:
        return normalized
    return None


def normalize_export_format(output_format: str | None) -> str | None:
    """Normalize an export format to a file format.

    Like ``normalize_user_export_format`` but also accepts ``tsv``.

    Args:
        output_format (str | None): Format string or file extension to normalize.

    Returns:
        str | None: A supported file format, or None if unrecognized.

    Raises:
        ValueError: If the format is ``dataframe``.

    """
    if output_format is None:
        return None

    normalized = str(output_format).lower().lstrip(".")
    if normalized == "dataframe":
        raise ValueError(DATAFRAME_EXPORT_FORMAT_ERROR)
    if normalized in USER_EXPORT_FORMATS or normalized == "tsv":
        return normalized
    return None


def normalize_parse_format(output_format: str | None) -> str | None:
    """Normalize an export format to the parser format required upstream.

    Maps tabular/parquet formats to ``dataframe`` and passes ``json``/``xml`` through.

    Args:
        output_format (str | None): Format string or file extension to normalize.

    Returns:
        str | None: ``dataframe``, ``json``, ``xml``, or None if unrecognized.

    """
    if output_format is None:
        return None

    normalized = output_format.lower().lstrip(".")
    if normalized in {"dataframe", "csv", "tsv", "parquet"}:
        return "dataframe"
    if normalized in {"json", "xml"}:
        return normalized
    return None


def _json_encode_value(value: Any) -> str | None:
    """JSON-encode a single nested cell value for a text column; pass None through."""
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _encode_nested_for_text(df: pl.DataFrame) -> pl.DataFrame:
    """JSON-encode List/Struct/Array/Object columns to strings; leave scalars as-is."""
    nested = df.select(_NESTED_SELECTOR).columns
    if not nested:
        return df
    return df.with_columns(
        pl.col(name).map_elements(_json_encode_value, return_dtype=pl.String) for name in nested
    )


def _encode_object_for_parquet(df: pl.DataFrame) -> pl.DataFrame:
    """JSON-encode ``Object`` columns to strings; keep List/Struct/Array native."""
    opaque = df.select(cs.by_dtype(pl.Object)).columns
    if not opaque:
        return df
    return df.with_columns(
        pl.col(name).map_elements(_json_encode_value, return_dtype=pl.String) for name in opaque
    )


def _xml_cell_text(value: Any) -> str:
    """Render a cell value as XML element text (nested values become JSON)."""
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, default=str)
    return str(value)


def _xml_tag(column: str) -> str:
    """Coerce a column name into a valid XML element name.

    Characters illegal in XML names are replaced with ``_``; a name that does not
    start with a letter or ``_`` is prefixed with ``_``. The original column name
    is preserved in a ``name`` attribute whenever it differs (see ``_write_xml``).
    """
    tag = re.sub(r"[^\w.\-]", "_", column, flags=re.UNICODE)
    if not tag or not (tag[0].isalpha() or tag[0] == "_"):
        tag = "_" + tag
    return tag


def _write_xml(df: pl.DataFrame, path: Path) -> None:
    """Write the frame as ``<data><row><col>value</col>...</row></data>`` XML."""
    root = Element("data")
    for record in df.to_dicts():
        row = SubElement(root, "row")
        for column, value in record.items():
            name = str(column)
            tag = _xml_tag(name)
            element = SubElement(row, tag)
            if tag != name:
                element.set("name", name)
            element.text = _xml_cell_text(value)
    ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def export_dataframe(
    df: pl.DataFrame,
    output_path: PathLike,
    output_format: str | None = None,
) -> Path:
    """Export a DataFrame to CSV, TSV, JSON, XML, or Parquet.

    The format is taken from ``output_format`` or the path suffix; a missing suffix
    is added from the resolved format and parent directories are created. Nested
    columns (lists/structs) are JSON-encoded for the text formats (CSV/TSV) and
    written natively for Parquet/JSON.

    Args:
        df (pl.DataFrame): DataFrame to export.
        output_path (PathLike): Destination file path.
        output_format (str | None): Explicit format; falls back to the path suffix.

    Returns:
        Path: The path the DataFrame was written to.

    Raises:
        TypeError: If ``df`` is not a Polars DataFrame.
        ValueError: If the export format is unsupported.

    """
    if not isinstance(df, pl.DataFrame):
        msg = "export_dataframe expects a Polars DataFrame."
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
        _encode_nested_for_text(df).write_csv(path)
    elif normalized_format == "tsv":
        _encode_nested_for_text(df).write_csv(path, separator="\t")
    elif normalized_format == "json":
        df.write_json(path)
    elif normalized_format == "xml":
        _write_xml(df, path)
    elif normalized_format == "parquet":
        _encode_object_for_parquet(df).write_parquet(path)

    return path
