"""Offline tests for the STRING interface."""

from __future__ import annotations

import pytest
from niquests_mock import startswith

from silkroute.core.interfaces.stringdb import StringInterface
from tests._helpers import load_fixture
from tests.core.interfaces._contract import CachingContract, HttpErrorContract

IDS_URL = "https://string-db.org/api/json/get_string_ids"


@pytest.fixture
def interface(tmp_path):
    return StringInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_builds_url_with_format_segment(interface, niquests_mock):
    body = load_fixture("stringdb", "get_string_ids")
    niquests_mock.get(url=startswith(IDS_URL)).respond(status_code=200, json=body)

    result = interface.fetch({"identifiers": "TP53", "species": 9606}, method="get_string_ids")

    assert result == body
    assert len(niquests_mock.calls) == 1
    sent = niquests_mock.calls[0].request.url
    assert sent.startswith(IDS_URL)
    assert "identifiers=TP53" in sent
    assert "species=9606" in sent


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("stringdb", "get_string_ids")
    parsed = interface.parse(body, fields_to_extract=["stringId", "preferredName"])

    assert isinstance(parsed, list)
    assert parsed[0] == {"stringId": "9606.ENSP00000269305", "preferredName": "TP53"}


class TestStringdbContract(CachingContract, HttpErrorContract):
    INTERFACE_URL = IDS_URL
    QUERY = {"identifiers": "TP53", "species": 9606}
    METHOD = "get_string_ids"
    FIXTURE = ("stringdb", "get_string_ids")
