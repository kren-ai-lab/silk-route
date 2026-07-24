"""Offline tests for the BioDBNet interface."""

from __future__ import annotations

import pytest
from niquests_mock import startswith

from silkroute.core.interfaces.biodbnet import BioDBNetInterface
from tests._helpers import load_fixture
from tests.core.interfaces._contract import CachingContract, HttpErrorContract

API_URL = "https://biodbnet.abcc.ncifcrf.gov/webServices/rest.php/biodbnetRestApi.json"


@pytest.fixture
def interface(tmp_path):
    return BioDBNetInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_builds_url_and_returns_pathways(interface, niquests_mock):
    body = load_fixture("biodbnet", "getpathways")
    niquests_mock.get(url=startswith(API_URL)).respond(status_code=200, json=body)

    result = interface.fetch({"pathways": "1", "taxonId": "511145"}, method="getpathways")

    assert result == body
    assert len(niquests_mock.calls) == 1
    sent = niquests_mock.calls[0].request.url
    assert sent.startswith(API_URL)
    assert "method=getpathways" in sent
    assert "taxonId=511145" in sent


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("biodbnet", "getpathways")
    parsed = interface.parse(body[0], fields_to_extract=["Name", "Source_Database"])

    assert parsed == {k: body[0][k] for k in ("Name", "Source_Database")}


def test_fetch_db2db_extracts_outputs(interface, niquests_mock):
    # BioDBNet echoes each input id as a top-level key whose "outputs" holds the row.
    body = {
        "1234": {"InputValue": "1234", "outputs": {"Gene Symbol": "TP53"}},
        "5678": {"InputValue": "5678", "outputs": {"Gene Symbol": "MDM2"}},
    }
    niquests_mock.get(url=startswith(API_URL)).respond(status_code=200, json=body)

    result = interface.fetch(
        {"input": "genbankid", "inputValues": ["1234", "5678"], "taxonId": "9606"},
        method="db2db",
    )

    assert result == [{"Gene Symbol": "TP53"}, {"Gene Symbol": "MDM2"}]
    # Single endpoint dispatched via ?method=db2db
    assert "method=db2db" in niquests_mock.calls[0].request.url


class TestBiodbnetContract(CachingContract, HttpErrorContract):
    INTERFACE_URL = API_URL
    QUERY = {"pathways": "1", "taxonId": "511145"}
    METHOD = "getpathways"
    FIXTURE = ("biodbnet", "getpathways")
