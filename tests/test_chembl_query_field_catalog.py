"""Tests for the ChEMBL query field catalog."""

from __future__ import annotations

from bioseq_dl.core.workflow.chembl_query_catalog import (
    get_chembl_query_resource_catalog,
)


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
