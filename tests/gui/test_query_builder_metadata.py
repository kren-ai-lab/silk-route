"""Characterization tests for PubChem/ChEBI query-builder metadata round-trips.

These pin the build -> restore round-trip for the two source families before any
dedup of the parallel build/restore helpers: the PubChem path serializes a
threshold (structure similarity), the ChEBI path does not.
"""

from __future__ import annotations

from bioseq_dl.gui.query_builders.chebi import ChEBIQueryBuilderRow, build_chebi_interpreted_query
from bioseq_dl.gui.query_builders.metadata import (
    build_chebi_query_builder_metadata,
    build_pubchem_query_builder_metadata,
    restore_query_builder_metadata,
)
from bioseq_dl.gui.query_builders.pubchem import PubChemQueryBuilderRow, build_pubchem_interpreted_query


def test_pubchem_structure_metadata_round_trip_preserves_threshold() -> None:
    row = PubChemQueryBuilderRow(resource="structure", field="similarity_2d_cid", value="2244", threshold=80)
    metadata = build_pubchem_query_builder_metadata("pubchem_structure", row)

    assert metadata["source"] == "pubchem"
    assert metadata["rows"] == [{"field": "similarity_2d_cid", "value": "2244", "threshold": 80}]

    query = build_pubchem_interpreted_query(row)
    restored = restore_query_builder_metadata(metadata, query, "compound", None)

    assert restored.builder_key == "pubchem_structure"
    assert restored.form_rows == ({"field": "similarity_2d_cid", "value": "2244", "threshold": 80},)


def test_chebi_entity_metadata_round_trip() -> None:
    row = ChEBIQueryBuilderRow(resource="entity", field="name", value="water")
    metadata = build_chebi_query_builder_metadata("chebi_entity", row)

    assert metadata["source"] == "chebi"
    assert metadata["rows"] == [{"field": "name", "value": "water"}]

    query = build_chebi_interpreted_query(row)
    restored = restore_query_builder_metadata(metadata, query, "compound", None)

    assert restored.builder_key == "chebi_entity"
    assert restored.form_rows == ({"field": "name", "value": "water"},)
