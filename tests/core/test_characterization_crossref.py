"""Tests for CrossRefEnricher frame handling.

The enricher builds DataFrames from irregular API results (rows with differing
keys, accidental numeric column names, nested values) and concatenates them.
Covers:

- ``_clean_frame`` coercion of raw row results,
- ``_process_dataframe`` aggregation/concat across rows with differing schemas.
"""

from __future__ import annotations

from typing import cast

import polars as pl

from silkroute.core.crossref_enricher import CrossRefEnricher, EndpointSpec
from silkroute.core.metadata import FetchMetadata
from tests._helpers import frame_to_records

# --- _clean_frame: coercing raw per-row results -----------------------------


def test_clean_frame_list_of_dicts():
    out = CrossRefEnricher._clean_frame([{"a": 1}, {"a": 2}])
    assert frame_to_records(out) == [{"a": 1}, {"a": 2}]


def test_clean_frame_single_dict_to_one_row():
    out = CrossRefEnricher._clean_frame({"a": 1, "b": "x"})
    assert frame_to_records(out) == [{"a": 1, "b": "x"}]


def test_clean_frame_empty_returns_none():
    assert CrossRefEnricher._clean_frame([]) is None
    assert CrossRefEnricher._clean_frame({}) is None
    assert CrossRefEnricher._clean_frame("unsupported") is None


def test_clean_frame_drops_numeric_named_columns():
    # Columns whose name is all digits ('0','1',...) are dropped as accidental.
    out = CrossRefEnricher._clean_frame([{"id": "P1", "0": "junk", "1": "junk2"}])
    assert frame_to_records(out) == [{"id": "P1"}]


def test_clean_frame_all_numeric_named_columns_returns_none():
    assert CrossRefEnricher._clean_frame([{"0": "a", "1": "b"}]) is None


# --- _process_dataframe: aggregation across rows ----------------------------


def test_process_dataframe_concats_differing_schemas(monkeypatch):
    # Each input row yields a result with a different column set; the aggregate
    # is the column union, missing cells filled with null (None after norm).
    enricher = CrossRefEnricher()

    def fake_search_and_merge(row, instance, spec, params, fmt):
        if row["id"] == "P1":
            return [{"a": 1}], FetchMetadata().to_dict()
        return [{"b": 2}], FetchMetadata().to_dict()

    monkeypatch.setattr(enricher, "_search_and_merge", fake_search_and_merge)

    df = pl.DataFrame({"id": ["P1", "P2"]})
    data, _ = enricher._process_dataframe(
        df, instance=None, spec=cast("EndpointSpec", None), params={}, fmt="dataframe"
    )
    records = frame_to_records(data)
    assert records == [{"a": 1, "b": None}, {"a": None, "b": 2}]


def test_process_dataframe_empty_results_returns_empty_frame(monkeypatch):
    enricher = CrossRefEnricher()

    def fake_search_and_merge(row, instance, spec, params, fmt):
        return [], FetchMetadata().to_dict()

    monkeypatch.setattr(enricher, "_search_and_merge", fake_search_and_merge)

    df = pl.DataFrame({"id": ["P1", "P2"]})
    data, _ = enricher._process_dataframe(
        df, instance=None, spec=cast("EndpointSpec", None), params={}, fmt="dataframe"
    )
    assert frame_to_records(data) == []


def test_process_dataframe_json_flattens_results(monkeypatch):
    enricher = CrossRefEnricher()

    def fake_search_and_merge(row, instance, spec, params, fmt):
        return [{"id": row["id"], "v": 1}], FetchMetadata().to_dict()

    monkeypatch.setattr(enricher, "_search_and_merge", fake_search_and_merge)

    df = pl.DataFrame({"id": ["P1", "P2"]})
    data, _ = enricher._process_dataframe(
        df, instance=None, spec=cast("EndpointSpec", None), params={}, fmt="json"
    )
    assert data == [{"id": "P1", "v": 1}, {"id": "P2", "v": 1}]
