"""Tests for ChEBI query-builder string parsing."""

from __future__ import annotations

import socket

import pytest

from bioseq_dl.core.workflow.chebi_query_parser import parse_chebi_query_builder_string


def fail_socket_connection(*_args: object, **_kwargs: object) -> socket.socket:
    """Fail if pure ChEBI parsing attempts a network connection."""
    msg = "network access attempted"
    raise AssertionError(msg)


def test_parse_chebi_entity_id_lookup() -> None:
    parsed = parse_chebi_query_builder_string("chebi.entity:chebi_id=CHEBI:15377")

    assert parsed == {
        "source": "chebi",
        "resource": "entity",
        "query_model": "advanced_search",
        "parameters": {"chebi_id": "CHEBI:15377"},
    }


def test_parse_chebi_entity_name_contains() -> None:
    parsed = parse_chebi_query_builder_string('chebi.entity:name_contains="caffeine"')

    assert parsed["parameters"] == {"name_contains": "caffeine"}


def test_parse_chebi_entity_formula() -> None:
    parsed = parse_chebi_query_builder_string('chebi.entity:formula="C8H10N4O2"')

    assert parsed["parameters"] == {"formula": "C8H10N4O2"}


def test_parse_chebi_entity_monoisotopic_mass_range() -> None:
    parsed = parse_chebi_query_builder_string("chebi.entity:monoisotopic_mass_range=194.0,195.0")

    assert parsed["parameters"] == {"monoisotopic_mass_range": (194.0, 195.0)}


def test_parse_chebi_entity_charge_range() -> None:
    parsed = parse_chebi_query_builder_string("chebi.entity:charge_range=-1,1")

    assert parsed["parameters"] == {"charge_range": (-1, 1)}


def test_parse_chebi_ontology_relation_search() -> None:
    parsed = parse_chebi_query_builder_string("chebi.ontology:relation=has_role AND term=metabolite")

    assert parsed == {
        "source": "chebi",
        "resource": "ontology",
        "query_model": "ontology_search",
        "parameters": {"relation": "has_role", "term": "metabolite"},
    }


def test_chebi_parser_rejects_invalid_chebi_ids() -> None:
    with pytest.raises(ValueError, match=r"CHEBI:<digits>"):
        parse_chebi_query_builder_string("chebi.entity:chebi_id=15377")


def test_chebi_parser_rejects_malformed_ranges() -> None:
    with pytest.raises(ValueError, match="comma-separated low,high range"):
        parse_chebi_query_builder_string("chebi.entity:monoisotopic_mass_range=194.0")


def test_chebi_parser_rejects_unsupported_resources() -> None:
    expected = "Unsupported ChEBI resource 'pathway'. Supported resources are: entity, ontology, structure."
    with pytest.raises(ValueError, match=expected):
        parse_chebi_query_builder_string("chebi.pathway:term=metabolite")


def test_chebi_parser_rejects_unsupported_entity_fields_clearly() -> None:
    expected = (
        "Unsupported ChEBI entity field 'target'. Supported fields are: "
        "chebi_id, name_contains, name, formula, average_mass_range, "
        "monoisotopic_mass_range, charge_range, database_xref, star."
    )
    with pytest.raises(ValueError, match=expected):
        parse_chebi_query_builder_string("chebi.entity:target=EGFR")


def test_chebi_parser_rejects_unsupported_ontology_fields_clearly() -> None:
    expected = "Unsupported ChEBI ontology field 'role'. Supported fields are: relation, term."
    with pytest.raises(ValueError, match=expected):
        parse_chebi_query_builder_string("chebi.ontology:role=has_role AND term=metabolite")


def test_chebi_parser_performs_no_network_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "create_connection", fail_socket_connection)

    assert parse_chebi_query_builder_string("chebi.entity:chebi_id=CHEBI:15377")["parameters"] == {
        "chebi_id": "CHEBI:15377"
    }
