"""Offline tests for the ChEBI interface."""

from __future__ import annotations

import pytest
import responses

from bioseq_dl.core.interfaces.chebi import ChEBIInterface
from tests._helpers import load_fixture

COMPOUND_URL = "https://www.ebi.ac.uk/chebi/backend/api/public/compound/15377"


@pytest.fixture
def interface(tmp_path):
    return ChEBIInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_builds_url_and_returns_compound(interface, mocked_responses):
    body = load_fixture("chebi", "compound")
    mocked_responses.add(responses.GET, COMPOUND_URL, json=body, status=200)

    result = interface.fetch("15377", method="compound")

    assert result == body
    assert len(mocked_responses.calls) == 1
    assert mocked_responses.calls[0].request.url.startswith(COMPOUND_URL)


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("chebi", "compound")
    parsed = interface.parse(body, fields_to_extract=["chebi_accession", "name"])

    assert parsed == {"chebi_accession": body["chebi_accession"], "name": body["name"]}


def test_fetch_single_round_trips_through_cache(interface, mocked_responses):
    body = load_fixture("chebi", "compound")
    mocked_responses.add(responses.GET, COMPOUND_URL, json=body, status=200)

    first, _ = interface.fetch_single("15377", method="compound")
    second, _ = interface.fetch_single("15377", method="compound")

    assert len(mocked_responses.calls) == 1
    assert first == second
