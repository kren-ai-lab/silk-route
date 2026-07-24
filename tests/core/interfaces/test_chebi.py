"""Offline tests for the ChEBI interface."""

from __future__ import annotations

import pytest
from niquests_mock import startswith

from silkroute.core.interfaces.chebi import ChEBIInterface
from tests._helpers import load_fixture
from tests.core.interfaces._contract import CachingContract, HttpErrorContract

COMPOUND_URL = "https://www.ebi.ac.uk/chebi/backend/api/public/compound/15377"


@pytest.fixture
def interface(tmp_path):
    return ChEBIInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_builds_url_and_returns_compound(interface, niquests_mock):
    body = load_fixture("chebi", "compound")
    niquests_mock.get(url=startswith(COMPOUND_URL)).respond(status_code=200, json=body)

    result = interface.fetch("15377", method="compound")

    assert result == body
    assert len(niquests_mock.calls) == 1
    assert niquests_mock.calls[0].request.url.startswith(COMPOUND_URL)


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("chebi", "compound")
    parsed = interface.parse(body, fields_to_extract=["chebi_accession", "name"])

    assert parsed == {"chebi_accession": body["chebi_accession"], "name": body["name"]}


class TestChebiContract(CachingContract, HttpErrorContract):
    INTERFACE_URL = COMPOUND_URL
    QUERY = "15377"
    METHOD = "compound"
    FIXTURE = ("chebi", "compound")
    ERROR_RETURNS_EMPTY = True
