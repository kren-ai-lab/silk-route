"""Offline tests for the PubChem interface (PUG-View path)."""

from __future__ import annotations

import re
from urllib.parse import parse_qs

import pytest
import responses

from bioseq_dl.core.interfaces.pubchem import (
    WORKFLOW_COMPOUND_PROPERTIES,
    WORKFLOW_COMPOUND_PROPERTIES_METHOD,
    PubChemInterface,
)
from tests._helpers import load_fixture

# Note the double slash: API_URL ends with "/" and the pug_view branch prepends "/pug_view".
COMPOUND_URL = "https://pubchem.ncbi.nlm.nih.gov/rest//pug_view/data/compound/444444/JSON"
WORKFLOW_BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"


@pytest.fixture
def interface(tmp_path):
    return PubChemInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_builds_url_and_returns_record(interface, mocked_responses):
    body = load_fixture("pubchem", "pug_view_compound")
    mocked_responses.add(responses.GET, COMPOUND_URL, json=body, status=200)

    result = interface.fetch({"cid": "444444"}, method="pug_view/compound", option="default")

    assert result == body
    assert len(mocked_responses.calls) == 1
    assert mocked_responses.calls[0].request.url == COMPOUND_URL


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("pubchem", "pug_view_compound")
    parsed = interface.parse(
        body, fields_to_extract={"default": {"title": "Record.RecordTitle"}}, option="default"
    )

    assert parsed == {"title": body["Record"]["RecordTitle"]}


def test_fetch_single_round_trips_through_cache(interface, mocked_responses):
    body = load_fixture("pubchem", "pug_view_compound")
    mocked_responses.add(responses.GET, COMPOUND_URL, json=body, status=200)

    query = {"cid": "444444"}
    first, _ = interface.fetch_single(query, method="pug_view/compound", option="default")
    second, _ = interface.fetch_single(query, method="pug_view/compound", option="default")

    assert len(mocked_responses.calls) == 1
    assert first == second


def test_workflow_fetch_single_builds_cid_lookup_url_and_returns_metadata(interface, mocked_responses):
    body = load_fixture("pubchem", "workflow_compound_properties")
    expected_url = f"{WORKFLOW_BASE_URL}/cid/5793/property/{WORKFLOW_COMPOUND_PROPERTIES}/JSON"
    mocked_responses.add(responses.GET, expected_url, json=body, status=200)

    result, metadata = interface.fetch_single(
        {"namespace": "cid", "identifier": "5793", "search_mode": "lookup"},
        method=WORKFLOW_COMPOUND_PROPERTIES_METHOD,
    )

    assert result == body["PropertyTable"]["Properties"]
    assert len(mocked_responses.calls) == 1
    assert mocked_responses.calls[0].request.url == expected_url
    assert metadata["api_name"] == "PubChem"
    assert metadata["method"] == WORKFLOW_COMPOUND_PROPERTIES_METHOD
    assert metadata["fetched_length"] == 1
    assert metadata["data_info"]["total_entries"] == 1


def test_workflow_fetch_single_builds_name_lookup_url(interface, mocked_responses):
    body = load_fixture("pubchem", "workflow_compound_properties")
    expected_url = f"{WORKFLOW_BASE_URL}/name/glucose/property/{WORKFLOW_COMPOUND_PROPERTIES}/JSON"
    mocked_responses.add(responses.GET, expected_url, json=body, status=200)

    result, _metadata = interface.fetch_single(
        {"namespace": "name", "identifier": "glucose", "search_mode": "lookup"},
        method=WORKFLOW_COMPOUND_PROPERTIES_METHOD,
    )

    assert result == body["PropertyTable"]["Properties"]
    assert mocked_responses.calls[0].request.url == expected_url


