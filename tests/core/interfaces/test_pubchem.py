"""Offline tests for the PubChem interface (PUG-View path)."""

from __future__ import annotations

import pytest
from niquests_mock import startswith

from bioseq_dl.core.exceptions import RequestError
from bioseq_dl.core.interfaces.pubchem import (
    WORKFLOW_COMPOUND_PROPERTIES_METHOD,
    PubChemInterface,
)
from tests._helpers import load_fixture
from tests.core.interfaces._contract import CachingContract, HttpErrorContract

# Note the double slash: API_URL ends with "/" and the pug_view branch prepends "/pug_view".
COMPOUND_URL = "https://pubchem.ncbi.nlm.nih.gov/rest//pug_view/data/compound/444444/JSON"


@pytest.fixture
def interface(tmp_path):
    return PubChemInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_builds_url_and_returns_record(interface, niquests_mock):
    body = load_fixture("pubchem", "pug_view_compound")
    niquests_mock.get(url=startswith(COMPOUND_URL)).respond(status_code=200, json=body)

    result = interface.fetch({"cid": "444444"}, method="pug_view/compound", option="default")

    assert result == body
    assert len(niquests_mock.calls) == 1
    assert niquests_mock.calls[0].request.url == COMPOUND_URL


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("pubchem", "pug_view_compound")
    parsed = interface.parse(
        body, fields_to_extract={"default": {"title": "Record.RecordTitle"}}, option="default"
    )

    assert parsed == {"title": body["Record"]["RecordTitle"]}


WORKFLOW_LOOKUP_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/aspirin/property/"


def test_workflow_fetch_raises_request_error_on_http_failure(interface, niquests_mock):
    # HTTP failure must raise RequestError so the base records request_error.
    niquests_mock.get(url=startswith(WORKFLOW_LOOKUP_URL)).respond(status_code=503)

    query = {"namespace": "name", "identifier": "aspirin", "search_mode": "lookup"}
    with pytest.raises(RequestError, match="PubChem workflow request failed"):
        interface.fetch(query, method=WORKFLOW_COMPOUND_PROPERTIES_METHOD)


@pytest.mark.parametrize(("threshold", "expected"), [(0, 0), (95, 95), (None, 90)])
def test_workflow_similarity_threshold_is_honored(interface, threshold, expected):
    query = {"namespace": "cid", "identifier": "2244", "search_mode": "similarity_2d"}
    if threshold is not None:
        query["threshold"] = threshold
    request = interface._build_workflow_compound_properties_request(query)
    assert request.params["Threshold"] == expected


def test_workflow_similarity_cache_key_matches_default_threshold(interface):
    # An unset threshold and an explicit 90 hit the same cache entry (request uses 90).
    spec = interface.METHODS[WORKFLOW_COMPOUND_PROPERTIES_METHOD]
    base = {"namespace": "cid", "identifier": "2244", "search_mode": "similarity_2d"}
    assert interface._make_identifier(base, spec) == interface._make_identifier(
        {**base, "threshold": 90}, spec
    )
    assert interface._make_identifier(base, spec) != interface._make_identifier(
        {**base, "threshold": 50}, spec
    )


class TestPubchemContract(CachingContract, HttpErrorContract):
    INTERFACE_URL = COMPOUND_URL
    QUERY = {"cid": "444444"}
    METHOD = "pug_view/compound"
    FIXTURE = ("pubchem", "pug_view_compound")
    CALL_KWARGS = {"option": "default"}
    ERROR_RETURNS_EMPTY = True
