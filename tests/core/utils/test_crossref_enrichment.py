"""Offline tests for the cross-reference enrichment workflow utilities.

Covers field-name normalization, the empty-input / empty-result predicates, and
the early-return skip paths of ``run_crossref_enrichment`` that decide whether
enrichment runs at all. No network: the skip paths return before any interface
is built.
"""

from __future__ import annotations

import pandas as pd
import pytest

from bioseq_dl.core.utils.crossref_enrichment import (
    has_enrichment_result_value,
    is_empty_enrichment_input,
    normalize_crossref_fields,
    run_crossref_enrichment,
)

# --- normalize_crossref_fields ----------------------------------------------


def test_normalize_none_returns_empty():
    assert normalize_crossref_fields(None) == []


def test_normalize_comma_string_splits_and_strips():
    assert normalize_crossref_fields(" kegg , brenda ") == ["kegg", "brenda"]


def test_normalize_drops_blanks():
    assert normalize_crossref_fields("kegg,,  ,brenda") == ["kegg", "brenda"]


@pytest.mark.parametrize("container", [list, tuple, set])
def test_normalize_accepts_collections(container):
    assert sorted(normalize_crossref_fields(container(["kegg", "brenda"]))) == ["brenda", "kegg"]


def test_normalize_skips_non_string_entries():
    assert normalize_crossref_fields(["kegg", 3, None, "brenda"]) == ["kegg", "brenda"]


def test_normalize_unsupported_type_returns_empty():
    assert normalize_crossref_fields(42) == []


# --- is_empty_enrichment_input ----------------------------------------------


# One case per type branch (empty + non-empty for the container types that matter).
@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (None, True),
        (pd.DataFrame(), True),
        (pd.DataFrame({"a": [1]}), False),
        ([], True),
        ({"a": 1}, False),
        (b"", True),
        ("   ", True),
        (42, False),  # unknown type treated as non-empty
    ],
)
def test_is_empty_enrichment_input(data, expected):
    assert is_empty_enrichment_input(data) is expected


# --- has_enrichment_result_value --------------------------------------------


# One case per type branch.
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, False),
        (pd.DataFrame(), False),
        (pd.DataFrame({"a": [1]}), True),
        ("", False),
        (b"", False),
        ([1], True),
        ({}, False),
        (0, True),  # unknown scalar treated as data
    ],
)
def test_has_enrichment_result_value(value, expected):
    assert has_enrichment_result_value(value) is expected


# --- run_crossref_enrichment skip paths (no network) ------------------------


def test_run_skips_when_no_fields():
    data, meta = run_crossref_enrichment(pd.DataFrame({"a": [1]}), crossref_fields=[])
    assert data == {}
    assert meta == {"skipped": True, "reason": "no_crossref_fields"}


def test_run_skips_when_input_empty():
    data, meta = run_crossref_enrichment(pd.DataFrame(), crossref_fields=["kegg"])
    assert data == {}
    assert meta == {"skipped": True, "reason": "empty_input"}


def test_run_skips_when_no_endpoint_specs_resolved():
    # A database name absent from XREF_MAPPING resolves to no endpoint specs, so
    # enrichment is skipped before any interface/network is touched.
    data, meta = run_crossref_enrichment(pd.DataFrame({"a": [1]}), crossref_fields=["definitelynotadatabase"])
    assert data == {}
    assert meta == {"skipped": True, "reason": "no_endpoint_specs"}
