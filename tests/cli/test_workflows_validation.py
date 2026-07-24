"""Offline tests for the pure validation/transform helpers in cli/workflows.

No network, no Typer invocation, no MainWorkflow — these cover the descriptor
validation pipeline, merge logic, export shaping, and the query-composition
label parsing that decides what users see when a workflow runs.
"""

from __future__ import annotations

import datetime as dt

import polars as pl
import pytest

from silkroute.cli.workflows import (
    add_id_column_for_export,
    build_default_workflow_values,
    check_forbidden_workflow_recipe_keys,
    count_query_composition_labels,
    determine_execution_status,
    get_expected_query_composition_labels,
    is_count_like_reporting_map,
    is_empty_export_content,
    is_reporting_value_allowed,
    is_valid_export_label,
    merge_workflow_recipe,
    normalize_optional_field_list,
    require_mapping,
    split_pair,
    to_json_compatible,
    validate_allowed_section_keys,
    validate_bool,
    validate_dataset_section,
    validate_descriptor_section_names,
    validate_int,
    validate_merged_workflow_values,
    validate_numeric_or_null,
    validate_pages_to_fetch,
    validate_query_section,
    validate_required_section_keys,
    validate_string_list,
)

# --- credential guard -------------------------------------------------------


def test_forbidden_keys_rejected_at_top_level():
    with pytest.raises(ValueError, match="Credentials must be provided"):
        check_forbidden_workflow_recipe_keys({"api_key": "x"})


def test_forbidden_keys_rejected_when_nested():
    with pytest.raises(ValueError, match="Credentials must be provided"):
        check_forbidden_workflow_recipe_keys({"execution": [{"password": "x"}]})


def test_forbidden_keys_case_insensitive():
    with pytest.raises(ValueError, match="Credentials must be provided"):
        check_forbidden_workflow_recipe_keys({"TOKEN": "x"})


def test_clean_descriptor_passes_credential_guard():
    check_forbidden_workflow_recipe_keys({"dataset": {"name": "demo"}, "query": {"value": "P12345"}})


# --- require_mapping --------------------------------------------------------


def test_require_mapping_coerces_keys_to_strings():
    assert require_mapping("dataset", {1: "a"}) == {"1": "a"}


def test_require_mapping_rejects_non_dict():
    with pytest.raises(TypeError, match="must be a mapping"):
        require_mapping("dataset", ["not", "a", "map"])


# --- section name / key validators ------------------------------------------


def test_descriptor_section_names_reject_old_mode_key():
    with pytest.raises(ValueError, match=r"dataset\.mode instead"):
        validate_descriptor_section_names({"dispatch_mode": "x"})


def test_descriptor_section_names_reject_old_root_key():
    with pytest.raises(ValueError, match="structured dataset/query"):
        validate_descriptor_section_names({"kind": 1})


def test_descriptor_section_names_reject_unknown():
    with pytest.raises(ValueError, match="Unknown workflow YAML section 'bogus'"):
        validate_descriptor_section_names({"bogus": {}})


def test_descriptor_section_names_accept_known():
    validate_descriptor_section_names({"dataset": {}, "query": {}, "reporting": {}})


def test_allowed_section_keys_rejects_unknown():
    with pytest.raises(ValueError, match="Unknown dataset YAML key 'oops'"):
        validate_allowed_section_keys("dataset", {"oops": 1}, {"name"})


def test_allowed_section_keys_special_error_wins():
    with pytest.raises(ValueError, match="deprecated"):
        validate_allowed_section_keys("query", {"type": 1}, {"value"}, special_errors={"type": "deprecated"})


def test_required_section_keys_reports_missing_and_null():
    with pytest.raises(ValueError, match="missing required key\\(s\\): modality, mode"):
        validate_required_section_keys("dataset", {"modality": None}, {"modality", "mode"})


# --- scalar type validators -------------------------------------------------


@pytest.mark.parametrize("value", [1, "x", None])
def test_validate_bool_rejects_non_bool(value):
    with pytest.raises(TypeError, match="must be a boolean"):
        validate_bool("execution", "enrich", value)


def test_validate_bool_accepts_bool():
    validate_bool("execution", "enrich", True)


@pytest.mark.parametrize("value", [True, 1.5, "3", None])
def test_validate_int_rejects_non_int_and_bool(value):
    with pytest.raises(TypeError, match="must be an integer"):
        validate_int("execution", "max_workers", value)


@pytest.mark.parametrize("value", [True, "x"])
def test_validate_numeric_or_null_rejects_bool_and_string(value):
    with pytest.raises(ValueError, match="must be numeric or null"):
        validate_numeric_or_null("execution", "uniprot_timeout", value)


