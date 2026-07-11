"""Offline tests for the UniProt interface.

UniProt subclasses BaseAPIInterface but keeps a bespoke multi-step id-mapping
flow: submit -> poll status -> resolve link -> fetch results. We replay that
sequence with ``responses``, plus a direct parse-shape test.
"""

from __future__ import annotations

import pytest
import responses

from bioseq_dl.core.interfaces.uniprot import API_URL, UniprotInterface
from tests._helpers import load_fixture


@pytest.fixture
def interface():
    return UniprotInterface()


def test_parse_extracts_requested_fields(interface):
    results = load_fixture("uniprot", "idmapping_results")
    entry = results["results"][0]["to"]
    parsed, _ = interface.parse(results, extract_fields=["accession", "organism", "length"])

    assert isinstance(parsed, list)
    assert parsed[0]["accession"] == entry["primaryAccession"]
    assert parsed[0]["organism"] == entry["organism"]["scientificName"]
    assert parsed[0]["length"] == entry["sequence"]["length"]


def test_submit_id_mapping_posts_and_returns_job_id(interface, mocked_responses):
    mocked_responses.add(responses.POST, f"{API_URL}/idmapping/run", json={"jobId": "JOB123"}, status=200)

    job_id = interface.submit_id_mapping("UniProtKB_AC-ID", "UniProtKB", ["P12345"])

    assert job_id == "JOB123"
    sent = mocked_responses.calls[0].request.body
    assert "from=UniProtKB_AC-ID" in sent
    assert "ids=P12345" in sent


def test_id_mapping_flow_resolves_and_fetches_results(interface, mocked_responses):
    results = load_fixture("uniprot", "idmapping_results")
    job = "JOB123"
    link = f"{API_URL}/idmapping/uniprotkb/results/{job}"

    mocked_responses.add(responses.GET, f"{API_URL}/idmapping/status/{job}", json=results, status=200)
    mocked_responses.add(
        responses.GET, f"{API_URL}/idmapping/details/{job}", json={"redirectURL": link}, status=200
    )
    mocked_responses.add(responses.GET, link, json=results, status=200, headers={"x-total-results": "1"})

    assert interface.check_id_mapping_results_ready(job) is True
    resolved = interface.get_id_mapping_results_link(job)
    assert resolved == link

    fetched = interface.get_id_mapping_results_search(resolved)
    assert fetched["results"][0]["from"] == "P12345"


def test_submit_stream_uses_search_endpoint_and_combines_results(interface, mocked_responses):
    first_page = {
        "results": [
            {"primaryAccession": "P00001"},
        ]
    }
    second_page = {
        "results": [
            {"primaryAccession": "P00002"},
        ]
    }
    next_link = f"{API_URL}/uniprotkb/search?cursor=next"
    mocked_responses.add(
        responses.GET,
        f"{API_URL}/uniprotkb/search",
        json=first_page,
        status=200,
        headers={"x-total-results": "2", "Link": f'<{next_link}>; rel="next"'},
    )
    mocked_responses.add(
        responses.GET,
        next_link,
        json=second_page,
        status=200,
    )

    payload, metadata = interface.submit_stream(
        query="reviewed:true",
        fields="accession",
        sort="accession asc",
    )

    assert [record["primaryAccession"] for record in payload["results"]] == ["P00001", "P00002"]
    assert "/uniprotkb/search" in mocked_responses.calls[0].request.url
    assert "/uniprotkb/stream" not in mocked_responses.calls[0].request.url
    assert metadata["search_process"]["endpoint_path"] == "/uniprotkb/search"
    assert metadata["search_process"]["total_results"] == 2
    assert metadata["search_process"]["retrieved_results"] == 2
