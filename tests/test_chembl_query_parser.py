"""Tests for ChEMBL query-builder string parsing."""

from __future__ import annotations

import pytest

from bioseq_dl.core.workflow.chembl_query_parser import parse_chembl_query_builder_string
from bioseq_dl.core.workflow.query_interpreter import build_default_chembl_interpreter


def test_chembl_filter_list_query_converts_to_filters_structure():
    parsed = parse_chembl_query_builder_string(
        "chembl.target:type__iexact=protein AND gene_symbol__icontains=EGFR"
    )

    assert parsed == {
        "resource": "target",
        "query_model": "filter_list",
        "filters": [
            {"field": "type", "filter_type": "iexact", "value": "protein"},
            {"field": "gene_symbol", "filter_type": "icontains", "value": "EGFR"},
        ],
    }


def test_chembl_activity_query_converts_to_flat_parameters_structure():
    parsed = parse_chembl_query_builder_string(
        "chembl.activity:target_chembl_id=CHEMBL5169197 AND pchembl_value=5.83"
    )

    assert parsed == {
        "resource": "activity",
        "query_model": "flat_parameters",
        "parameters": {
            "target_chembl_id": "CHEMBL5169197",
            "pchembl_value": "5.83",
        },
    }


def test_chembl_interpreter_exposes_builder_query_parser():
    interpreter = build_default_chembl_interpreter()

    assert interpreter.parse_query_builder_string(
        "chembl.target:gene_symbol__icontains=EGFR"
    ) == {
        "resource": "target",
        "query_model": "filter_list",
        "filters": [{"field": "gene_symbol", "filter_type": "icontains", "value": "EGFR"}],
    }


def test_existing_chembl_ic50_behavior_still_works():
    interpreter = build_default_chembl_interpreter()

    assert interpreter.interpret("ic50:10-100") == (
        "standard_type=IC50 AND standard_value>10 AND standard_value<100"
    )


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            "ic50:0-10 AND standard_units:nM",
            "standard_type=IC50 AND standard_value>0 AND standard_value<10 AND standard_units=nM",
        ),
        (
            "ic50:<1000 AND standard_units:nM",
            "standard_type=IC50 AND standard_value<1000 AND standard_units=nM",
        ),
        (
            "ic50:>=10 AND standard_units=uM",
            "standard_type=IC50 AND standard_value>=10 AND standard_units=uM",
        ),
        (
            "ic50:50 AND standard_units: nM",
            "standard_type=IC50 AND standard_value=50 AND standard_units=nM",
        ),
        (
            "ic50:0-1 AND standard_units:µM",
            "standard_type=IC50 AND standard_value>0 AND standard_value<1 AND standard_units=uM",
        ),
        (
            "ic50:0-1 AND standard_units:μM",
            "standard_type=IC50 AND standard_value>0 AND standard_value<1 AND standard_units=uM",
        ),
    ],
)
def test_chembl_ic50_standard_units_are_interpreted(query: str, expected: str) -> None:
    interpreter = build_default_chembl_interpreter()

    assert interpreter.interpret(query) == expected


def test_chembl_ic50_empty_standard_units_are_rejected() -> None:
    interpreter = build_default_chembl_interpreter()

    with pytest.raises(ValueError, match="standard_units must be a non-empty value"):
        interpreter.interpret("ic50:0-10 AND standard_units:")