@pytest.mark.parametrize("value", [None, 1, 2.5])
def test_validate_numeric_or_null_accepts_numbers_and_null(value):
    validate_numeric_or_null("execution", "uniprot_timeout", value)


@pytest.mark.parametrize("value", [0, -2])
def test_validate_pages_to_fetch_rejects_zero_and_below_minus_one(value):
    with pytest.raises(ValueError, match="must be -1 or a positive integer"):
        validate_pages_to_fetch("execution", "chembl_pages_to_fetch", value)


@pytest.mark.parametrize("value", [-1, 1, 50])
def test_validate_pages_to_fetch_accepts_minus_one_and_positive(value):
    validate_pages_to_fetch("execution", "chembl_pages_to_fetch", value)


def test_validate_string_list_rejects_mixed():
    with pytest.raises(ValueError, match="must be a list of strings"):
        validate_string_list("resources", "primary", ["uniprot", 3])


# --- normalize_optional_field_list ------------------------------------------


def test_normalize_field_list_none_returns_none():
    assert normalize_optional_field_list("query", "fields", None) is None


def test_normalize_field_list_passthrough_string():
    assert normalize_optional_field_list("query", "fields", "a,b") == "a,b"


def test_normalize_field_list_joins_and_strips_list():
    assert normalize_optional_field_list("query", "fields", [" a ", "", "b"]) == "a,b"


def test_normalize_field_list_all_blank_becomes_none():
    assert normalize_optional_field_list("query", "fields", ["", "  "]) is None


def test_normalize_field_list_rejects_bad_type():
    with pytest.raises(ValueError, match="null, a string, or a list of strings"):
        normalize_optional_field_list("query", "fields", 42)


# --- reporting value safety -------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [None, "x", 1, 2.5, True, dt.date(2026, 6, 26), [1, "a"], {"k": [1, 2]}],
)
def test_reporting_value_allowed(value):
    assert is_reporting_value_allowed(value) is True


@pytest.mark.parametrize("value", [object(), {1: "non-string-key"}, [object()]])
def test_reporting_value_disallowed(value):
    assert is_reporting_value_allowed(value) is False


def test_is_count_like_reporting_map():
    assert is_count_like_reporting_map({"a": 1, "b": None}) is True
    assert is_count_like_reporting_map({"a": True}) is False  # bool rejected
    assert is_count_like_reporting_map({}) is False


# --- dataset / query section round-trip -------------------------------------


def test_validate_dataset_section_ok_with_output_dir():
    out = validate_dataset_section(
        {"modality": "protein", "mode": "query_first"}, export_section={"output_dir": "out_dir"}
    )
    assert out["modality"] == "protein"


def test_validate_dataset_section_requires_name_without_output_dir():
    with pytest.raises(ValueError, match=r"dataset\.name is required"):
        validate_dataset_section({"modality": "protein", "mode": "query_first"}, export_section={})


def test_validate_dataset_section_rejects_bad_modality():
    with pytest.raises(ValueError, match=r"Unsupported dataset\.modality"):
        validate_dataset_section({"modality": "rna", "mode": "query_first", "name": "d"}, export_section={})


def test_validate_query_section_returns_normalized_fields():
    section, fields, crossref = validate_query_section(
        {"value": "P12345", "fields": [" accession ", "sequence"], "crossref_fields": "kegg"}
    )
    assert section["value"] == "P12345"
    assert fields == "accession,sequence"
    assert crossref == "kegg"


def test_validate_query_section_rejects_blank_value():
    with pytest.raises(ValueError, match="must be a non-empty string"):
        validate_query_section({"value": "   "})


# --- merge + merged validation ----------------------------------------------


def test_merge_recipe_cli_overrides_recipe_and_defaults():
    cli = {"query": "CLI_QUERY", "modality": None}  # None is ignored
    recipe = {"query": "RECIPE_QUERY", "modality": "protein", "mode": "query_first"}
    merged = merge_workflow_recipe(cli, recipe)
    assert merged["query"] == "CLI_QUERY"  # explicit CLI wins
    assert merged["modality"] == "protein"  # None CLI -> recipe value kept
    assert merged["workers"] == 5  # untouched default


def test_validate_merged_values_reports_missing():
    values = build_default_workflow_values()
    with pytest.raises(ValueError, match="Missing required workflow value"):
        validate_merged_workflow_values(values)


