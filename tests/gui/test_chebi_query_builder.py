"""Tests for pure ChEBI query builder utilities."""

from __future__ import annotations

import subprocess
import sys

import pytest

from bioseq_dl.gui.query_builders.chebi import (
    ChEBIQueryBuilderRow,
    build_chebi_interpreted_query,
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
    rows = [ChEBIQueryBuilderRow("ontology", "ontology_term", "contains", "metabolite", "cofactor")]

    with pytest.raises(ValueError, match="must use the ontology_relation field"):
        build_chebi_interpreted_query(rows)


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
