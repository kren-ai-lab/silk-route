"""Offline fetch/parse/cache tests for the InterPro interface.

(Regression for the query_usage NameError bug lives in test_interpro.py.)
"""

from __future__ import annotations

import pytest
import responses

from bioseq_dl.core.interfaces.interpro import InterproInterface
from tests._helpers import load_fixture

ENTRY_URL = "https://www.ebi.ac.uk:443/interpro/api/entry/InterPro/IPR000001/"


@pytest.fixture
def interface(tmp_path):
    return InterproInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_builds_url_and_wraps_in_list(interface, mocked_responses):
    body = load_fixture("interpro", "entry")
    mocked_responses.add(responses.GET, ENTRY_URL, json=body, status=200)

    result = interface.fetch({"db": "InterPro", "id": "IPR000001"}, method="entry")

    # fetch_pages wraps a non-paginated single response in a list.
    assert result == [body]
    assert len(mocked_responses.calls) == 1
    assert mocked_responses.calls[0].request.url == ENTRY_URL


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("interpro", "entry")
    parsed = interface.parse(
        body, fields_to_extract={"accession": "metadata.accession", "type": "metadata.type"}
    )

    assert parsed == {"accession": "IPR000001", "type": "domain"}


def test_fetch_single_round_trips_through_cache(interface, mocked_responses):
    body = load_fixture("interpro", "entry")
    mocked_responses.add(responses.GET, ENTRY_URL, json=body, status=200)

    query = {"db": "InterPro", "id": "IPR000001"}
    first, _ = interface.fetch_single(query, method="entry")
    second, _ = interface.fetch_single(query, method="entry")

    assert len(mocked_responses.calls) == 1
    assert first == second
