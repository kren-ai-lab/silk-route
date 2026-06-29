"""Tests for pure ChEBI query builder utilities."""

from __future__ import annotations

import subprocess
import sys

import pytest

from bioseq_dl.core.workflow.chebi_query_catalog import get_chebi_query_builder_field_catalog
from bioseq_dl.core.workflow.chebi_query_parser import parse_chebi_query_builder_string
from bioseq_dl.gui.query_builders.chebi import (
    ChEBIQueryBuilderRow,
    build_chebi_interpreted_query,
    get_chebi_executable_parameter_name,
)

CHEBI_CONSISTENCY_CASES = (
    (
        "entity",
        "chebi_id",
        "exact",
        "CHEBI:15377",
        None,
        "chebi.entity:chebi_id=CHEBI:15377",
        {"chebi_id": "CHEBI:15377"},
        ("chebi_id",),
    ),
    (
        "entity",
        "name",
        "contains",
        "caffeine",
        None,
        'chebi.entity:name_contains="caffeine"',
        {"name_contains": "caffeine"},
        ("name",),
    ),
    (
        "entity",
        "formula",
        "exact",
        "C8H10N4O2",
        None,
        'chebi.entity:formula="C8H10N4O2"',
        {"formula": "C8H10N4O2"},
        ("formula",),
    ),
    (
        "entity",
        "average_mass",
        "range",
        "194.0,195.0",
        None,
        "chebi.entity:average_mass_range=194.0,195.0",
        {"average_mass_range": (194.0, 195.0)},
        ("average_mass",),
    ),
    (
        "entity",
        "monoisotopic_mass",
        "range",
        "194.0,195.0",
        None,
        "chebi.entity:monoisotopic_mass_range=194.0,195.0",
        {"monoisotopic_mass_range": (194.0, 195.0)},
        ("monoisotopic_mass",),
    ),
    (
        "entity",
        "charge",
        "range",
        "-1,1",
        None,
        "chebi.entity:charge_range=-1,1",
        {"charge_range": (-1, 1)},
        ("charge",),
    ),
    (
        "entity",
        "database_xref",
        "exact",
        "ChEMBL",
        None,
        "chebi.entity:database_xref=ChEMBL",
        {"database_xref": "ChEMBL"},
        ("database_xref",),
    ),
    (
        "entity",
        "star",
        "exact",
        "3",
        None,
        "chebi.entity:star=3",
        {"star": 3},
        ("star",),
    ),
    (
        "ontology",
        "ontology_relation",
        "exact",
        "has_role",
        "metabolite",
        "chebi.ontology:relation=has_role AND term=metabolite",
        {"relation": "has_role", "term": "metabolite"},
        ("ontology_relation", "ontology_term"),
    ),
    (
        "structure",
        "connectivity",
        "connectivity",
        "BSYNRYMUTXBXSQ",
        None,
        'chebi.structure:connectivity="BSYNRYMUTXBXSQ"',
        {"connectivity": "BSYNRYMUTXBXSQ"},
        ("connectivity",),
    ),
    (
        "structure",
        "substructure",
        "substructure",
        "c1ccccc1",
        None,
        'chebi.structure:substructure="c1ccccc1"',
        {"substructure": "c1ccccc1"},
        ("substructure",),
    ),
    (
        "structure",
        "similarity",
        "similarity",
        "c1ccccc1",
        None,
        'chebi.structure:similarity="c1ccccc1"',
        {"similarity": "c1ccccc1"},
        ("similarity",),
    ),
)


def test_chebi_entity_builder_produces_query_value() -> None:
    rows = [
        ChEBIQueryBuilderRow("entity", "name", "contains", "caffeine"),
        ChEBIQueryBuilderRow("entity", "star", "exact", "3"),
    ]

    assert build_chebi_interpreted_query(rows) == 'chebi.entity:name_contains="caffeine" AND star=3'


def test_chebi_ontology_builder_produces_query_value() -> None:
    rows = [ChEBIQueryBuilderRow("ontology", "ontology_relation", "exact", "has_role", "metabolite")]

    assert build_chebi_interpreted_query(rows) == "chebi.ontology:relation=has_role AND term=metabolite"


def test_chebi_ontology_builder_rejects_term_as_primary_field() -> None:
    rows = [ChEBIQueryBuilderRow("ontology", "ontology_term", "exact", "metabolite", "cofactor")]

    with pytest.raises(ValueError, match="must use the ontology_relation field"):
        build_chebi_interpreted_query(rows)


@pytest.mark.parametrize(
    (
        "resource",
        "field",
        "operator",
        "value",
        "secondary_value",
        "expected_query",
        "expected_parameters",
        "catalog_fields",
    ),
    CHEBI_CONSISTENCY_CASES,
)
def test_chebi_catalog_builder_parser_consistency(
    resource: str,
    field: str,
    operator: str,
    value: str,
    secondary_value: str | None,
    expected_query: str,
    expected_parameters: dict[str, object],
    catalog_fields: tuple[str, ...],
) -> None:
    catalog = get_chebi_query_builder_field_catalog(resource)
    assert set(catalog_fields) <= set(catalog)

    query = build_chebi_interpreted_query(
        [ChEBIQueryBuilderRow(resource, field, operator, value, secondary_value)]
    )
    plan = parse_chebi_query_builder_string(query)

    assert query == expected_query
    assert plan["parameters"] == expected_parameters


def test_all_visible_chebi_fields_have_consistency_cases() -> None:
    visible_fields = {
        (resource, field)
        for resource in ("entity", "ontology", "structure")
        for field in get_chebi_query_builder_field_catalog(resource)
    }
    tested_fields = {
        (resource, catalog_field)
        for resource, *_middle, catalog_fields in CHEBI_CONSISTENCY_CASES
        for catalog_field in catalog_fields
    }

    assert tested_fields == visible_fields


def test_chebi_ontology_parameter_mapping_is_explicit() -> None:
    assert get_chebi_executable_parameter_name("ontology", "ontology_relation", "exact") == "relation"
    assert get_chebi_executable_parameter_name("ontology", "ontology_term", "exact") == "term"


def test_chebi_structure_builder_produces_query_value() -> None:
    rows = [ChEBIQueryBuilderRow("structure", "substructure", "substructure", "c1ccccc1")]

    assert build_chebi_interpreted_query(rows) == 'chebi.structure:substructure="c1ccccc1"'


def test_chebi_builder_import_does_not_import_nicegui() -> None:
    import_script = """
import sys
import bioseq_dl.gui.query_builders.chebi

if "nicegui" in sys.modules:
    raise RuntimeError("Importing pure ChEBI query builder utilities loaded NiceGUI.")
"""

    subprocess.run(  # noqa: S603
        [sys.executable, "-c", import_script],
        check=True,
        capture_output=True,
        text=True,
    )
