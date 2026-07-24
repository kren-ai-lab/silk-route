"""Offline tests for the pure helpers in main_workflow (no network, no mocks).

Covers page-cap normalization, the defensive ChEMBL activity filter, activity
filter metadata shaping, elapsed-time math and the small result-merge helpers.
"""

from __future__ import annotations

import polars as pl
import pytest

from silkroute.core.workflow.main_workflow import (
    _apply_label,
    _elapsed_seconds,
    activity_filter_metadata,
    calculate_enrichment_execution_time,
    filter_chembl_activity_dataframe,
    filter_chembl_activity_result,
    merge_into_dict,
    normalize_chembl_pages_to_fetch,
)

# --- normalize_chembl_pages_to_fetch ---------------------------------------


@pytest.mark.parametrize(("value", "expected"), [(None, -1), (5, 5), (-1, -1), ("3", 3)])
def test_normalize_pages_valid(value, expected):
    assert normalize_chembl_pages_to_fetch(value) == expected


@pytest.mark.parametrize("value", [0, -2, "x"])
def test_normalize_pages_value_error(value):
    with pytest.raises(ValueError, match="chembl_pages_to_fetch"):
        normalize_chembl_pages_to_fetch(value)


@pytest.mark.parametrize("value", [True, False])
def test_normalize_pages_bool_is_type_error(value):
    # bool is an int subclass but is explicitly rejected.
    with pytest.raises(TypeError, match="chembl_pages_to_fetch"):
        normalize_chembl_pages_to_fetch(value)


# --- filter_chembl_activity_dataframe --------------------------------------


@pytest.fixture
def activity_df():
    return pl.DataFrame(
        [
            {"standard_type": "IC50", "standard_value": 50},
            {"standard_type": "IC50", "standard_value": 5000},
            {"standard_type": "Ki", "standard_value": 10},
        ]
    )


def test_filter_exact_value(activity_df):
    filtered, meta = filter_chembl_activity_dataframe(
        activity_df, {"standard_type": "IC50", "standard_value": 50}
    )
    assert filtered["standard_value"].to_list() == [50]
    assert meta["filtered_rows"] == 1


def test_filter_min_exclusive(activity_df):
    filtered, _ = filter_chembl_activity_dataframe(
        activity_df, {"standard_type": "IC50", "standard_value_min": 100}
    )
    assert filtered["standard_value"].to_list() == [5000]


def test_filter_min_inclusive(activity_df):
    filtered, _ = filter_chembl_activity_dataframe(
        activity_df,
        {"standard_type": "IC50", "standard_value_min": 50, "standard_value_min_inclusive": True},
    )
    assert filtered["standard_value"].to_list() == [50, 5000]


def test_filter_max_exclusive(activity_df):
    filtered, meta = filter_chembl_activity_dataframe(
        activity_df, {"standard_type": "IC50", "standard_value_max": 100}
    )
    assert filtered["standard_value"].to_list() == [50]
    assert meta["removed_rows"] == 2


def test_filter_type_is_case_insensitive(activity_df):
    filtered, _ = filter_chembl_activity_dataframe(
        activity_df, {"standard_type": "ic50", "standard_value": 50}
    )
    assert filtered["standard_value"].to_list() == [50]


def test_filter_empty_dataframe():
    filtered, meta = filter_chembl_activity_dataframe(pl.DataFrame(), {"standard_type": "IC50"})
    assert filtered.is_empty()
    assert meta == {"applied": True, "initial_rows": 0, "filtered_rows": 0, "removed_rows": 0}


def test_filter_missing_columns_drops_everything():
    filtered, meta = filter_chembl_activity_dataframe(pl.DataFrame([{"a": 1}]), {"standard_type": "IC50"})
    assert filtered.is_empty()
    assert meta["reason"] == "missing_standard_type_or_standard_value"
    assert meta["removed_rows"] == 1


# --- filter_chembl_activity_result (shape dispatch) ------------------------


