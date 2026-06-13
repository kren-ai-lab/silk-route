"""Offline tests for the Rhea interface."""

from __future__ import annotations

import pytest
import responses

from bioseq_dl.core.interfaces.rhea import RheaInterface
from tests._helpers import load_fixture

API_URL = "https://www.rhea-db.org/rhea/"


@pytest.fixture
def interface(tmp_path):
    return RheaInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_builds_url_and_returns_results(interface, mocked_responses):
    body = load_fixture("rhea", "reaction")
    mocked_responses.add(responses.GET, API_URL, json=body, status=200)

    result = interface.fetch("RHEA:10000", method="rhea")

    # fetch unwraps the "results" envelope.
    assert result == body["results"]

    # Request was built against the right URL with the expected params.
    assert len(mocked_responses.calls) == 1
    sent = mocked_responses.calls[0].request.url
    assert sent.startswith(API_URL)
    assert "query=RHEA%3A10000" in sent
    assert "format=json" in sent
    assert "limit=100" in sent


def test_parse_returns_records_with_expected_keys(interface):
    body = load_fixture("rhea", "reaction")
    record = body["results"][0]
    parsed = interface.parse([record], fields_to_extract=["id", "equation", "status"])

    assert isinstance(parsed, list)
    assert parsed[0] == {k: record[k] for k in ("id", "equation", "status")}


def test_fetch_single_round_trips_through_cache(interface, mocked_responses):
    body = load_fixture("rhea", "reaction")
    mocked_responses.add(responses.GET, API_URL, json=body, status=200)

    first, _ = interface.fetch_single("RHEA:10000", method="rhea")
    second, _ = interface.fetch_single("RHEA:10000", method="rhea")

    # Second call served from cache: only one network request total.
    assert len(mocked_responses.calls) == 1
    assert first == second
