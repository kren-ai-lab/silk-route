"""Offline tests for the GenOntology interface."""

from __future__ import annotations

import pytest
from niquests_mock import startswith

from silkroute.core.interfaces.genontology import GenOntologyInterface
from tests._helpers import load_fixture
from tests.core.interfaces._contract import CachingContract, HttpErrorContract

TERM_URL = "https://api.geneontology.org/api/ontology/term/GO%3A0008150"


@pytest.fixture
def interface(tmp_path):
    return GenOntologyInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_builds_url_and_returns_term(interface, niquests_mock):
    body = load_fixture("genontology", "term")
    niquests_mock.get(url=startswith(TERM_URL)).respond(status_code=200, json=body)

    result = interface.fetch("GO:0008150", method="ontology-term")

    assert result == body
    assert len(niquests_mock.calls) == 1
    assert niquests_mock.calls[0].request.url == TERM_URL


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("genontology", "term")
    parsed = interface.parse(body, fields_to_extract=["goid", "label"])

    assert parsed == {"goid": "GO:0008150", "label": "biological_process"}


class TestGenontologyContract(CachingContract, HttpErrorContract):
    INTERFACE_URL = TERM_URL
    QUERY = "GO:0008150"
    METHOD = "ontology-term"
    FIXTURE = ("genontology", "term")
