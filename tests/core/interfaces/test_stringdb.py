"""Offline tests for the STRING interface."""

from __future__ import annotations

import pytest
import responses

from bioseq_dl.core.interfaces.stringdb import StringInterface
from tests._helpers import load_fixture

IDS_URL = "https://string-db.org/api/json/get_string_ids"


@pytest.fixture
def interface(tmp_path):
    return StringInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_builds_url_with_format_segment(interface, mocked_responses):
    body = load_fixture("stringdb", "get_string_ids")
    mocked_responses.add(responses.GET, IDS_URL, json=body, status=200)

    result = interface.fetch({"identifiers": "TP53", "species": 9606}, method="get_string_ids")

    assert result == body
    assert len(mocked_responses.calls) == 1
    sent = mocked_responses.calls[0].request.url
    assert sent.startswith(IDS_URL)
    assert "identifiers=TP53" in sent
    assert "species=9606" in sent


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("stringdb", "get_string_ids")
    parsed = interface.parse(body, fields_to_extract=["stringId", "preferredName"])

    assert isinstance(parsed, list)
    assert parsed[0] == {"stringId": "9606.ENSP00000269305", "preferredName": "TP53"}


def test_fetch_single_round_trips_through_cache(interface, mocked_responses):
    body = load_fixture("stringdb", "get_string_ids")
    mocked_responses.add(responses.GET, IDS_URL, json=body, status=200)

    query = {"identifiers": "TP53", "species": 9606}
    first, _ = interface.fetch_single(query, method="get_string_ids")
    second, _ = interface.fetch_single(query, method="get_string_ids")

    assert len(mocked_responses.calls) == 1
    assert first == second
