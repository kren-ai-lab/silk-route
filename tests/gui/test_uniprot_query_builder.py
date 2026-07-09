"""Tests for pure UniProt query builder utilities."""

from __future__ import annotations

import subprocess
import sys

import pytest

from bioseq_dl.gui.query_builders.uniprot import (
    UniProtQueryBuilderRow,
    build_uniprot_friendly_query,
    build_uniprot_interpreted_query,
    get_uniprot_query_builder_field_metadata,
)


def test_one_organism_row_builds_quoted_friendly_query():
    rows = [UniProtQueryBuilderRow(None, "organism", "Homo sapiens", "any")]

    assert build_uniprot_friendly_query(rows) == 'organism_any:"Homo sapiens"'


def test_multiple_rows_with_and_build_friendly_query():
    rows = [
        UniProtQueryBuilderRow(None, "organism", "Homo sapiens", "any"),
        UniProtQueryBuilderRow("AND", "temperature", "20-30,50-60", "any"),
    ]

    assert build_uniprot_friendly_query(rows) == 'organism_any:"Homo sapiens" AND temperature_any:20-30,50-60'


def test_multiple_rows_with_or_build_friendly_query():
    rows = [
        UniProtQueryBuilderRow(None, "keywords", "ATP binding,Metal-binding", "any"),
        UniProtQueryBuilderRow("OR", "go", "DNA repair", "any"),
    ]

    assert (
        build_uniprot_friendly_query(rows)
        == 'keywords_any:"ATP binding",Metal-binding OR go_any:"DNA repair"'
    )


def test_values_with_spaces_are_quoted_and_ranges_are_not_quoted():
    rows = [
        UniProtQueryBuilderRow(None, "organism", "Homo sapiens,Mus musculus", "any"),
        UniProtQueryBuilderRow("AND", "temperature", "20-30,50-60", "any"),
    ]

    assert (
        build_uniprot_friendly_query(rows)
        == 'organism_any:"Homo sapiens","Mus musculus" AND temperature_any:20-30,50-60'
    )


def test_invalid_field_is_rejected():
    rows = [UniProtQueryBuilderRow(None, "unsupported", "value", "any")]

    with pytest.raises(ValueError, match="Row 1: field is not supported"):
        build_uniprot_friendly_query(rows)


def test_invalid_match_mode_is_rejected():
    rows = [UniProtQueryBuilderRow(None, "organism", "Homo sapiens", "some")]

    with pytest.raises(ValueError, match="Row 1: match mode must be any, all, or not"):
        build_uniprot_friendly_query(rows)


def test_missing_connector_in_non_first_row_is_rejected():
    rows = [
        UniProtQueryBuilderRow(None, "organism", "Homo sapiens", "any"),
        UniProtQueryBuilderRow(None, "go", "DNA repair", "any"),
    ]

    with pytest.raises(ValueError, match="Row 2: connector must be AND or OR"):
        build_uniprot_friendly_query(rows)


def test_first_row_does_not_require_connector():
    rows = [UniProtQueryBuilderRow(None, "organism", "Homo sapiens", "any")]

    assert build_uniprot_friendly_query(rows) == 'organism_any:"Homo sapiens"'


def test_builder_error_for_missing_values_includes_row_context():
    rows = [
        UniProtQueryBuilderRow(None, "organism", "Homo sapiens", "any"),
        UniProtQueryBuilderRow("AND", "go", "", "any"),
    ]

    with pytest.raises(ValueError, match="Row 2: values are required"):
        build_uniprot_friendly_query(rows)


def test_selected_field_metadata_is_available_for_ui_display():
    metadata = get_uniprot_query_builder_field_metadata("go")

    assert metadata.label == "GO term"
    assert metadata.description
    assert metadata.placeholder == '0006281,"DNA repair"'
    assert metadata.examples


def test_interpreted_query_is_returned_from_builder_rows():
    rows = [
        UniProtQueryBuilderRow(None, "organism", "Homo sapiens", "any"),
        UniProtQueryBuilderRow("AND", "temperature", "20-30,50-60", "any"),
    ]

    assert (
        build_uniprot_interpreted_query(rows)
        == "organism_id:9606 AND (cc_bpcp_temp_dependence:20-30 OR cc_bpcp_temp_dependence:50-60)"
    )


def test_databases_field_builds_interpreted_query_and_db_alias_is_rejected():
    rows = [UniProtQueryBuilderRow(None, "databases", "alphafold,pdb", "any")]

    assert build_uniprot_friendly_query(rows) == "databases_any:alphafold,pdb"
    assert build_uniprot_interpreted_query(rows) == "(database:alphafolddb OR database:pdb)"

    with pytest.raises(ValueError, match="field is not supported"):
        build_uniprot_friendly_query([UniProtQueryBuilderRow(None, "db", "alphafold", "any")])


def test_query_builder_import_does_not_import_nicegui():
    import_script = """
import sys
import bioseq_dl.gui.query_builders.uniprot

if "nicegui" in sys.modules:
    raise RuntimeError("Importing pure UniProt query builder utilities loaded NiceGUI.")
"""

    subprocess.run(  # noqa: S603
        [sys.executable, "-c", import_script],
        check=True,
        capture_output=True,
        text=True,
    )
