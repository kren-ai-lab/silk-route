"""Tests for PubChem query-builder string parsing."""

from __future__ import annotations

import socket

import pytest

from bioseq_dl.core.workflow.pubchem_query_parser import parse_pubchem_query_builder_string


def fail_socket_connection(*_args: object, **_kwargs: object) -> socket.socket:
    """Fail if pure PubChem parsing attempts a network connection."""
    msg = "network access attempted"
    raise AssertionError(msg)


def test_parse_pubchem_compound_cid_lookup() -> None:
    parsed = parse_pubchem_query_builder_string("pubchem.compound:cid=2244")

    assert parsed == {
        "source": "pubchem",
        "resource": "compound",
        "query_model": "compound_lookup",
        "parameters": {"cid": "2244"},
    }


def test_parse_pubchem_compound_name_lookup() -> None:
    parsed = parse_pubchem_query_builder_string('pubchem.compound:name="glucose"')

    assert parsed["parameters"] == {"name": "glucose"}


def test_parse_pubchem_compound_inchikey_lookup() -> None:
    parsed = parse_pubchem_query_builder_string("pubchem.compound:inchikey=BSYNRYMUTXBXSQ-UHFFFAOYSA-N")

    assert parsed["parameters"] == {"inchikey": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"}


def test_parse_pubchem_structure_substructure_search() -> None:
    parsed = parse_pubchem_query_builder_string('pubchem.structure:smiles_substructure="c1ccccc1"')

    assert parsed == {
        "source": "pubchem",
        "resource": "structure",
        "query_model": "structure_search",
        "parameters": {"smiles_substructure": "c1ccccc1"},
    }


def test_parse_pubchem_structure_similarity_search() -> None:
    parsed = parse_pubchem_query_builder_string("pubchem.structure:similarity_2d_cid=446157 AND threshold=80")

    assert parsed["parameters"] == {"similarity_2d_cid": "446157", "threshold": 80}


@pytest.mark.parametrize(
    "query",
    [
        "pubchem.structure:similarity_2d_cid=446157 AND threshold=101",
        "pubchem.structure:similarity_2d_cid=446157 AND threshold=-1",
        "pubchem.structure:similarity_2d_cid=446157 AND threshold=80.5",
    ],
)
def test_pubchem_parser_rejects_invalid_thresholds(query: str) -> None:
    with pytest.raises(ValueError, match="threshold must be an integer between 0 and 100"):
        parse_pubchem_query_builder_string(query)


def test_pubchem_parser_rejects_unsupported_resources() -> None:
    expected = "Unsupported PubChem resource 'assay'. Supported resources are: compound, structure."
    with pytest.raises(ValueError, match=expected):
        parse_pubchem_query_builder_string("pubchem.assay:name=glucose")


def test_pubchem_parser_rejects_unsupported_fields() -> None:
    expected = "Unsupported PubChem compound field 'sid'. Supported fields are: cid, name, inchikey, inchi."
    with pytest.raises(ValueError, match=expected):
        parse_pubchem_query_builder_string("pubchem.compound:sid=123")


def test_pubchem_parser_performs_no_network_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "create_connection", fail_socket_connection)

    assert parse_pubchem_query_builder_string("pubchem.compound:cid=2244")["parameters"] == {"cid": "2244"}
