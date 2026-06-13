"""Offline tests for the BioDBNet interface."""

from __future__ import annotations

import pytest
import responses

from bioseq_dl.core.interfaces.biodbnet import BioDBNetInterface
from tests._helpers import load_fixture

API_URL = "https://biodbnet.abcc.ncifcrf.gov/webServices/rest.php/biodbnetRestApi.json"


@pytest.fixture
def interface(tmp_path):
    return BioDBNetInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_builds_url_and_returns_pathways(interface, mocked_responses):
    body = load_fixture("biodbnet", "getpathways")
    mocked_responses.add(responses.GET, API_URL, json=body, status=200)

    result = interface.fetch({"pathways": "1", "taxonId": "511145"}, method="getpathways")

    assert result == body
    assert len(mocked_responses.calls) == 1
    sent = mocked_responses.calls[0].request.url
    assert sent.startswith(API_URL)
    assert "method=getpathways" in sent
    assert "taxonId=511145" in sent


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("biodbnet", "getpathways")
    parsed = interface.parse(body[0], fields_to_extract=["Name", "Source_Database"])

    assert parsed == {k: body[0][k] for k in ("Name", "Source_Database")}


def test_fetch_single_round_trips_through_cache(interface, mocked_responses):
    body = load_fixture("biodbnet", "getpathways")
    mocked_responses.add(responses.GET, API_URL, json=body, status=200)

    query = {"pathways": "1", "taxonId": "511145"}
    first, _ = interface.fetch_single(query, method="getpathways")
    second, _ = interface.fetch_single(query, method="getpathways")

    assert len(mocked_responses.calls) == 1
    assert first == second