def test_workflow_fetch_single_builds_inchi_lookup_post(interface, mocked_responses):
    body = load_fixture("pubchem", "workflow_compound_properties")
    inchi = "InChI=1S/C6H12O6"
    expected_url = f"{WORKFLOW_BASE_URL}/inchi/property/{WORKFLOW_COMPOUND_PROPERTIES}/JSON"
    mocked_responses.add(responses.POST, expected_url, json=body, status=200)

    result, _metadata = interface.fetch_single(
        {"namespace": "inchi", "identifier": inchi, "search_mode": "lookup"},
        method=WORKFLOW_COMPOUND_PROPERTIES_METHOD,
    )

    request = mocked_responses.calls[0].request
    assert result == body["PropertyTable"]["Properties"]
    assert request.method == "POST"
    assert request.url == expected_url
    assert parse_qs(str(request.body)) == {"inchi": [inchi]}
    assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"


def test_workflow_fetch_single_builds_inchikey_lookup_url(interface, mocked_responses):
    body = load_fixture("pubchem", "workflow_compound_properties")
    inchikey = "WQZGKKKJIJFFOK-GASJEMHNSA-N"
    expected_url = f"{WORKFLOW_BASE_URL}/inchikey/{inchikey}/property/{WORKFLOW_COMPOUND_PROPERTIES}/JSON"
    mocked_responses.add(responses.GET, expected_url, json=body, status=200)

    result, _metadata = interface.fetch_single(
        {"namespace": "inchikey", "identifier": inchikey, "search_mode": "lookup"},
        method=WORKFLOW_COMPOUND_PROPERTIES_METHOD,
    )

    assert result == body["PropertyTable"]["Properties"]
    assert mocked_responses.calls[0].request.url == expected_url


def test_workflow_identity_fetch_uses_official_fast_search_path(interface, mocked_responses):
    body = load_fixture("pubchem", "workflow_structure_search")
    smiles = "CC(=O)Oc1ccccc1C(=O)O"
    mocked_responses.add(
        responses.GET,
        re.compile(r"https://pubchem\.ncbi\.nlm\.nih\.gov/rest/pug/compound/fastidentity/.*"),
        json=body,
        status=200,
    )

    result, _metadata = interface.fetch_single(
        {
            "namespace": "smiles",
            "identifier": smiles,
            "search_mode": "identity",
            "max_records": 10,
        },
        method=WORKFLOW_COMPOUND_PROPERTIES_METHOD,
    )

    request = mocked_responses.calls[0].request
    assert result == body["PropertyTable"]["Properties"]
    assert "/fastidentity/smiles/" in request.url
    assert "MaxRecords=10" in request.url
    assert "/property/CID,MolecularFormula,MolecularWeight" in request.url


def test_workflow_substructure_fetch_uses_official_fast_search_path(interface, mocked_responses):
    body = load_fixture("pubchem", "workflow_compound_properties")
    mocked_responses.add(
        responses.GET,
        re.compile(r"https://pubchem\.ncbi\.nlm\.nih\.gov/rest/pug/compound/fastsubstructure/.*"),
        json=body,
        status=200,
    )

    result, _metadata = interface.fetch_single(
        {
            "namespace": "smiles",
            "identifier": "c1ccccc1",
            "search_mode": "substructure",
            "max_records": 25,
        },
        method=WORKFLOW_COMPOUND_PROPERTIES_METHOD,
    )

    assert result == body["PropertyTable"]["Properties"]
    request = mocked_responses.calls[0].request
    assert "/fastsubstructure/smiles/" in request.url
    assert "MaxRecords=25" in request.url
    assert "/property/CID,MolecularFormula,MolecularWeight" in request.url


def test_workflow_similarity_fetch_uses_threshold_query_param(interface, mocked_responses):
    body = load_fixture("pubchem", "workflow_compound_properties")
    mocked_responses.add(
        responses.GET,
        re.compile(r"https://pubchem\.ncbi\.nlm\.nih\.gov/rest/pug/compound/fastsimilarity_2d/.*"),
        json=body,
        status=200,
    )

    result, _metadata = interface.fetch_single(
        {
            "namespace": "cid",
            "identifier": "446157",
            "search_mode": "similarity_2d",
            "threshold": 80,
            "max_records": 50,
        },
        method=WORKFLOW_COMPOUND_PROPERTIES_METHOD,
    )

    request = mocked_responses.calls[0].request
    query_params = parse_qs(request.url.split("?", 1)[1])
    assert result == body["PropertyTable"]["Properties"]
    assert "/fastsimilarity_2d/cid/446157/" in request.url
    assert query_params == {"MaxRecords": ["50"], "Threshold": ["80"]}


