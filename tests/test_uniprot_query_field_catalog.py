"""Tests for the shared UniProt query field catalog."""

from __future__ import annotations

from bioseq_dl.core.workflow.query_field_catalog import (
    SUPPORTED_MATCH_MODES,
    get_uniprot_query_builder_field_catalog,
    get_uniprot_query_field_catalog,
)
from bioseq_dl.core.workflow.query_interpreter import build_default_uniprot_interpreter


def test_uniprot_query_field_catalog_contains_supported_interpreter_fields():
    catalog = get_uniprot_query_field_catalog()

    assert {
        "databases",
        "keyword",
        "keywords",
        "reviewed",
        "go",
        "organism",
        "taxon",
        "taxid",
        "taxa",
        "ec",
        "length",
        "temperature",
        "ph",
    } <= set(catalog)


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


def test_uniprot_query_builder_catalog_exposes_canonical_database_field_only():
    catalog = get_uniprot_query_builder_field_catalog()

    assert "databases" in catalog
    assert "db" not in catalog
    assert "xref" not in catalog
    assert "database" not in catalog


def test_uniprot_query_builder_catalog_hides_query_alias_fields():
    catalog = get_uniprot_query_builder_field_catalog()

    assert "keywords" in catalog
    assert "keyword" not in catalog
    assert "reviewed" not in catalog


def test_uniprot_query_builder_catalog_contains_field_specific_placeholders():
    catalog = get_uniprot_query_builder_field_catalog()

    assert catalog["organism"].placeholder == "Homo sapiens"
    assert catalog["temperature"].placeholder == "20-30,50-60"
    assert catalog["go"].placeholder == '0006281,"DNA repair"'
    assert catalog["keywords"].placeholder == '"ATP binding","Metal-binding"'
    assert catalog["databases"].placeholder == "alphafold,pdb,string"
    assert catalog["length"].placeholder == "100-500"
    assert catalog["ph"].placeholder == "6-8"


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
