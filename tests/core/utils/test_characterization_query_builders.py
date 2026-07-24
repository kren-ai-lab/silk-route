"""Tests for query builders.

Query builders consume one DataFrame row (a ``{column: value}`` dict) and return
API query params. Covers ``to_str_list`` value normalization (None / scalar /
list / JSON-string) and the per-builder output for representative cases.
"""

from __future__ import annotations

import pytest

from silkroute.core.utils.query_builders import (
    build_query_brenda,
    build_query_chebi_compounds,
    build_query_pubchem_compound_summary,
    to_str_list,
)


def row(values: dict) -> dict:
    """Build a builder input row from a dict of column values."""
    return values


# --- to_str_list: value normalization ---------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, []),
        (float("nan"), []),
        ("", []),
        ("  P12345  ", ["P12345"]),
        (["a", " b ", ""], ["a", "b"]),
        (("a", "b"), ["a", "b"]),
        ("['x', 'y']", ["x", "y"]),  # JSON/py-literal list string
        ("[]", []),
        (123, ["123"]),
    ],
)
def test_to_str_list_normalization(value, expected):
    assert to_str_list(value) == expected


# --- representative builders ------------------------------------------------


def test_brenda_filters_invalid_ec_numbers():
    # Only well-formed 4-part numeric EC numbers survive.
    r = row({"ec": ["1.1.1.1", "2.7.11", "not.an.ec.x"]})
    assert build_query_brenda(r, {}) == [{"ecNumber": "1.1.1.1"}]


def test_brenda_empty_when_no_valid_ec():
    assert build_query_brenda(row({"ec": None}), {}) == []


def test_chebi_compounds_groups_ids_by_five():
    r = row({"chebi_ids": [str(i) for i in range(7)]})
    out = build_query_chebi_compounds(r, {})
    assert len(out) == 2
    assert out[0]["chebi_ids"] == ["0", "1", "2", "3", "4"]
    assert out[1]["chebi_ids"] == ["5", "6"]


def test_pubchem_compound_summary_requires_both_fields():
    # Missing organism_id (None) -> the missing-value guard yields no queries.
    assert build_query_pubchem_compound_summary(row({"gene_primary": "TP53", "organism_id": None}), {}) == []


def test_pubchem_compound_summary_builds_query():
    out = build_query_pubchem_compound_summary(row({"gene_primary": "TP53", "organism_id": 9606}), {})
    assert out == [{"genesymbol": "TP53", "taxid": "9606"}]
