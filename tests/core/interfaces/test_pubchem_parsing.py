"""Offline tests for PubChem response unwrapping and PUG-View flattening.

Pure logic, no network: envelope unwrapping, the nested-section flattener, and
the Value-object extractor that collapses PubChem's verbose value format into
plain scalars/lists. This is where malformed real-world responses bite.
"""

from __future__ import annotations

import pytest

from bioseq_dl.core.interfaces.pubchem import PubChemInterface


@pytest.fixture
def interface(tmp_path):
    return PubChemInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


# --- _has_exactly_one_identifier --------------------------------------------


def test_compound_requires_exactly_one_identifier():
    assert PubChemInterface._has_exactly_one_identifier("pug/compound", {"cid": "1"}) is True
    assert PubChemInterface._has_exactly_one_identifier("pug/compound", {}) is False
    assert PubChemInterface._has_exactly_one_identifier("pug/compound", {"cid": "1", "name": "x"}) is False


def test_gene_requires_exactly_one_identifier():
    assert PubChemInterface._has_exactly_one_identifier("pug/gene", {"genesymbol": "TP53"}) is True
    assert (
        PubChemInterface._has_exactly_one_identifier("pug/gene", {"genesymbol": "x", "geneid": "1"}) is False
    )


def test_methods_without_constraint_pass():
    assert PubChemInterface._has_exactly_one_identifier("pug/protein", {}) is True


# --- _unwrap_pug_envelope ---------------------------------------------------


def test_unwrap_information_list():
    response = {"InformationList": {"Information": [{"CID": 1}, {"CID": 2}]}}
    out = PubChemInterface._unwrap_pug_envelope(response, "compound", "default", {})
    assert out == [{"CID": 1}, {"CID": 2}]


def test_unwrap_property_table_follows_nested_path():
    response = {"PropertyTable": {"Properties": [{"CID": 1, "MolecularWeight": "18"}]}}
    out = PubChemInterface._unwrap_pug_envelope(response, "compound", "default", {})
    assert out == [{"CID": 1, "MolecularWeight": "18"}]


def test_unwrap_table_zips_columns_and_rows():
    response = {
        "Table": {
            "Columns": {"Column": ["cid", "name"]},
            "Row": [{"Cell": [1, "water"]}, {"Cell": [2, "ethanol"]}],
        }
    }
    out = PubChemInterface._unwrap_pug_envelope(response, "compound", "default", {})
    assert out == [{"cid": 1, "name": "water"}, {"cid": 2, "name": "ethanol"}]


def test_unwrap_pc_compounds_returns_payload_directly():
    response = {"PC_Compounds": [{"id": 1}]}
    out = PubChemInterface._unwrap_pug_envelope(response, "compound", "default", {})
    assert out == [{"id": 1}]


def test_unwrap_unknown_envelope_returns_response_unchanged():
    response = {"Something": 1}
    assert PubChemInterface._unwrap_pug_envelope(response, "compound", "default", {}) == response


# --- _proccess_information_value --------------------------------------------


def test_value_string_with_markup_single_collapses_to_scalar(interface):
    assert interface._proccess_information_value({"StringWithMarkup": [{"String": "hello"}]}) == "hello"


def test_value_string_with_markup_multiple_returns_list(interface):
    out = interface._proccess_information_value({"StringWithMarkup": [{"String": "a"}, {"String": "b"}]})
    assert out == ["a", "b"]


def test_value_number_single_collapses(interface):
    assert interface._proccess_information_value({"Number": [42]}) == 42


def test_value_plain_string(interface):
    assert interface._proccess_information_value({"String": "x"}) == "x"


def test_value_url(interface):
    assert interface._proccess_information_value({"URL": "http://x"}) == "http://x"


def test_value_boolean_single_collapses(interface):
    assert interface._proccess_information_value({"Boolean": [True]}) is True


def test_value_unknown_key_returned_unchanged(interface):
    payload = {"Mystery": 1}
    assert interface._proccess_information_value(payload) == payload


# --- is_pug_view_record -----------------------------------------------------


def test_is_pug_view_record_true(interface):
    assert interface.is_pug_view_record({"record_type": "cid", "record_number": 1, "sections": []})


def test_is_pug_view_record_false_when_keys_missing(interface):
    assert interface.is_pug_view_record({"record_type": "cid"}) is False


# --- process_tocheadings (nested flattening) --------------------------------


def test_process_tocheadings_flattens_and_recurses(interface):
    sections = [
        {
            "TOCHeading": "Names",
            "Information": [{"Value": {"StringWithMarkup": [{"String": "water"}]}}],
        },
        {
            "TOCHeading": "Properties",
            "Section": [
                {
                    "TOCHeading": "Molecular Weight",
                    "Information": [{"Value": {"Number": [18.015]}}],
                }
            ],
        },
    ]
    out = interface.process_tocheadings(sections)
    assert out == {"Names": "water", "Molecular Weight": 18.015}


def test_process_sections_includes_record_id(interface):
    data = {
        "record_type": "CID",
        "record_number": 962,
        "sections": [{"TOCHeading": "Title", "Information": [{"Value": {"String": "Water"}}]}],
    }
    out = interface.process_sections(data)
    assert out == {"CID": 962, "Title": "Water"}
