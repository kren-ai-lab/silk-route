"""Characterization tests for query builders (pre-Polars migration).

Query builders consume one DataFrame row and return API query params. Today the
row arrives as a ``pandas.Series``; after the migration it will be a plain dict
from ``DataFrame.iter_rows(named=True)``. Both support ``.get()`` / ``[]`` /
``pd.isna``, so these golden tests feed plain dict rows (a valid stand-in for
both) and pin the value-normalization and per-builder output that must survive.

``to_str_list`` is the shared normalizer most at risk: it special-cases pandas
NaN and numpy arrays today; the migration must keep its observable output for
the None / scalar / list / JSON-string cases pinned here.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from bioseq_dl.core.utils.query_builders import (
    build_query_brenda,
    build_query_chebi_compounds,
    build_query_pubchem_compound_summary,
    to_str_list,
)


def row(values: dict) -> pd.Series:
    """Build a builder input row. Single migration touch-point (Series -> dict)."""
    return pd.Series(values)


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


def test_to_str_list_numpy_array():
    assert to_str_list(np.array(["a", "b"])) == ["a", "b"]


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
    # Missing organism_id (None) -> the pd.isna guard yields no queries.
    assert build_query_pubchem_compound_summary(row({"gene_primary": "TP53", "organism_id": None}), {}) == []


def test_pubchem_compound_summary_builds_query():
    out = build_query_pubchem_compound_summary(row({"gene_primary": "TP53", "organism_id": 9606}), {})
    assert out == [{"genesymbol": "TP53", "taxid": "9606"}]
