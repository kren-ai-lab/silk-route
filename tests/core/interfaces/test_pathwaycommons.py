"""Offline tests for the PathwayCommons interface."""

from __future__ import annotations

import pytest
from niquests_mock import startswith

from bioseq_dl.core.exceptions import RequestError
from bioseq_dl.core.interfaces.pathwaycommons import PathwayCommonsInterface
from tests._helpers import load_fixture

FETCH_URL = "https://www.pathwaycommons.org/pc2/v2/fetch"
TOP_PATHWAYS_URL = "https://www.pathwaycommons.org/pc2/v2/top_pathways"


@pytest.fixture
def interface(tmp_path):
    return PathwayCommonsInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_unwraps_graph(interface, niquests_mock):
    body = load_fixture("pathwaycommons", "fetch")
    niquests_mock.post(url=startswith(FETCH_URL)).respond(status_code=200, json=body)

    result = interface.fetch({"uri": ["uniprot:P04637"]}, method="fetch")

    # fetch unwraps the JSON-LD "@graph" envelope.
    assert result == body["@graph"]
    assert len(niquests_mock.calls) == 1


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("pathwaycommons", "fetch")
    record = body["@graph"][0]
    parsed = interface.parse(record, fields_to_extract=["@id", "@type"])

    assert parsed == {k: record[k] for k in ("@id", "@type")}


def test_fetch_single_round_trips_through_cache(interface, niquests_mock):
    body = load_fixture("pathwaycommons", "fetch")
    niquests_mock.post(url=startswith(FETCH_URL)).respond(status_code=200, json=body)

    query = {"uri": ["uniprot:P04637"]}
    first, _ = interface.fetch_single(query, method="fetch")
    second, _ = interface.fetch_single(query, method="fetch")

    assert len(niquests_mock.calls) == 1
    assert first == second


def test_fetch_unwraps_search_hit(interface, niquests_mock):
    body = {"searchHit": [{"uri": "http://identifiers.org/reactome/R-HSA-1"}]}
    niquests_mock.post(url=startswith(TOP_PATHWAYS_URL)).respond(status_code=200, json=body)

    result = interface.fetch({"q": "TP53"}, method="top_pathways")

    assert result == body["searchHit"]


def test_fetch_missing_required_param_raises(interface):
    with pytest.raises(ValueError, match="uri"):
        interface.fetch({"uri": []}, method="fetch")


def test_fetch_raises_on_http_error(interface, niquests_mock):
    niquests_mock.post(url=startswith(FETCH_URL)).respond(status_code=500, json={"error": "boom"})

    with pytest.raises(RequestError):
        interface.fetch({"uri": ["uniprot:P04637"]}, method="fetch")
