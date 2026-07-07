"""Offline tests for the ChEMBL interface (paginated activity endpoint)."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

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


def test_ic50_activity_filter_defaults_to_nm_and_uses_semi_open_range():
    activity_filter = ChEMBLInterface.extract_ic50_activity_filter(
        "ic50:0-10"
    )

    assert activity_filter == {
        "standard_type": "IC50",
        "standard_value_min": 0.0,
        "standard_value_max": 10.0,
        "standard_value_min_inclusive": True,
        "standard_value_max_inclusive": False,
        "standard_units": "nM",
    }
    assert ChEMBLInterface.build_activity_filter_params(activity_filter, limit=100) == {
        "standard_type": "IC50",
        "format": "json",
        "limit": 100,
        "standard_units": "nM",
        "standard_value__gte": "0",
        "standard_value__lt": "10",
    }


def test_ic50_activity_filter_defaults_unspecified_standard_units_to_nm():
    activity_filter = ChEMBLInterface.extract_ic50_activity_filter(
        "standard_type=IC50 AND standard_value<1000"
    )

    assert activity_filter is not None
    assert activity_filter["standard_units"] == "nM"
    assert ChEMBLInterface.build_activity_filter_params(activity_filter, limit=20)[
        "standard_units"
    ] == "nM"


def test_ic50_second_potency_range_uses_semi_open_url_params():
    activity_filter = ChEMBLInterface.extract_ic50_activity_filter("ic50:10-100")

    assert activity_filter is not None
    params = ChEMBLInterface.build_activity_filter_params(activity_filter, limit=100)
    assert params["standard_units"] == "nM"
    assert params["standard_value__gte"] == "10"
    assert params["standard_value__lt"] == "100"


def test_ic50_activity_filter_preserves_inclusive_comparison_with_units():
    activity_filter = ChEMBLInterface.extract_ic50_activity_filter(
        "standard_type=IC50 AND standard_value>=10 AND standard_units=uM"
    )

    assert activity_filter is not None
    assert activity_filter["standard_units"] == "uM"
    assert ChEMBLInterface.build_activity_filter_params(activity_filter, limit=None) == {
        "standard_type": "IC50",
        "format": "json",
        "standard_units": "uM",
        "standard_value__gte": "10",
    }


@pytest.mark.parametrize(
    ("query", "expected_param", "expected_value"),
    [
        ("ic50:>10", "standard_value__gt", "10"),
        ("ic50:>=10", "standard_value__gte", "10"),
        ("ic50:<1000", "standard_value__lt", "1000"),
        ("ic50:<=1000", "standard_value__lte", "1000"),
        ("ic50:50", "standard_value", "50"),
    ],
)
def test_ic50_explicit_macro_comparisons_remain_structured(
    query: str,
    expected_param: str,
    expected_value: str,
) -> None:
    activity_filter = ChEMBLInterface.extract_ic50_activity_filter(query)

    assert activity_filter is not None
    params = ChEMBLInterface.build_activity_filter_params(activity_filter, limit=None)
    assert params["standard_units"] == "nM"
    assert params[expected_param] == expected_value


def test_activity_search_endpoint_receives_standard_units(interface, monkeypatch):
    captured: dict[str, object] = {}

    def fake_fetch_pages(url: str, method: str, pages_to_fetch: int) -> list:
        captured.update(url=url, method=method, pages_to_fetch=pages_to_fetch)
        return []

    monkeypatch.setattr(interface, "fetch_pages", fake_fetch_pages)

    result = interface.fetch(
        "ic50:0-10",
        method="activity-search",
        limit=100,
        pages_to_fetch=1,
    )

    assert result == []
    assert captured["method"] == "activity-search"
    assert captured["pages_to_fetch"] == 1
    params = parse_qs(urlparse(str(captured["url"])).query)
    assert params == {
        "standard_type": ["IC50"],
        "format": ["json"],
        "limit": ["100"],
        "standard_units": ["nM"],
        "standard_value__gte": ["0"],
        "standard_value__lt": ["10"],
    }
