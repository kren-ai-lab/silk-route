"""Shared helpers for the offline interface test suite.

Fixtures are frozen raw API responses captured once (see ``tests/_capture``)
and committed under ``tests/fixtures/<api>/<case>.json``. Tests replay them
through ``responses`` so the default test run never touches the network.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, ClassVar
from xml.etree.ElementTree import fromstring

from silkroute.core.interfaces.base import BaseAPIInterface

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# --- Frame helpers ----------------------------------------------------------


def is_frame(obj: Any) -> bool:
    """Return whether ``obj`` looks like a pandas or polars DataFrame."""
    return hasattr(obj, "columns") and (hasattr(obj, "to_dict") or hasattr(obj, "to_dicts"))


def frame_to_records(obj: Any) -> list[dict]:
    """Convert a pandas/polars DataFrame (or list/dict) to a list of row dicts.

    Pandas exposes ``to_dict(orient="records")``; polars exposes ``to_dicts()``.
    NaN values are normalized to None.
    """
    if hasattr(obj, "to_dicts"):
        records = obj.to_dicts()
    elif hasattr(obj, "to_dict"):
        records = obj.to_dict(orient="records")
    elif isinstance(obj, dict):
        records = [obj]
    elif isinstance(obj, list):
        records = obj
    else:
        msg = f"Cannot convert {type(obj)!r} to records"
        raise TypeError(msg)
    return [{k: _nan_to_none(v) for k, v in row.items()} for row in records]


def _nan_to_none(value: Any) -> Any:
    """Map a float NaN to None; leave every other value untouched."""
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def frame_columns(obj: Any) -> list[str]:
    """Return the column names of a pandas/polars DataFrame as a list of str."""
    return [str(c) for c in obj.columns]


def frame_row_count(obj: Any) -> int:
    """Return the row count of a pandas/polars DataFrame."""
    return int(obj.shape[0])


# --- File readback -----------------------------------------------------------


def read_exported_file(path: Path) -> list[dict]:
    """Read a csv/tsv/json/parquet/xml export back to a list of row dicts."""
    suffix = path.suffix.lower().lstrip(".")
    if suffix in ("csv", "tsv"):
        delimiter = "\t" if suffix == "tsv" else ","
        with path.open(newline="") as f:
            return list(csv.DictReader(f, delimiter=delimiter))
    if suffix == "json":
        with path.open() as f:
            return json.load(f)
    if suffix == "parquet":
        import polars as pl

        return pl.read_parquet(path).to_dicts()
    if suffix == "xml":
        root = fromstring(path.read_text())  # noqa: S314  # local test-written file
        return [{child.tag: (child.text or "") for child in rec} for rec in root]
    msg = f"Unsupported export suffix: {suffix}"
    raise ValueError(msg)


def fixture_path(api: str, case: str) -> Path:
    """Return the path to a fixture file (``tests/fixtures/<api>/<case>.json``)."""
    return FIXTURES_DIR / api / f"{case}.json"


def load_fixture(api: str, case: str) -> Any:
    """Load a frozen API response fixture as parsed JSON.

    Return type is ``Any``: fixtures are heterogeneous (dict, list, or a JSON
    string for text APIs like KEGG/SABIO-RK), and tests index/call into them
    freely.
    """
    with fixture_path(api, case).open() as f:
        return json.load(f)


def load_fixture_text(api: str, case: str) -> str:
    """Load a fixture file as raw text (for non-JSON APIs such as KEGG)."""
    return fixture_path(api, case).read_text()


class FakeRecordsInterface(BaseAPIInterface):
    """Minimal offline ``BaseAPIInterface`` for engine-level tests.

    ``fetch`` turns each id of a (comma-joined string or list) query into a
    synthetic ``{"id": x, "value": "val<x>"}`` record and appends the id list it
    was called with to ``fetch_calls`` — enough to exercise caching, batching and
    provenance without a network or a real parser.
    """

    API_NAME = "Fake"
    METHODS: ClassVar[dict[str, Any]] = {
        "get": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {"id": (str, None, True)},
            "group_queries": ["id"],
            "separator": ",",
        }
    }

    def __init__(self, **kwargs):
        super().__init__(min_wait=0, max_wait=0, use_config=False, **kwargs)
        self.fetch_calls: list[list[str]] = []

    def fetch(self, query, *, method="get", **kwargs):
        raw = query["id"] if isinstance(query, dict) else query
        ids = raw.split(",") if isinstance(raw, str) else list(raw)
        self.fetch_calls.append(ids)
        return [{"id": x, "value": f"val{x}"} for x in ids]

    def parse(self, data, fields_to_extract, **kwargs):
        return data
