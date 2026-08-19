"""Offline tests for the UniProt interface.

UniProt subclasses BaseAPIInterface but keeps a bespoke multi-step id-mapping
flow: submit -> poll status -> resolve link -> fetch results. We replay that
sequence with ``responses``, plus a direct parse-shape test.
"""

from __future__ import annotations

import polars as pl
import pytest
from niquests_mock import startswith

from silkroute.core.interfaces.uniprot import API_URL, UniprotInterface
from silkroute.core.metadata import FetchMetadata
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