def test_filter_result_no_filter_passes_through():
    assert filter_chembl_activity_result([1, 2], None) == ([1, 2], {"applied": False})


def test_filter_result_list_returns_records():
    out, meta = filter_chembl_activity_result(
        [{"standard_type": "IC50", "standard_value": 50}], {"standard_type": "IC50", "standard_value": 50}
    )
    assert out == [{"standard_type": "IC50", "standard_value": 50}]
    assert meta["filtered_rows"] == 1


def test_filter_result_dict_match_returns_dict():
    out, _ = filter_chembl_activity_result(
        {"standard_type": "IC50", "standard_value": 50}, {"standard_type": "IC50", "standard_value": 50}
    )
    assert out == {"standard_type": "IC50", "standard_value": 50}


def test_filter_result_dict_no_match_returns_empty():
    out, _ = filter_chembl_activity_result(
        {"standard_type": "IC50", "standard_value": 9}, {"standard_type": "IC50", "standard_value": 50}
    )
    assert out == {}


def test_filter_result_unsupported_type():
    out, meta = filter_chembl_activity_result(42, {"standard_type": "IC50"})
    assert out == 42
    assert meta == {"applied": False, "reason": "unsupported_result_type:int"}


# --- activity_filter_metadata ----------------------------------------------


def test_activity_filter_metadata_omits_absent_standard_value():
    meta = activity_filter_metadata({"standard_type": "IC50"})
    assert "standard_value" not in meta
    assert meta["standard_type"] == "IC50"


def test_activity_filter_metadata_includes_present_standard_value():
    assert activity_filter_metadata({"standard_type": "IC50", "standard_value": 5})["standard_value"] == 5


# --- elapsed-time math -----------------------------------------------------


def test_elapsed_seconds_valid_pair():
    assert _elapsed_seconds("2026-06-23T10:00:00", "2026-06-23T10:00:05") == 5.0


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (None, "2026-06-23T10:00:05"),  # missing start
        ("not-iso", "2026-06-23T10:00:05"),  # invalid format
        ("2026-06-23T10:00:05", "2026-06-23T10:00:00"),  # negative -> clamped to 0
    ],
)
def test_elapsed_seconds_degrades_to_zero(start, end):
    assert _elapsed_seconds(start, end) == 0.0


def test_calculate_enrichment_execution_time_sums_endpoints():
    total = calculate_enrichment_execution_time(
        {
            "a": {"started_at": "2026-06-23T10:00:00", "finished_at": "2026-06-23T10:00:02"},
            "b": {"started_at": "2026-06-23T10:00:00", "finished_at": "2026-06-23T10:00:03"},
        }
    )
    assert total == 5.0


def test_calculate_enrichment_execution_time_non_dict_is_zero():
    assert calculate_enrichment_execution_time("nope") == 0.0


# --- merge helpers ---------------------------------------------------------


def test_merge_into_dict_inserts_new_key():
    target = {}
    merge_into_dict(target, "x", [1])
    assert target == {"x": [1]}


def test_merge_into_dict_merges_existing_key():
    target = {"x": [1]}
    merge_into_dict(target, "x", [2])
    assert target == {"x": [1, 2]}


# --- _apply_label ----------------------------------------------------------


def test_apply_label_scalar_becomes_label_dict():
    assert _apply_label(42, "L1") == {"_label": "L1"}


def test_apply_label_list_of_dicts_setdefault():
    rows = [{"a": 1}, {"a": 2, "_label": "keep"}]
    out = _apply_label(rows, "L1")
    assert out[0]["_label"] == "L1"
    assert out[1]["_label"] == "keep"  # existing label preserved


def test_apply_label_dataframe_preserves_existing_as_original():
    df = pl.DataFrame({"a": [1], "_label": ["old"]})
    out = _apply_label(df, "new")
    assert out["_label"].to_list() == ["new"]
    assert out["_label_original"].to_list() == ["old"]
