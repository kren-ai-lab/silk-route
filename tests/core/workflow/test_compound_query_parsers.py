"""Offline tests for PubChem/ChEBI query-builder string parsing."""

from __future__ import annotations

import pytest

from silkroute.core.workflow.chebi_query_parser import (
    get_chebi_prefixed_query_resource,
    parse_chebi_query_builder_string,
)
from silkroute.core.workflow.pubchem_query_parser import (
    get_pubchem_prefixed_query_resource,
    parse_pubchem_query_builder_string,
)


@pytest.mark.parametrize(
    "query",
    ["PUBCHEM.COMPOUND:name=aspirin", "pubchem.Compound:name=aspirin"],
)
def test_pubchem_prefix_is_case_insensitive(query):
    plan = parse_pubchem_query_builder_string(query)
    assert plan["resource"] == "compound"
    assert get_pubchem_prefixed_query_resource(query) == "compound"


@pytest.mark.parametrize("query", ["ChEBI.entity:name=water", "CHEBI.ENTITY:name=water"])
def test_chebi_prefix_is_case_insensitive(query):
    plan = parse_chebi_query_builder_string(query)
    assert plan["resource"] == "entity"
    assert get_chebi_prefixed_query_resource(query) == "entity"


def test_pubchem_body_case_is_preserved():
    # The identifier body must keep its original case (SMILES/InChI are case-sensitive).
    plan = parse_pubchem_query_builder_string("PubChem.structure:smiles_identity=CCO")
    assert plan["parameters"]["smiles_identity"] == "CCO"


def test_duplicate_structure_condition_is_rejected():
    with pytest.raises(ValueError, match="duplicate condition"):
        parse_pubchem_query_builder_string("pubchem.structure:smiles_identity=CCO AND smiles_identity=CCC")


def test_similarity_threshold_zero_is_preserved():
    plan = parse_pubchem_query_builder_string("pubchem.structure:similarity_2d_cid=2244 AND threshold=0")
    assert plan["parameters"]["threshold"] == 0
