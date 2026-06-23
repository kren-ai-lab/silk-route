"""Offline tests for the ChEMBL interface (paginated activity endpoint)."""

from __future__ import annotations

import pytest
from niquests_mock import startswith

from bioseq_dl.core.interfaces.chembl import ChEMBLInterface
from tests._helpers import load_fixture
from tests.core.interfaces._contract import CachingContract

ACTIVITY_URL = "https://www.ebi.ac.uk/chembl/api/data/activity"


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
