"""Offline tests for the ChEMBL interface (paginated activity endpoint)."""

from __future__ import annotations

import pytest
import responses

from bioseq_dl.core.interfaces.chembl import ChEMBLInterface
from tests._helpers import load_fixture

ACTIVITY_URL = "https://www.ebi.ac.uk/chembl/api/data/activity"


@pytest.fixture
def interface(tmp_path):
    return ChEMBLInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_unwraps_activities_list(interface, mocked_responses):
    body = load_fixture("chembl", "activity")
    mocked_responses.add(responses.GET, ACTIVITY_URL, json=body, status=200)

    result = interface.fetch({"target_chembl_id": "CHEMBL279"}, method="activity")

    # fetch_pages flattens the "activities" page into a list of records.
    assert result == body["activities"]
    assert len(mocked_responses.calls) == 1
    sent = mocked_responses.calls[0].request.url
    assert sent.startswith(ACTIVITY_URL)
    assert "target_chembl_id=CHEMBL279" in sent


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("chembl", "activity")
    activity = body["activities"][0]
    parsed = interface.parse(activity, fields_to_extract=["molecule_chembl_id", "standard_type"])

    assert parsed == {k: activity[k] for k in ("molecule_chembl_id", "standard_type")}


def test_fetch_single_round_trips_through_cache(interface, mocked_responses):
    body = load_fixture("chembl", "activity")
    mocked_responses.add(responses.GET, ACTIVITY_URL, json=body, status=200)

    query = {"target_chembl_id": "CHEMBL279"}
    first, _ = interface.fetch_single(query, method="activity")
    second, _ = interface.fetch_single(query, method="activity")

    assert len(mocked_responses.calls) == 1
    assert first == second
