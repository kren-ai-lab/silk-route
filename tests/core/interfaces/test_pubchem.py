"""Offline tests for the PubChem interface (PUG-View path)."""

from __future__ import annotations

import re

import pytest
import responses

from bioseq_dl.core.interfaces.pubchem import (
    WORKFLOW_COMPOUND_PROPERTIES_METHOD,
    PubChemInterface,
)
from tests._helpers import load_fixture

# Note the double slash: API_URL ends with "/" and the pug_view branch prepends "/pug_view".
COMPOUND_URL = "https://pubchem.ncbi.nlm.nih.gov/rest//pug_view/data/compound/444444/JSON"


@pytest.fixture
def interface(tmp_path):
    return PubChemInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_builds_url_and_returns_record(interface, mocked_responses):
    body = load_fixture("pubchem", "pug_view_compound")
    mocked_responses.add(responses.GET, COMPOUND_URL, json=body, status=200)

    result = interface.fetch({"cid": "444444"}, method="pug_view/compound", option="default")

    assert result == body
    assert len(mocked_responses.calls) == 1
    assert mocked_responses.calls[0].request.url == COMPOUND_URL


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("pubchem", "pug_view_compound")
    parsed = interface.parse(
        body, fields_to_extract={"default": {"title": "Record.RecordTitle"}}, option="default"
    )

    assert parsed == {"title": body["Record"]["RecordTitle"]}


def test_fetch_single_round_trips_through_cache(interface, mocked_responses):
    body = load_fixture("pubchem", "pug_view_compound")
    mocked_responses.add(responses.GET, COMPOUND_URL, json=body, status=200)

    query = {"cid": "444444"}
    first, _ = interface.fetch_single(query, method="pug_view/compound", option="default")
    second, _ = interface.fetch_single(query, method="pug_view/compound", option="default")

    assert len(mocked_responses.calls) == 1
    assert first == second


def test_workflow_substructure_fetch_uses_official_fast_search_path(interface, mocked_responses):
    body = {"PropertyTable": {"Properties": [{"CID": 241, "Title": "Benzene"}]}}
    mocked_responses.add(
        responses.GET,
        re.compile(r"https://pubchem\.ncbi\.nlm\.nih\.gov/rest/pug/compound/fastsubstructure/.*"),
        json=body,
        status=200,
    )

    result, _metadata = interface.fetch_single(
        {
            "namespace": "smiles",
            "identifier": "c1ccccc1",
            "search_mode": "substructure",
            "max_records": 25,
        },
        method=WORKFLOW_COMPOUND_PROPERTIES_METHOD,
    )

    assert result == [{"CID": 241, "Title": "Benzene"}]
    request = mocked_responses.calls[0].request
    assert "/fastsubstructure/smiles/" in request.url
    assert "MaxRecords=25" in request.url
    assert "/property/CID,MolecularFormula,MolecularWeight" in request.url
