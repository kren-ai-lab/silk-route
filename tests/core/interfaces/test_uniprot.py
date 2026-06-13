"""Offline tests for the UniProt interface.

UniProt is standalone (not a BaseAPIInterface) and uses a multi-step id-mapping
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
