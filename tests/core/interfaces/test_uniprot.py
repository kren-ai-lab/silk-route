"""Offline tests for the UniProt interface.

UniProt subclasses BaseAPIInterface but keeps a bespoke multi-step id-mapping
flow: submit -> poll status -> resolve link -> fetch results. We replay that
sequence with ``responses``, plus a direct parse-shape test.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import polars as pl
import pytest
from niquests.exceptions import ConnectionError as NiquestsConnectionError
from niquests_mock import build_response, startswith

from silkroute.core.exceptions import RequestError
from silkroute.core.interfaces import uniprot as uniprot_module
from silkroute.core.interfaces.uniprot import API_URL, SEARCH_PAGE_SIZE, UniprotInterface
from silkroute.core.metadata import FetchMetadata
from tests._helpers import load_fixture

SEARCH_URL = f"{API_URL}/uniprotkb/search"


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


def test_parse_explicit_fields_excludes_nested_unrequested_fields(interface):
    results = {
        "results": [
            {
                "primaryAccession": "P12345",
                "proteinDescription": {
                    "recommendedName": {
                        "fullName": {"value": "Example enzyme"},
                        "ecNumbers": [{"value": "1.2.3.4"}],
                    }
                },
                "sequence": {"value": "MPEPTIDE", "length": 8},
            }
        ]
    }

    parsed, _ = interface.parse(
        results,
        extract_fields=["accession", "protein_name", "sequence"],
        format="dataframe",
    )

    assert parsed.columns == ["accession", "protein_name", "sequence"]
    assert parsed.to_dicts() == [
        {"accession": "P12345", "protein_name": "Example enzyme", "sequence": "MPEPTIDE"}
    ]


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


def test_submit_stream_returns_fetchmetadata_shape(interface, niquests_mock):
    # UniProt fetch metadata is normalized onto FetchMetadata so it matches every
    # other source's block (#2): common envelope + UniProt detail under `extra`.
    results = load_fixture("uniprot", "idmapping_results")
    niquests_mock.get(url=startswith(f"{API_URL}/uniprotkb/stream")).respond(
        status_code=200, json=results, headers={"Content-Length": "123"}
    )

    _, metadata = interface.submit_stream(query="kinase", fields="accession", sort="")

    assert metadata["tool"]["name"] == "silkroute"
    assert metadata["request"] == {"api_name": "UniProt", "method": "uniprotkb", "option": None}
    assert metadata["started_at"]
    assert metadata["finished_at"]
    assert set(metadata) >= {"tool", "request", "cached", "fetched", "failed", "data_info", "extra"}
    assert metadata["extra"]["status_code"] == 200
    assert metadata["extra"]["query"] == "kinase"


def test_submit_search_fetches_single_page_with_expected_parameters(interface, niquests_mock):
    requested_urls = []

    def serve_page(request):
        requested_urls.append(request.url)
        return build_response(
            request,
            status_code=200,
            json={"results": [{"primaryAccession": "P12345"}]},
            headers={"x-total-results": "1"},
        )

    niquests_mock.get(url=startswith(SEARCH_URL)).mock(side_effect=serve_page)

    payload, metadata = interface.submit_search(
        query="taxonomy_id:2731619",
        fields="accession,protein_name,sequence",
        sort="accession desc",
        include_isoform=True,
    )

    assert payload == {"results": [{"primaryAccession": "P12345"}]}
    assert len(requested_urls) == 1
    parsed_url = urlparse(requested_urls[0])
    assert parsed_url.path == "/uniprotkb/search"
    assert parse_qs(parsed_url.query) == {
        "query": ["taxonomy_id:2731619"],
        "fields": ["accession, protein_name, sequence"],
        "sort": ["accession desc"],
        "includeIsoform": ["True"],
        "format": ["json"],
        "size": [str(SEARCH_PAGE_SIZE)],
    }
    assert metadata["extra"]["pages_fetched"] == 1
    assert metadata["extra"]["records_fetched"] == 1
    assert metadata["extra"]["total_results"] == 1


def test_submit_search_follows_complete_next_urls_and_preserves_page_order(interface, niquests_mock):
    next_url_1 = f"{SEARCH_URL}?cursor=cursor-one&format=json&size=500"
    next_url_2 = f"{SEARCH_URL}?cursor=cursor-two&format=json&size=500"
    requested_urls = []

    def serve_page(request):
        requested_urls.append(request.url)
        cursor = parse_qs(urlparse(request.url).query).get("cursor", [None])[0]
        if cursor is None:
            return build_response(
                request,
                json={"results": [{"primaryAccession": "P1"}]},
                headers={"Link": f'<{next_url_1}>; rel="next"'},
            )
        if cursor == "cursor-one":
            return build_response(
                request,
                json={"results": [{"primaryAccession": "P2"}], "failedIds": ["BAD1"]},
                headers={"Link": f'<{next_url_2}>; rel="next"'},
            )
        return build_response(request, json={"results": [{"primaryAccession": "P3"}]})

    niquests_mock.get(url=startswith(SEARCH_URL)).mock(side_effect=serve_page)

    payload, metadata = interface.submit_search(query="kinase", fields="accession", sort="accession asc")

    assert [record["primaryAccession"] for record in payload["results"]] == ["P1", "P2", "P3"]
    assert payload["failedIds"] == ["BAD1"]
    assert requested_urls[1:] == [next_url_1, next_url_2]
    assert metadata["extra"]["pages_fetched"] == 3
    assert metadata["extra"]["records_fetched"] == 3
    assert "total_results" not in metadata["extra"]


def test_submit_search_retries_only_the_failed_current_page(monkeypatch, niquests_mock):
    interface = UniprotInterface(total_retries=2)
    next_url = f"{SEARCH_URL}?cursor=retry-page&format=json&size=500"
    requested_urls = []
    page_two_attempts = 0

    def serve_page(request):
        nonlocal page_two_attempts
        requested_urls.append(request.url)
        if request.url == next_url:
            page_two_attempts += 1
            if page_two_attempts == 1:
                raise NiquestsConnectionError("connection reset")
            return build_response(request, json={"results": [{"primaryAccession": "P2"}]})
        return build_response(
            request,
            json={"results": [{"primaryAccession": "P1"}]},
            headers={"Link": f'<{next_url}>; rel="next"'},
        )

    monkeypatch.setattr(uniprot_module.time, "sleep", lambda _seconds: None)
    niquests_mock.get(url=startswith(SEARCH_URL)).mock(side_effect=serve_page)

    payload, metadata = interface.submit_search(query="kinase", fields="accession", sort="accession asc")

    assert [record["primaryAccession"] for record in payload["results"]] == ["P1", "P2"]
    assert sum(url.startswith(f"{SEARCH_URL}?") and "cursor=" not in url for url in requested_urls) == 1
    assert requested_urls.count(next_url) == 2
    assert metadata["extra"]["pages_fetched"] == 2
    assert metadata["extra"]["attempts"] == 3


def test_submit_search_raises_when_current_page_exhausts_retries(monkeypatch, niquests_mock):
    interface = UniprotInterface(total_retries=2)
    next_url = f"{SEARCH_URL}?cursor=broken-page&format=json&size=500"
    requested_urls = []

    def serve_page(request):
        requested_urls.append(request.url)
        if request.url == next_url:
            raise NiquestsConnectionError("connection reset")
        return build_response(
            request,
            json={"results": [{"primaryAccession": "P1"}]},
            headers={"Link": f'<{next_url}>; rel="next"'},
        )

    monkeypatch.setattr(uniprot_module.time, "sleep", lambda _seconds: None)
    niquests_mock.get(url=startswith(SEARCH_URL)).mock(side_effect=serve_page)

    with pytest.raises(RequestError, match="search page 2 failed after 2 attempts"):
        interface.submit_search(query="kinase", fields="accession", sort="accession asc")

    assert sum(url.startswith(f"{SEARCH_URL}?") and "cursor=" not in url for url in requested_urls) == 1
    assert requested_urls.count(next_url) == 2


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


def test_identify_id_type_matches_uniprot_and_pdb(interface):
    # Regression: the matcher used to bail after the first pattern, classifying
    # everything as "unknown". It must scan all patterns across all db types.
    assert interface.identify_id_type("P12345") == "uniprot"
    assert interface.identify_id_type("1ABC") == "pdb"
    assert interface.identify_id_type("???") == ""


def test_download_batch_auto_db_accumulates_all_groups(interface, monkeypatch):
    # auto_db routes mixed IDs through the REAL grouping (P12345 -> uniprot,
    # 1ABC -> pdb); every group's results + metadata must be accumulated
    # (previously only the last group survived). Only the network call is stubbed.
    def fake_process(ids, from_db, to_db, batch_size, db_type):
        meta = FetchMetadata()
        meta.fetched.add(ids[0], {"id": ids[0]})
        meta.extra.update({"num_batches": 1, "failed_ids_count": 0})
        meta.data_info = {"total_entries": 1}
        return [{"results": [{"id": ids[0], "source_db": db_type}]}], meta.to_dict()

    monkeypatch.setattr(interface, "process_id_batch", fake_process)

    df = pl.DataFrame({"id": ["P12345", "1ABC", "???"]})
    results, metadata = interface.download_batch(df, "id", auto_db=True)

    # Both valid groups contributed results (unknown "???" is skipped).
    source_dbs = {r["source_db"] for res in results for r in res["results"]}
    assert source_dbs == {"uniprot", "pdb"}
    # Metadata merged across groups + per-group breakdown exposed.
    assert metadata["fetched"]["length"] == 2
    assert metadata["data_info"]["total_entries"] == 2
    assert {g["db_type"] for g in metadata["extra"]["groups"]} == {"uniprot", "pdb"}
