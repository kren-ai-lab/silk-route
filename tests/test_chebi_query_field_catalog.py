"""Tests for the ChEBI query field catalog."""

from __future__ import annotations

from bioseq_dl.core.workflow.chebi_query_catalog import (
    ENTITY_SEARCH_MODEL,
    ONTOLOGY_SEARCH_MODEL,
    STRUCTURE_SEARCH_MODEL,
    get_chebi_query_builder_field_catalog,
    get_chebi_query_resource_catalog,
)


def test_chebi_query_catalog_contains_expected_resources() -> None:
    catalog = get_chebi_query_resource_catalog()

    assert {"entity", "ontology", "structure"} <= set(catalog)
    assert catalog["entity"].query_model == ENTITY_SEARCH_MODEL
    assert catalog["ontology"].query_model == ONTOLOGY_SEARCH_MODEL
    assert catalog["structure"].query_model == STRUCTURE_SEARCH_MODEL


def test_chebi_query_catalog_contains_expected_fields() -> None:
    catalog = get_chebi_query_resource_catalog()

    assert {
        "chebi_id",
        "name",
        "formula",
        "average_mass",
        "monoisotopic_mass",
        "charge",
        "database_xref",
    } <= set(catalog["entity"].fields)
    assert {"ontology_relation", "ontology_term"} <= set(catalog["ontology"].fields)
    assert {"connectivity", "substructure", "similarity"} <= set(catalog["structure"].fields)


def test_chebi_range_capable_fields_are_marked() -> None:
    catalog = get_chebi_query_resource_catalog()

    assert catalog["entity"].fields["average_mass"].supports_range
    assert catalog["entity"].fields["monoisotopic_mass"].supports_range
    assert catalog["entity"].fields["charge"].supports_range
    assert not catalog["entity"].fields["name"].supports_range


def test_chebi_visible_fields_expose_ui_metadata() -> None:
    for resource in ("entity", "ontology", "structure"):
        fields = get_chebi_query_builder_field_catalog(resource)
        assert fields
        for field in fields.values():
            assert field.label
            assert field.description
            assert field.placeholder
            assert field.examples
            assert field.supported_operators
            assert field.resolver_kind
