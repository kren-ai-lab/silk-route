"""Offline tests for the KEGG interface (text/flat-file responses)."""

from __future__ import annotations

from typing import ClassVar

import pytest
from niquests_mock import startswith

from silkroute.core.interfaces.kegg import KEGGInterface
from tests._helpers import load_fixture
from tests.core.interfaces._contract import CachingContract, HttpErrorContract

GET_URL = "https://rest.kegg.jp/get/hsa:10458"


@pytest.fixture
def interface(tmp_path):
    return KEGGInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_splits_flatfile_entries(interface, niquests_mock):
    text = load_fixture("kegg", "get")
    niquests_mock.get(url=startswith(GET_URL)).respond(status_code=200, text=text)

    result = interface.fetch({"entries": "hsa:10458"}, method="get")

    # `get` returns a list of flat-file entry blocks (trailing "///" stripped).
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].startswith("ENTRY")
    assert "///" not in result[0]
    assert niquests_mock.calls[0].request.url == GET_URL


def test_parse_builds_keyed_entry(interface):
    text = load_fixture("kegg", "get")
    entry = text.split("\n///")[0]
    parsed = interface.parse(entry, method="get")

    assert isinstance(parsed, dict)
    assert "10458" in parsed["ENTRY"]
    assert "NAME" in parsed


class TestKeggContract(CachingContract, HttpErrorContract):
    INTERFACE_URL = GET_URL
    QUERY = {"entries": "hsa:10458"}
    METHOD = "get"
    FIXTURE = ("kegg", "get")
    BODY_IS_TEXT = True
    ERROR_RETURNS_EMPTY = True
    ERROR_EMPTY_VALUE: ClassVar[list] = []  # fetch returns a list of records
