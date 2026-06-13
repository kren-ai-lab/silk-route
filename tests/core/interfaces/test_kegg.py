"""Offline tests for the KEGG interface (text/flat-file responses)."""

from __future__ import annotations

import pytest
import responses

from bioseq_dl.core.interfaces.kegg import KEGGInterface
from tests._helpers import load_fixture

GET_URL = "https://rest.kegg.jp/get/hsa:10458"


@pytest.fixture
def interface(tmp_path):
    return KEGGInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_splits_flatfile_entries(interface, mocked_responses):
    text = load_fixture("kegg", "get")
    mocked_responses.add(responses.GET, GET_URL, body=text, status=200)

    result = interface.fetch({"entries": "hsa:10458"}, method="get")

    # `get` returns a list of flat-file entry blocks (trailing "///" stripped).
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].startswith("ENTRY")
    assert "///" not in result[0]
    assert mocked_responses.calls[0].request.url == GET_URL


def test_parse_builds_keyed_entry(interface):
    text = load_fixture("kegg", "get")
    entry = text.split("\n///")[0]
    parsed = interface.parse(entry, method="get")

    assert isinstance(parsed, dict)
    assert "10458" in parsed["ENTRY"]
    assert "NAME" in parsed


def test_fetch_single_round_trips_through_cache(interface, mocked_responses):
    text = load_fixture("kegg", "get")
    mocked_responses.add(responses.GET, GET_URL, body=text, status=200)

    first, _ = interface.fetch_single({"entries": "hsa:10458"}, method="get")
    second, _ = interface.fetch_single({"entries": "hsa:10458"}, method="get")

    assert len(mocked_responses.calls) == 1
    assert first == second
