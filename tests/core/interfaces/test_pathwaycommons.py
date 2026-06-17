"""Offline tests for the PathwayCommons interface."""

from __future__ import annotations

import pytest
from niquests_mock import startswith

from bioseq_dl.core.interfaces.pathwaycommons import PathwayCommonsInterface
from tests._helpers import load_fixture

FETCH_URL = "https://www.pathwaycommons.org/pc2/v2/fetch"


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


def test_fetch_returns_empty_on_http_error(interface, niquests_mock):
    niquests_mock.post(url=startswith(FETCH_URL)).respond(status_code=500, json={"error": "boom"})

    assert interface.fetch({"uri": ["uniprot:P04637"]}, method="fetch") == {}
