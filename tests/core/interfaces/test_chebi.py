"""Offline tests for the ChEBI interface."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
import responses

from bioseq_dl.core.interfaces.chebi import ChEBIInterface
from tests._helpers import load_fixture

COMPOUND_URL = "https://www.ebi.ac.uk/chebi/backend/api/public/compound/15377"
WORKFLOW_COMPOUND_URL = "https://www.ebi.ac.uk/chebi/backend/api/public/compound/CHEBI%3A15377"
WORKFLOW_SEARCH_URL = "https://www.ebi.ac.uk/chebi/backend/api/public/es_search/"


@pytest.fixture
def interface(tmp_path):
    return ChEBIInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_builds_url_and_returns_compound(interface, mocked_responses):
    body = load_fixture("chebi", "compound")
    mocked_responses.add(responses.GET, COMPOUND_URL, json=body, status=200)

    result = interface.fetch("15377", method="compound")

    assert result == body
    assert len(mocked_responses.calls) == 1
    assert mocked_responses.calls[0].request.url.startswith(COMPOUND_URL)


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("chebi", "compound")
    parsed = interface.parse(body, fields_to_extract=["chebi_accession", "name"])

    assert parsed == {"chebi_accession": body["chebi_accession"], "name": body["name"]}


def test_fetch_single_round_trips_through_cache(interface, mocked_responses):
    body = load_fixture("chebi", "compound")
    mocked_responses.add(responses.GET, COMPOUND_URL, json=body, status=200)

    first, _ = interface.fetch_single("15377", method="compound")
    second, _ = interface.fetch_single("15377", method="compound")

    assert len(mocked_responses.calls) == 1
    assert first == second


def test_fetch_single_compound_builds_workflow_chebi_id_url_and_metadata(
    interface,
    mocked_responses,
):
    body = load_fixture("chebi", "workflow_compound")
    mocked_responses.add(responses.GET, WORKFLOW_COMPOUND_URL, json=body, status=200)

    result, metadata = interface.fetch_single("CHEBI:15377", method="compound")

    assert result == body
    assert len(mocked_responses.calls) == 1
    assert mocked_responses.calls[0].request.url.startswith(WORKFLOW_COMPOUND_URL)
    assert metadata["api_name"] == "ChEBI"
    assert metadata["method"] == "compound"
    assert metadata["fetched_length"] == 1
    assert metadata["data_info"]["total_entries"] == 1


def test_fetch_single_es_search_builds_url_params_and_unwraps_results(
    interface,
    mocked_responses,
):
    body = load_fixture("chebi", "workflow_entity_search")
    mocked_responses.add(responses.GET, WORKFLOW_SEARCH_URL, json=body, status=200)

    result, metadata = interface.fetch_single(
        {"term": "caffeine", "page": 1, "size": 100},
        method="es_search",
    )

    request = mocked_responses.calls[0].request
    query_params = parse_qs(urlparse(request.url).query)
    assert result == body["results"]
    assert request.url.startswith(WORKFLOW_SEARCH_URL)
    assert query_params == {"term": ["caffeine"], "page": ["1"], "size": ["100"]}
    assert metadata["api_name"] == "ChEBI"
    assert metadata["method"] == "es_search"
    assert metadata["fetched_length"] == 1
    assert metadata["data_info"]["total_entries"] == 1


def test_fetch_single_es_search_uses_cache_on_second_call(interface, mocked_responses):
    body = load_fixture("chebi", "workflow_entity_search")
    query = {"term": "caffeine", "page": 1, "size": 100}
    mocked_responses.add(responses.GET, WORKFLOW_SEARCH_URL, json=body, status=200)

    first, first_metadata = interface.fetch_single(query, method="es_search")
    second, second_metadata = interface.fetch_single(query, method="es_search")

    assert first == second
    assert len(mocked_responses.calls) == 1
    assert first_metadata["fetched_ids"]
    assert second_metadata["cached_ids"]


def test_fetch_single_es_search_page_size_are_part_of_cache_identity(interface, mocked_responses):
    body = load_fixture("chebi", "workflow_entity_search")
    mocked_responses.add(responses.GET, WORKFLOW_SEARCH_URL, json=body, status=200)
    mocked_responses.add(responses.GET, WORKFLOW_SEARCH_URL, json=body, status=200)

    interface.fetch_single({"term": "caffeine", "page": 1, "size": 100}, method="es_search")
    interface.fetch_single({"term": "caffeine", "page": 2, "size": 100}, method="es_search")

    assert len(mocked_responses.calls) == 2
