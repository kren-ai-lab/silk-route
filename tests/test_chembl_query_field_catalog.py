"""Tests for the ChEMBL query field catalog."""

from __future__ import annotations

from bioseq_dl.core.workflow.chembl_query_catalog import (
    FILTER_LIST_MODEL,
    FLAT_PARAMETERS_MODEL,
    SINGLE_STRUCTURE_QUERY_MODEL,
    get_chembl_query_resource_catalog,
)


def test_chembl_query_catalog_contains_expected_resources():
    catalog = get_chembl_query_resource_catalog()

    assert {
        "target",
        "assay",
        "cell_line",
        "molecule",
        "activity",
        "substructure",
        "similarity",
    } <= set(catalog)


def test_chembl_query_catalog_resource_models():
    catalog = get_chembl_query_resource_catalog()

    for resource in ("target", "assay", "cell_line", "molecule"):
        assert catalog[resource].query_model == FILTER_LIST_MODEL
    assert catalog["activity"].query_model == FLAT_PARAMETERS_MODEL
    assert catalog["substructure"].query_model == SINGLE_STRUCTURE_QUERY_MODEL
    assert catalog["similarity"].query_model == SINGLE_STRUCTURE_QUERY_MODEL
    assert catalog["substructure"].query_builder_visible is False
    assert catalog["similarity"].query_builder_visible is False


def test_chembl_query_catalog_expected_fields_exist():
    catalog = get_chembl_query_resource_catalog()

    assert {"type", "gene_symbol", "pref_name", "organism"} <= set(catalog["target"].fields)
    assert {"label_type", "organism", "taxonomy_organism", "assay_type", "target_chembl_id"} <= set(
        catalog["assay"].fields
    )
    assert {"organism", "taxonomy_organism", "cell_name", "cell_chembl_id"} <= set(
        catalog["cell_line"].fields
    )
    assert {
        "name",
        "molecular_weight",
        "molecule_chembl_id",
        "molecule_structures__canonical_smiles__connectivity",
    } <= set(catalog["molecule"].fields)
    assert {
        "target_chembl_id",
        "pchembl_value",
        "standard_type",
        "standard_value",
        "standard_units",
        "molecule_chembl_id",
        "assay_chembl_id",
        "assay_type",
        "relationship_type",
        "target_organism",
    } <= set(catalog["activity"].fields)


def test_chembl_visible_fields_expose_ui_metadata():
    catalog = get_chembl_query_resource_catalog()

    for resource in ("target", "assay", "cell_line", "molecule", "activity"):
        for field in catalog[resource].fields.values():
            assert field.label
            assert field.description
            assert field.placeholder
            assert field.examples
            assert field.allowed_operators
            assert field.value_type


def test_chembl_field_operator_expectations():
    catalog = get_chembl_query_resource_catalog()

    assert "icontains" in catalog["target"].fields["gene_symbol"].allowed_operators
    assert "iexact" in catalog["assay"].fields["label_type"].allowed_operators
    assert "icontains" in catalog["cell_line"].fields["organism"].allowed_operators
    assert "range" in catalog["molecule"].fields["molecular_weight"].allowed_operators
    assert {"exact", "in"} <= set(catalog["activity"].fields["target_chembl_id"].allowed_operators)
    assert {"gt", "gte", "lt", "lte", "range"} <= set(
        catalog["activity"].fields["pchembl_value"].allowed_operators
    )