def test_workflow_fetch_single_uses_cache_on_second_call(interface, mocked_responses):
    body = load_fixture("pubchem", "workflow_compound_properties")
    expected_url = f"{WORKFLOW_BASE_URL}/name/glucose/property/{WORKFLOW_COMPOUND_PROPERTIES}/JSON"
    query = {
        "namespace": "name",
        "identifier": "glucose",
        "search_mode": "lookup",
        "max_records": 100,
    }
    mocked_responses.add(responses.GET, expected_url, json=body, status=200)

    first, first_metadata = interface.fetch_single(query, method=WORKFLOW_COMPOUND_PROPERTIES_METHOD)
    second, second_metadata = interface.fetch_single(query, method=WORKFLOW_COMPOUND_PROPERTIES_METHOD)

    assert first == second
    assert len(mocked_responses.calls) == 1
    assert first_metadata["fetched_ids"]
    assert second_metadata["cached_ids"]


def test_workflow_fetch_single_allows_empty_property_records(interface, mocked_responses):
    body = {"PropertyTable": {"Properties": []}}
    expected_url = f"{WORKFLOW_BASE_URL}/name/missing/property/{WORKFLOW_COMPOUND_PROPERTIES}/JSON"
    mocked_responses.add(responses.GET, expected_url, json=body, status=200)

    result, metadata = interface.fetch_single(
        {"namespace": "name", "identifier": "missing", "search_mode": "lookup"},
        method=WORKFLOW_COMPOUND_PROPERTIES_METHOD,
    )

    assert result == []
    assert metadata["failed_ids"]
    assert metadata["data_info"]["total_entries"] == 0


def test_workflow_similarity_threshold_is_part_of_cache_identity(interface, mocked_responses):
    body = load_fixture("pubchem", "workflow_compound_properties")
    mocked_responses.add(
        responses.GET,
        re.compile(r"https://pubchem\.ncbi\.nlm\.nih\.gov/rest/pug/compound/fastsimilarity_2d/.*"),
        json=body,
        status=200,
    )
    mocked_responses.add(
        responses.GET,
        re.compile(r"https://pubchem\.ncbi\.nlm\.nih\.gov/rest/pug/compound/fastsimilarity_2d/.*"),
        json=body,
        status=200,
    )

    for threshold in (80, 95):
        interface.fetch_single(
            {
                "namespace": "cid",
                "identifier": "446157",
                "search_mode": "similarity_2d",
                "threshold": threshold,
                "max_records": 50,
            },
            method=WORKFLOW_COMPOUND_PROPERTIES_METHOD,
        )

    assert len(mocked_responses.calls) == 2


def test_workflow_request_plan_is_ignored_for_cache_identity(interface, mocked_responses):
    body = load_fixture("pubchem", "workflow_compound_properties")
    expected_url = f"{WORKFLOW_BASE_URL}/name/glucose/property/{WORKFLOW_COMPOUND_PROPERTIES}/JSON"
    query = {
        "namespace": "name",
        "identifier": "glucose",
        "search_mode": "lookup",
        "max_records": 100,
    }
    mocked_responses.add(responses.GET, expected_url, json=body, status=200)

    first, _first_metadata = interface.fetch_single(
        query,
        method=WORKFLOW_COMPOUND_PROPERTIES_METHOD,
        workflow_request_plan={"source": "pubchem", "parameters": {"name": "glucose"}},
    )
    second, second_metadata = interface.fetch_single(
        query,
        method=WORKFLOW_COMPOUND_PROPERTIES_METHOD,
        workflow_request_plan={"source": "pubchem", "parameters": {"name": "glucose"}, "note": "duplicate"},
    )

    assert first == second
    assert len(mocked_responses.calls) == 1
    assert second_metadata["cached_ids"]
