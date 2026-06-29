"""Tests for the PubChem query field catalog."""

from __future__ import annotations

from bioseq_dl.core.workflow.pubchem_query_catalog import (
    COMPOUND_LOOKUP_MODEL,
    STRUCTURE_SEARCH_MODEL,
    get_pubchem_query_builder_field_catalog,
    get_pubchem_query_resource_catalog,
)


def test_pubchem_query_catalog_contains_expected_resources() -> None:
    catalog = get_pubchem_query_resource_catalog()

    assert {"compound", "structure"} <= set(catalog)
    assert catalog["compound"].query_model == COMPOUND_LOOKUP_MODEL
    assert catalog["structure"].query_model == STRUCTURE_SEARCH_MODEL


def test_pubchem_query_catalog_contains_expected_builder_fields() -> None:
    catalog = get_pubchem_query_resource_catalog()

    assert {"cid", "name", "inchikey", "inchi"} <= set(catalog["compound"].fields)
    assert {"smiles_identity", "smiles_substructure", "similarity_2d"} <= set(catalog["structure"].fields)


def test_pubchem_visible_fields_expose_ui_metadata() -> None:
    for resource in ("compound", "structure"):
        fields = get_pubchem_query_builder_field_catalog(resource)
        assert fields
        for field in fields.values():
            assert field.label
            assert field.description
            assert field.placeholder
            assert field.examples
            assert field.supported_modes
            assert field.native_input_kind
            assert field.resolver_kind


def test_pubchem_unsupported_fields_are_not_exposed() -> None:
    compound_fields = get_pubchem_query_builder_field_catalog("compound")

    assert "sid" not in compound_fields
    assert "activity" not in compound_fields
