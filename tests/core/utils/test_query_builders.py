"""Unit tests for cross-reference query builders."""

from __future__ import annotations

import numpy as np
import pytest

from bioseq_dl.core.utils.query_builders import (
    QUERY_BUILDERS,
    get_query_builder,
    to_str_list,
)


def test_to_str_list_handles_missing():
    assert to_str_list(None) == []
    assert to_str_list(float("nan")) == []
    assert to_str_list("") == []


def test_to_str_list_parses_literal_list_string():
    assert to_str_list("['a', 'b']") == ["a", "b"]


def test_to_str_list_list_and_ndarray():
    assert to_str_list(["a", " b ", ""]) == ["a", "b"]
    assert to_str_list(np.array(["x", "y"])) == ["x", "y"]


def test_get_query_builder_unknown_raises():
    with pytest.raises(ValueError, match="No query builder"):
        get_query_builder("nope", "nope")


def test_build_query_rhea():
    builder = get_query_builder("rhea", "rhea")
    out = builder({"rhea_ids": ["RHEA:1", "RHEA:2"]}, {})  # ty: ignore[invalid-argument-type]  # dict duck-types pd.Series
    assert out == [{"query": "RHEA:1"}, {"query": "RHEA:2"}]


def test_build_query_rhea_empty_when_missing():
    builder = get_query_builder("rhea", "rhea")
    assert builder({"other": "x"}, {}) == []  # ty: ignore[invalid-argument-type]  # dict duck-types pd.Series


def test_build_query_biodbnet_db2db_merges_params():
    builder = get_query_builder("biodbnet", "db2db")
    out = builder({"gene_primary": ["TP53"], "organism_id": ["9606"]}, {"outputs": "genesymbol"})  # ty: ignore[invalid-argument-type]  # dict duck-types pd.Series
    assert out == [{"inputValues": ["TP53"], "taxonId": "9606", "outputs": "genesymbol"}]


def test_build_query_brenda_filters_invalid_ec():
    builder = get_query_builder("brenda", "getKmValue")
    out = builder({"ec": ["1.1.1.1", "not-an-ec", "2.7.1"]}, {})  # ty: ignore[invalid-argument-type]  # dict duck-types pd.Series
    assert out == [{"ecNumber": "1.1.1.1"}]


def test_chebi_compounds_chunks_in_groups_of_five():
    builder = get_query_builder("chebi", "compounds")
    ids = [str(i) for i in range(12)]
    out = builder({"chebi_ids": ids}, {})  # ty: ignore[invalid-argument-type]  # dict duck-types pd.Series
    assert len(out) == 3  # 5 + 5 + 2
    assert out[0]["chebi_ids"] == ids[:5]
    assert out[2]["chebi_ids"] == ids[10:]


def test_registry_is_populated():
    # Sanity: a representative set of builders is registered.
    for key in ("rhea_rhea", "biodbnet_db2db", "string_get_string_ids", "pubchem_compound_summary"):
        assert key in QUERY_BUILDERS
