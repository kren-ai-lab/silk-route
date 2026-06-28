"""Characterization tests for BaseAPIInterface's tabular behavior (pre-Polars).

Golden tests pinning the *observable* contract of the fetch/parse/cache engine
so the Polars migration can prove nothing broke:

- ``_maybe_parse`` format conversion (dataframe / json / xml) content,
- ``_build_data_info`` metadata shape (counts, names, missing) — NOT backend
  dtype strings, which legitimately change with the backend,
- ``fetch_single`` / ``fetch_batch`` returned content and the cache round-trip
  (a second call served from cache yields identical content).

Assertions use the backend-agnostic ``frame_*`` helpers so they remain valid
once the engine returns polars frames instead of pandas.
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest

from bioseq_dl.core.interfaces.base import BaseAPIInterface
from tests._helpers import frame_columns, frame_row_count, frame_to_records, is_frame


class NestedRecordsInterface(BaseAPIInterface):
    """Offline interface returning records with a nested list field.

    Exercises the engine's handling of irregular/nested columns (the main
    Polars-migration risk) without a network. Each id ``x`` yields
    ``{"id": x, "value": "val<x>", "tags": [x, "t"]}``.
    """

    API_NAME = "Nested"
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
        self.fetch_count = 0

    def fetch(self, query, *, method="get", **kwargs):
        self.fetch_count += 1
        raw = query["id"] if isinstance(query, dict) else query
        ids = raw.split(",") if isinstance(raw, str) else list(raw)
        return [{"id": x, "value": f"val{x}", "tags": [x, "t"]} for x in ids]

    def parse(self, data, fields_to_extract, **kwargs):
        return data


@pytest.fixture
def iface(tmp_path):
    return NestedRecordsInterface(cache_dir=str(tmp_path))


# --- _maybe_parse: format conversion content --------------------------------


def test_maybe_parse_list_to_dataframe_content(iface):
    out = iface._maybe_parse([{"a": 1}, {"a": 2}], parse=False, fmt="dataframe")
    assert is_frame(out)
    assert frame_to_records(out) == [{"a": 1}, {"a": 2}]


def test_maybe_parse_dict_to_single_row(iface):
    out = iface._maybe_parse({"a": 1, "b": "x"}, parse=False, fmt="dataframe")
    assert frame_to_records(out) == [{"a": 1, "b": "x"}]


def test_maybe_parse_empty_to_empty_frame(iface):
    out = iface._maybe_parse([], parse=False, fmt="dataframe")
    assert is_frame(out)
    assert frame_row_count(out) == 0


def test_maybe_parse_json_passthrough(iface):
    payload = [{"a": 1}, {"a": 2}]
    assert iface._maybe_parse(payload, parse=False, fmt="json") == payload


def test_maybe_parse_xml_bytes(iface):
    out = iface._maybe_parse({"a": "x"}, parse=False, fmt="xml")
    assert isinstance(out, bytes)
    assert b"<a>x</a>" in out


# --- _build_data_info: metadata contract (backend-independent) --------------


def test_build_data_info_from_list(iface):
    info = iface._build_data_info([{"a": 1, "b": None}, {"a": 2, "b": 5}])
    assert info["total_entries"] == 2
    assert info["data_type"] == "list"
    names = {c["name"]: c for c in info["columns"]}
    assert set(names) == {"a", "b"}
    # n_missing counts nulls per column; "b" has one missing value.
    assert names["b"]["n_missing"] == 1
    assert names["a"]["n_missing"] == 0
    # dtype is reported as a string (its exact value is backend-specific).
    assert all(isinstance(c["dtype"], str) for c in info["columns"])


def test_build_data_info_empty(iface):
    info = iface._build_data_info([])
    assert info["total_entries"] == 0
    assert info["columns"] == []


# --- fetch_single / fetch_batch content + cache round-trip ------------------


def test_fetch_single_json_content(iface):
    data, meta = iface.fetch_single("A", method="get", format="json")
    assert data == [{"id": "A", "value": "valA", "tags": ["A", "t"]}]
    assert meta["data_info"]["total_entries"] == 1


def test_fetch_single_dataframe_content(iface):
    data, _ = iface.fetch_single("A", method="get", format="dataframe")
    assert is_frame(data)
    records = frame_to_records(data)
    assert records == [{"id": "A", "value": "valA", "tags": ["A", "t"]}]


def test_fetch_single_cache_roundtrip_identical(iface):
    first, _ = iface.fetch_single("A", method="get", format="dataframe")
    assert iface.fetch_count == 1
    second, _ = iface.fetch_single("A", method="get", format="dataframe")
    # Second call served from cache: no extra fetch, identical content.
    assert iface.fetch_count == 1
    assert frame_to_records(first) == frame_to_records(second)


def test_fetch_single_nested_field_survives_cache(iface):
    iface.fetch_single("A", method="get", format="dataframe")  # populate cache
    cached, _ = iface.fetch_single("A", method="get", format="json")
    # The nested list field round-trips through the JSON cache unchanged.
    assert cached[0]["tags"] == ["A", "t"]


def test_fetch_batch_uncached_drops_dataframe_format(iface):
    # CHARACTERIZATION OF A KNOWN QUIRK: fetch_batch pops ``format`` before
    # delegating to fetch_single, so for freshly-fetched (uncached) queries the
    # requested "dataframe" format is NOT applied — each query comes back as its
    # raw JSON list and the result is a list-of-lists, not a concatenated frame.
    # Pinned so the migration surfaces (rather than silently alters) this.
    data, meta = iface.fetch_batch(["A", "B"], method="get", format="dataframe")
    assert not is_frame(data)
    assert data == [
        [{"id": "A", "value": "valA", "tags": ["A", "t"]}],
        [{"id": "B", "value": "valB", "tags": ["B", "t"]}],
    ]
    assert meta["data_info"]["total_entries"] == 2


def test_fetch_batch_cached_path_builds_frame(iface):
    # Populate the cache for each id, then batch-fetch: the cached branch DOES
    # honour the dataframe format (it calls _maybe_parse with fmt), and the
    # per-query frames are concatenated into one.
    iface.fetch_single("A", method="get", format="dataframe")
    iface.fetch_single("B", method="get", format="dataframe")
    data, meta = iface.fetch_batch(["A", "B"], method="get", format="dataframe")
    assert is_frame(data)
    records = frame_to_records(data)
    assert sorted(r["id"] for r in records) == ["A", "B"]
    assert set(frame_columns(data)) == {"id", "value", "tags"}
    assert meta["data_info"]["total_entries"] == 2
