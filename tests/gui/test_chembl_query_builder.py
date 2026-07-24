"""Tests for pure ChEMBL query builder utilities."""

from __future__ import annotations

import subprocess
import sys

import pytest

from silkroute.gui.query_builders.chembl import (
    ChEMBLFilterQueryBuilderRow,
    build_chembl_interpreted_query,
)


def test_chembl_target_filters_build_interpreted_query():
    rows = [
        ChEMBLFilterQueryBuilderRow("target", "type", "iexact", "protein"),
        ChEMBLFilterQueryBuilderRow("target", "gene_symbol", "icontains", "EGFR"),
    ]

    assert (
        build_chembl_interpreted_query(rows)
        == "chembl.target:type__iexact=protein AND gene_symbol__icontains=EGFR"
    )


def test_chembl_molecule_filters_build_interpreted_query():
    rows = [
        ChEMBLFilterQueryBuilderRow("molecule", "name", "iexact", "Imatinib"),
        ChEMBLFilterQueryBuilderRow("molecule", "molecular_weight", "range", "80,200"),
    ]

    assert (
        build_chembl_interpreted_query(rows)
        == "chembl.molecule:name__iexact=Imatinib AND molecular_weight__range=80,200"
    )


def test_chembl_activity_filters_build_interpreted_query():
    rows = [
        ChEMBLFilterQueryBuilderRow("activity", "target_chembl_id", "exact", "CHEMBL5169197"),
        ChEMBLFilterQueryBuilderRow("activity", "pchembl_value", "exact", "5.83"),
    ]

    assert (
        build_chembl_interpreted_query(rows)
        == "chembl.activity:target_chembl_id=CHEMBL5169197 AND pchembl_value=5.83"
    )


def test_chembl_builder_rejects_invalid_resource():
    rows = [ChEMBLFilterQueryBuilderRow("unknown", "gene_symbol", "icontains", "EGFR")]

    with pytest.raises(ValueError, match="resource 'unknown' is not supported"):
        build_chembl_interpreted_query(rows)


def test_chembl_builder_rejects_invalid_field():
    rows = [ChEMBLFilterQueryBuilderRow("target", "unknown", "icontains", "EGFR")]

    with pytest.raises(ValueError, match="field 'unknown' is not supported"):
        build_chembl_interpreted_query(rows)


def test_chembl_builder_rejects_invalid_operator():
    rows = [ChEMBLFilterQueryBuilderRow("target", "gene_symbol", "range", "EGFR")]

    with pytest.raises(ValueError, match="operator 'range' is not allowed"):
        build_chembl_interpreted_query(rows)


def test_chembl_builder_rejects_empty_value():
    rows = [ChEMBLFilterQueryBuilderRow("target", "gene_symbol", "icontains", "")]

    with pytest.raises(ValueError, match="value is required"):
        build_chembl_interpreted_query(rows)


def test_chembl_builder_rejects_range_with_one_value():
    rows = [ChEMBLFilterQueryBuilderRow("molecule", "molecular_weight", "range", "80")]

    with pytest.raises(ValueError, match="range requires exactly two"):
        build_chembl_interpreted_query(rows)


def test_chembl_builder_rejects_value_with_condition_separator():
    # ' AND ' in a value would mis-parse into extra conditions downstream.
    rows = [ChEMBLFilterQueryBuilderRow("molecule", "name", "icontains", "foo AND bar")]

    with pytest.raises(ValueError, match="value cannot contain ' AND '"):
        build_chembl_interpreted_query(rows)


def test_chembl_builder_import_does_not_import_nicegui():
    import_script = """
import sys
import silkroute.gui.query_builders.chembl

if "nicegui" in sys.modules:
    raise RuntimeError("Importing pure ChEMBL query builder utilities loaded NiceGUI.")
"""

    subprocess.run(  # noqa: S603
        [sys.executable, "-c", import_script],
        check=True,
        capture_output=True,
        text=True,
    )
