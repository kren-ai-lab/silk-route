"""Offline fetch/parse/cache tests for the InterPro interface."""

from __future__ import annotations

import pytest
from niquests_mock import startswith

from bioseq_dl.core.interfaces.interpro import InterproInterface
from tests._helpers import load_fixture
from tests.core.interfaces._contract import CachingContract, HttpErrorContract

ENTRY_URL = "https://www.ebi.ac.uk:443/interpro/api/entry/InterPro/IPR000001/"


@pytest.fixture
def interface(tmp_path):
    return InterproInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_builds_url_and_wraps_in_list(interface, niquests_mock):
    body = load_fixture("interpro", "entry")
    niquests_mock.get(url=startswith(ENTRY_URL)).respond(status_code=200, json=body)

    result = interface.fetch({"db": "InterPro", "id": "IPR000001"}, method="entry")

    # fetch_pages wraps a non-paginated single response in a list.
    assert result == [body]
    assert len(niquests_mock.calls) == 1
    assert niquests_mock.calls[0].request.url == ENTRY_URL


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("interpro", "entry")
    parsed = interface.parse(
        body, fields_to_extract={"accession": "metadata.accession", "type": "metadata.type"}
    )

    assert parsed == {"accession": "IPR000001", "type": "domain"}


class TestInterproContract(CachingContract, HttpErrorContract):
    INTERFACE_URL = ENTRY_URL
    QUERY = {"db": "InterPro", "id": "IPR000001"}
    METHOD = "entry"
    FIXTURE = ("interpro", "entry")
    ERROR_RETURNS_EMPTY = True
