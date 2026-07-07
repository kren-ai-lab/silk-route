"""Tests for pure ChEMBL query builder utilities."""

from __future__ import annotations

import subprocess
import sys

import pytest

from bioseq_dl.core.workflow.query_interpreter import build_default_chembl_interpreter
from bioseq_dl.gui.query_builders.chembl import (
    ChEMBLFilterQueryBuilderRow,
    build_chembl_friendly_query,
    build_chembl_interpreted_query,
)
from bioseq_dl.gui.query_builders.chembl_ic50 import (
    ChEMBLIC50QueryBuilderRow,
    build_chembl_ic50_interpreted_query,
)
from bioseq_dl.gui.query_builders.metadata import (
    QUERY_BUILDER_SCHEMA_VERSION,
    build_chembl_ic50_query_builder_metadata,
    build_chembl_query_builder_metadata,
)


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        (ChEMBLIC50QueryBuilderRow("range", "0", "10", "", "nM"), "ic50:0-10 AND standard_units:nM"),
        (ChEMBLIC50QueryBuilderRow("range", "0", "10", "", ""), "ic50:0-10"),
        (
            ChEMBLIC50QueryBuilderRow("lt", value="1000", standard_units="nM"),
            "ic50:<1000 AND standard_units:nM",
        ),
        (
            ChEMBLIC50QueryBuilderRow("lte", value="1000", standard_units="nM"),
            "ic50:<=1000 AND standard_units:nM",
        ),
        (ChEMBLIC50QueryBuilderRow("gt", value="10", standard_units="uM"), "ic50:>10 AND standard_units:uM"),
        (
            ChEMBLIC50QueryBuilderRow("gte", value="10", standard_units="uM"),
            "ic50:>=10 AND standard_units:uM",
        ),
        (
            ChEMBLIC50QueryBuilderRow("exact", value="50", standard_units="nM"),
            "ic50:50 AND standard_units:nM",
        ),
        (ChEMBLIC50QueryBuilderRow("range", "0", "1", "", "µM"), "ic50:0-1 AND standard_units:uM"),
        (ChEMBLIC50QueryBuilderRow("range", "0", "1", "", "μM"), "ic50:0-1 AND standard_units:uM"),
    ],
)
def test_chembl_ic50_builder_generates_macro_queries(
    row: ChEMBLIC50QueryBuilderRow,
    expected: str,
) -> None:
    assert build_chembl_ic50_interpreted_query(row) == expected


@pytest.mark.parametrize(
    "row",
    [
        ChEMBLIC50QueryBuilderRow("range", "invalid", "10", "", "nM"),
        ChEMBLIC50QueryBuilderRow("exact", value="", standard_units="nM"),
    ],
)
def test_chembl_ic50_builder_rejects_invalid_numeric_values(
    row: ChEMBLIC50QueryBuilderRow,
) -> None:
    with pytest.raises(ValueError, match=r"IC50 .*value"):
        build_chembl_ic50_interpreted_query(row)


def test_chembl_ic50_builder_rejects_invalid_comparison_mode() -> None:
    with pytest.raises(ValueError, match="Unsupported IC50 comparison mode"):
        build_chembl_ic50_interpreted_query(ChEMBLIC50QueryBuilderRow("between", "0", "10", "", "nM"))


def test_chembl_ic50_builder_metadata_uses_one_stable_row() -> None:
    metadata = build_chembl_ic50_query_builder_metadata(
        ChEMBLIC50QueryBuilderRow("range", "0", "10", "", "nM")
    )

    assert metadata == {
        "schema_version": QUERY_BUILDER_SCHEMA_VERSION,
        "source": "chembl",
        "builder_key": "chembl_ic50_activity",
        "builder_type": "ic50_activity",
        "rows": [
            {
                "comparison_mode": "range",
                "lower_value": "0",
                "upper_value": "10",
                "value": "",
                "standard_units": "nM",
            }
        ],
    }


def test_generated_chembl_ic50_query_is_accepted_by_backend_interpreter() -> None:
    query = build_chembl_ic50_interpreted_query(
        ChEMBLIC50QueryBuilderRow("range", "0", "10", "", "nM")
    )

    assert build_default_chembl_interpreter().interpret(query) == (
        "standard_type=IC50 AND standard_value>=0 AND standard_value<10 "
        "AND standard_units=nM"
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


def test_chembl_assay_filters_build_interpreted_query():
    rows = [
        ChEMBLFilterQueryBuilderRow("assay", "label_type", "iexact", "functional"),
        ChEMBLFilterQueryBuilderRow("assay", "organism", "icontains", "virus"),
    ]

    assert (
        build_chembl_interpreted_query(rows)
        == "chembl.assay:label_type__iexact=functional AND organism__icontains=virus"
    )


def test_chembl_cell_line_filters_build_interpreted_query():
    rows = [ChEMBLFilterQueryBuilderRow("cell_line", "organism", "icontains", "mus")]

    assert build_chembl_interpreted_query(rows) == "chembl.cell_line:organism__icontains=mus"


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


def test_chembl_friendly_query_uses_interpreted_preview_format():
    rows = [ChEMBLFilterQueryBuilderRow("target", "gene_symbol", "icontains", "EGFR")]

    assert build_chembl_friendly_query(rows) == "chembl.target:gene_symbol__icontains=EGFR"


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


def test_chembl_builder_output_is_suitable_for_query_value():
    rows = [
        ChEMBLFilterQueryBuilderRow("activity", "standard_type", "exact", "IC50"),
        ChEMBLFilterQueryBuilderRow("activity", "standard_value", "range", "0,100"),
        ChEMBLFilterQueryBuilderRow("activity", "standard_units", "exact", "nM"),
    ]

    assert (
        build_chembl_interpreted_query(rows)
        == "chembl.activity:standard_type=IC50 AND standard_value__range=0,100 AND standard_units=nM"
    )


def test_chembl_builder_metadata_preserves_visual_rows():
    rows = [
        ChEMBLFilterQueryBuilderRow("activity", "target_chembl_id", "exact", "CHEMBL203"),
        ChEMBLFilterQueryBuilderRow("activity", "pchembl_value", "gte", "7"),
    ]

    metadata = build_chembl_query_builder_metadata("chembl_activity", rows)

    assert metadata == {
        "schema_version": QUERY_BUILDER_SCHEMA_VERSION,
        "source": "chembl",
        "builder_key": "chembl_activity",
        "builder_type": "flat_parameters",
        "rows": [
            {"field": "target_chembl_id", "operator": "exact", "value": "CHEMBL203"},
            {"field": "pchembl_value", "operator": "gte", "value": "7"},
        ],
    }


def test_chembl_builder_import_does_not_import_nicegui():
    import_script = """
import sys
import bioseq_dl.gui.query_builders.chembl

if "nicegui" in sys.modules:
    raise RuntimeError("Importing pure ChEMBL query builder utilities loaded NiceGUI.")
"""

    subprocess.run(  # noqa: S603
        [sys.executable, "-c", import_script],
        check=True,
        capture_output=True,
        text=True,
    )
