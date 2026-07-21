"""Offline tests for the ChEMBL interface (paginated activity endpoint)."""

from __future__ import annotations

import pytest
from niquests_mock import startswith

from bioseq_dl.core.interfaces.chembl import ChEMBLInterface
from tests._helpers import load_fixture
from tests.core.interfaces._contract import CachingContract

ACTIVITY_URL = "https://www.ebi.ac.uk/chembl/api/data/activity"
MOLECULE_URL = "https://www.ebi.ac.uk/chembl/api/data/molecule"


class PaginatedResponse:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class PaginatedSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def get(self, url, **_kwargs):
        self.urls.append(url)
        return self.responses.pop(0)


@pytest.fixture
def interface(tmp_path):
    return ChEMBLInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_unwraps_activities_list(interface, niquests_mock):
    body = load_fixture("chembl", "activity")
    niquests_mock.get(url=startswith(ACTIVITY_URL)).respond(status_code=200, json=body)

    result = interface.fetch({"target_chembl_id": "CHEMBL279"}, method="activity")

    # fetch_pages flattens the "activities" page into a list of records.
    assert result == body["activities"]
    assert len(niquests_mock.calls) == 1
    sent = niquests_mock.calls[0].request.url
    assert sent.startswith(ACTIVITY_URL)
    assert "target_chembl_id=CHEMBL279" in sent


def test_fetch_activity_follows_successful_pagination(interface):
    interface.session = PaginatedSession(
        [
            PaginatedResponse(
                {
                    "activities": [{"activity_id": 1}],
                    "page_meta": {"next": "/chembl/api/data/activity?page=2"},
                }
            ),
            PaginatedResponse({"activities": [{"activity_id": 2}], "page_meta": {"next": None}}),
        ]
    )

    result = interface.fetch({"target_chembl_id": "CHEMBL279"}, method="activity", pages_to_fetch=-1)

    assert result == [{"activity_id": 1}, {"activity_id": 2}]
    assert len(interface.session.urls) == 2


def test_fetch_activity_accepts_catalog_flat_filters(interface, niquests_mock):
    # GUI-built activity queries carry catalog fields with operator suffixes.
    body = load_fixture("chembl", "activity")
    niquests_mock.get(url=startswith(ACTIVITY_URL)).respond(status_code=200, json=body)

    interface.fetch({"standard_type": "IC50", "standard_value__lte": "100"}, method="activity")

    sent = niquests_mock.calls[0].request.url
    assert "standard_type=IC50" in sent
    assert "standard_value__lte=100" in sent


def test_fetch_activity_rejects_field_outside_catalog(interface, niquests_mock):
    # Unknown activity fields must fail validation and short-circuit to an empty result.
    result = interface.fetch({"bogus_field": "x"}, method="activity")

    assert result == []
    assert len(niquests_mock.calls) == 0


def test_fetch_molecule_filters_builds_filtered_url(interface, niquests_mock):
    # Filter-list resources must serialize catalog operators into a well-formed URL.
    niquests_mock.get(url=startswith(MOLECULE_URL)).respond(status_code=200, json={"molecules": []})

    interface.fetch(
        {"filters": [{"field": "molecular_weight", "filter_type": "gt", "value": "300"}]},
        method="molecule",
    )

    sent = niquests_mock.calls[0].request.url
    assert "molecular_weight__gt=300" in sent
    # Filters and pagination params must be joined with '&', not concatenated.
    assert "&limit=" in sent
    assert "&format=json" in sent


def test_fetch_single_activity_preserves_flat_filters(interface, niquests_mock):
    # fetch_single strips undeclared keys via _prepare_params; catalog filters must survive.
    body = load_fixture("chembl", "activity")
    niquests_mock.get(url=startswith(ACTIVITY_URL)).respond(status_code=200, json=body)

    interface.fetch_single(
        {"standard_type": "IC50", "standard_value__lte": "100"}, method="activity", format="json"
    )

    sent = niquests_mock.calls[0].request.url
    assert "standard_type=IC50" in sent
    assert "standard_value__lte=100" in sent


def test_fetch_single_activity_filters_do_not_collide_in_cache(interface, niquests_mock):
    # Distinct flat-filter sets must yield distinct cache identifiers (not one shared key).
    body = load_fixture("chembl", "activity")
    niquests_mock.get(url=startswith(ACTIVITY_URL)).respond(status_code=200, json=body)

    interface.fetch_single({"standard_type": "IC50"}, method="activity", format="json")
    interface.fetch_single({"standard_type": "Ki"}, method="activity", format="json")

    assert len(niquests_mock.calls) == 2


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("chembl", "activity")
    activity = body["activities"][0]
    parsed = interface.parse(activity, fields_to_extract=["molecule_chembl_id", "standard_type"])

    assert parsed == {k: activity[k] for k in ("molecule_chembl_id", "standard_type")}


class TestChemblContract(CachingContract):
    INTERFACE_URL = ACTIVITY_URL
    QUERY = {"target_chembl_id": "CHEMBL279"}
    METHOD = "activity"
    FIXTURE = ("chembl", "activity")
