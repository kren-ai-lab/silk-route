"""Tests for the shared UniProt query field catalog."""

from __future__ import annotations

from silkroute.core.workflow.query_field_catalog import (
    SUPPORTED_MATCH_MODES,
    get_uniprot_query_builder_field_catalog,
    get_uniprot_query_field_catalog,
)
from silkroute.core.workflow.query_interpreter import build_default_uniprot_interpreter


def test_uniprot_query_builder_visible_fields_expose_gui_metadata():
    catalog = get_uniprot_query_builder_field_catalog()

    for entry in catalog.values():
        assert entry.key
        assert entry.label
        assert entry.description
        assert entry.placeholder
        assert entry.examples
        assert entry.supported_match_modes == SUPPORTED_MATCH_MODES
        assert entry.query_builder_visible is True


def test_default_uniprot_interpreter_builds_fields_from_shared_catalog():
    catalog = get_uniprot_query_field_catalog()
    interpreter = build_default_uniprot_interpreter()

    assert set(interpreter.config.fields) == set(catalog)
    assert interpreter.config.fields["organism"].field == catalog["organism"].native_field
    assert interpreter.config.fields["go"].value_map == catalog["go"].value_map
    assert interpreter.config.fields["taxon"].resolver_kind == "taxonomy_map"
    assert interpreter.config.fields["taxid"].resolver_kind == "taxonomy_map"
    assert interpreter.config.fields["taxa"].resolver_kind == "taxonomy_map"
    assert interpreter.config.fields["length"].supports_range is True