def test_validate_merged_values_normalizes_export_format_in_place():
    values = build_default_workflow_values()
    values.update({"output": "out_dir", "query": "P1", "modality": "protein", "mode": "query_first"})
    values["export_format"] = "CSV"
    validate_merged_workflow_values(values)
    assert values["export_format"] == "csv"


def test_validate_merged_values_rejects_bad_format():
    values = build_default_workflow_values()
    values.update(
        {
            "output": "out_dir",
            "query": "P1",
            "modality": "protein",
            "mode": "query_first",
            "export_format": "xlsx",
        }
    )
    with pytest.raises(ValueError, match="Unsupported export format"):
        validate_merged_workflow_values(values)


# --- export helpers ---------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "expected"),
    [("uniprot", True), ("", False), (None, False), ("none", False), ("NULL", False)],
)
def test_is_valid_export_label(label, expected):
    assert is_valid_export_label(label) is expected


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (None, True),
        (pl.DataFrame(), True),
        (pl.DataFrame({"a": [1]}), False),
        ("  ", True),
        ([], True),
        ([1], False),
        ({}, True),
    ],
)
def test_is_empty_export_content(content, expected):
    assert is_empty_export_content(content) is expected


def test_add_id_column_inserts_when_requested():
    df = pl.DataFrame({"a": [10, 20]})
    out = add_id_column_for_export(df, "uniprot", "id")
    assert out["id"].to_list() == ["uniprot_1", "uniprot_2"]
    assert "id" not in df.columns  # original untouched


def test_add_id_column_skips_when_no_column_or_already_present():
    df = pl.DataFrame({"id": [1], "a": [2]})
    assert add_id_column_for_export(df, "x", None) is df
    assert add_id_column_for_export(df, "x", "id") is df


def test_to_json_compatible_handles_frames_dates_paths():
    from pathlib import Path

    path = Path("/data/x")
    value = {
        "df": pl.DataFrame({"a": [1]}),
        "when": dt.date(2026, 6, 26),
        "path": path,
        "series": pl.Series([1, 2]),
    }
    out = to_json_compatible(value)
    assert out["df"] == [{"a": 1}]
    assert out["when"] == "2026-06-26"
    assert out["path"] == str(path)
    assert out["series"] == [1, 2]


def test_to_json_compatible_nan_becomes_none():
    assert to_json_compatible(float("nan")) is None


# --- query-composition label parsing ----------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [("q=label", ("q", "label")), ("q|label", ("q", "label")), (" q = l ", ("q", "l"))],
)
def test_split_pair_valid(text, expected):
    assert split_pair(text) == expected


def test_split_pair_invalid():
    with pytest.raises(ValueError, match="Use 'query=label'"):
        split_pair("noseparator")


def test_expected_labels_in_order_without_duplicates():
    values = {"query": "P1=human, P2=mouse, P3=human"}
    assert get_expected_query_composition_labels(values) == ["human", "mouse"]


def test_expected_labels_skips_unsplittable_parts():
    values = {"query": "P1=human, broken, P2=mouse"}
    assert get_expected_query_composition_labels(values) == ["human", "mouse"]


def test_expected_labels_non_string_query():
    assert get_expected_query_composition_labels({"query": None}) == []


def test_count_query_composition_labels_counts_label_column():
    df = pl.DataFrame({"acc": ["a", "b", "c"], "_label": ["human", "mouse", "human"]})
    values = {"mode": "query_composition", "modality": "protein", "query": "x=human, y=mouse"}
    output_infos = [{"category": "result", "label": "uniprot", "column_names": ["_label"]}]
    counts = count_query_composition_labels(values, {"uniprot": df}, output_infos)
    assert counts == {"human": 2, "mouse": 1}


def test_count_query_composition_labels_not_applicable_in_query_first():
    values = {"mode": "query_first", "modality": "protein"}
    assert count_query_composition_labels(values, {"uniprot": pl.DataFrame()}, []) == {}


# --- execution status -------------------------------------------------------


def test_status_success_when_no_errors():
    status, msg = determine_execution_status({"fetch": {"ok": True}}, [{"category": "result"}])
    assert (status, msg) == ("success", None)


def test_status_failed_when_fetch_error_and_no_output():
    meta = {"fetch": {"error": "boom"}}
    status, msg = determine_execution_status(meta, [])
    assert status == "failed"
    assert msg == "boom"


def test_status_completed_with_errors_when_output_exists():
    meta = {"uniprot_enrichment": {"error": "partial"}}
    status, msg = determine_execution_status(meta, [{"category": "result"}])
    assert status == "completed_with_errors"
    assert msg == "partial"
