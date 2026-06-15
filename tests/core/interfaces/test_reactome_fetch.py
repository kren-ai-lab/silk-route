"""Offline fetch/parse/cache tests for the Reactome interface.

(validate_query regression tests live in test_reactome.py.)
"""

from __future__ import annotations

import pytest
from niquests_mock import startswith

from bioseq_dl.core.interfaces.reactome import ReactomeInterface
from tests._helpers import load_fixture

DISCOVER_URL = "https://reactome.org/ContentService/data/discover/R-HSA-109581/"


@pytest.fixture
def interface(tmp_path):
    return ReactomeInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_builds_url_and_returns_record(interface, niquests_mock):
    body = load_fixture("reactome", "discover")
    niquests_mock.get(url=startswith(DISCOVER_URL)).respond(status_code=200, json=body)

    result = interface.fetch("R-HSA-109581", method="data-discover")

    assert result == body
    assert len(niquests_mock.calls) == 1
    assert niquests_mock.calls[0].request.url == DISCOVER_URL


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("reactome", "discover")
    parsed = interface.parse(body, fields_to_extract=["name", "@type"])

    assert parsed == {"name": body["name"], "@type": body["@type"]}


def test_fetch_single_round_trips_through_cache(interface, niquests_mock):
    body = load_fixture("reactome", "discover")
    niquests_mock.get(url=startswith(DISCOVER_URL)).respond(status_code=200, json=body)

    first, _ = interface.fetch_single("R-HSA-109581", method="data-discover")
    second, _ = interface.fetch_single("R-HSA-109581", method="data-discover")

    assert len(niquests_mock.calls) == 1
    assert first == second
