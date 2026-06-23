"""Offline tests for the UniProt interface.

UniProt subclasses BaseAPIInterface but keeps a bespoke multi-step id-mapping
flow: submit -> poll status -> resolve link -> fetch results. We replay that
sequence with ``responses``, plus a direct parse-shape test.
"""

from __future__ import annotations

import pytest
from niquests_mock import startswith

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


def test_parse_aggregates_field_coverage_across_records(interface):
    results = load_fixture("uniprot", "idmapping_results")
    fields = ["accession", "organism", "length"]
    _, metadata = interface.parse(results, extract_fields=fields)

    # Aggregate (not first-record) metadata: requested fields, record count, and
    # per-field non-null coverage.
    assert metadata["requested_fields"] == fields
    assert metadata["records"] == len(results["results"])
    assert metadata["failed_records"] == len(results.get("failedIds", []))
    assert set(metadata["field_coverage"]) == set(fields)
    # Every coverage count is bounded by the number of records.
    assert all(0 <= n <= metadata["records"] for n in metadata["field_coverage"].values())


def test_parse_counts_failed_ids_as_failed_records(interface):
    results = {"results": [], "failedIds": ["BADID1", "BADID2"]}
    _, metadata = interface.parse(results, extract_fields=["accession"])

    assert metadata["records"] == 0
    assert metadata["failed_records"] == 2


def test_submit_id_mapping_posts_and_returns_job_id(interface, niquests_mock):
    niquests_mock.post(url=startswith(f"{API_URL}/idmapping/run")).respond(
        status_code=200, json={"jobId": "JOB123"}
    )

    job_id = interface.submit_id_mapping("UniProtKB_AC-ID", "UniProtKB", ["P12345"])

    assert job_id == "JOB123"
    sent = niquests_mock.calls[0].request.body
    assert "from=UniProtKB_AC-ID" in sent
    assert "ids=P12345" in sent


def test_id_mapping_flow_resolves_and_fetches_results(interface, niquests_mock):
    results = load_fixture("uniprot", "idmapping_results")
    job = "JOB123"
    link = f"{API_URL}/idmapping/uniprotkb/results/{job}"

    niquests_mock.get(url=startswith(f"{API_URL}/idmapping/status/{job}")).respond(
        status_code=200, json=results
    )
    niquests_mock.get(url=startswith(f"{API_URL}/idmapping/details/{job}")).respond(
        status_code=200, json={"redirectURL": link}
    )
    niquests_mock.get(url=startswith(link)).respond(
        status_code=200, json=results, headers={"x-total-results": "1"}
    )

    assert interface.check_id_mapping_results_ready(job) is True
    resolved = interface.get_id_mapping_results_link(job)
    assert resolved == link

    fetched = interface.get_id_mapping_results_search(resolved)
    assert fetched["results"][0]["from"] == "P12345"
