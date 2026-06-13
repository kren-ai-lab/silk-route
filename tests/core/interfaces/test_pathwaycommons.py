"""Offline tests for the PathwayCommons interface."""

from __future__ import annotations

import pytest
import responses

from bioseq_dl.core.interfaces.pathwaycommons import PathwayCommonsInterface
from tests._helpers import load_fixture

FETCH_URL = "https://www.pathwaycommons.org/pc2/v2/fetch"


@pytest.fixture
def interface(tmp_path):
    return PathwayCommonsInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_unwraps_graph(interface, mocked_responses):
    body = load_fixture("pathwaycommons", "fetch")
    mocked_responses.add(responses.POST, FETCH_URL, json=body, status=200)

    result = interface.fetch({"uri": ["http://identifiers.org/uniprot/P04637"]}, method="fetch")

    # fetch unwraps the JSON-LD "@graph" envelope.
    assert result == body["@graph"]
    assert len(mocked_responses.calls) == 1


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("pathwaycommons", "fetch")
    parsed = interface.parse(body["@graph"][0], fields_to_extract=["@id", "@type"])

    assert parsed == {
        "@id": "http://pathwaycommons.org/pc2/Catalysis_1",
        "@type": "Catalysis",
    }


def test_fetch_single_round_trips_through_cache(interface, mocked_responses):
    body = load_fixture("pathwaycommons", "fetch")
    mocked_responses.add(responses.POST, FETCH_URL, json=body, status=200)

    query = {"uri": ["http://identifiers.org/uniprot/P04637"]}
    first, _ = interface.fetch_single(query, method="fetch")
    second, _ = interface.fetch_single(query, method="fetch")

    assert len(mocked_responses.calls) == 1
    assert first == second
