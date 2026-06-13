"""Offline tests for the GenOntology interface."""

from __future__ import annotations

import pytest
import responses

from bioseq_dl.core.interfaces.genontology import GenOntologyInterface
from tests._helpers import load_fixture

TERM_URL = "https://api.geneontology.org/api/ontology/term/GO%3A0008150"


@pytest.fixture
def interface(tmp_path):
    return GenOntologyInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_builds_url_and_returns_term(interface, mocked_responses):
    body = load_fixture("genontology", "term")
    mocked_responses.add(responses.GET, TERM_URL, json=body, status=200)

    result = interface.fetch("GO:0008150", method="ontology-term")

    assert result == body
    assert len(mocked_responses.calls) == 1
    assert mocked_responses.calls[0].request.url == TERM_URL


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("genontology", "term")
    parsed = interface.parse(body, fields_to_extract=["goid", "label"])

    assert parsed == {"goid": "GO:0008150", "label": "biological_process"}


def test_fetch_single_round_trips_through_cache(interface, mocked_responses):
    body = load_fixture("genontology", "term")
    mocked_responses.add(responses.GET, TERM_URL, json=body, status=200)

    first, _ = interface.fetch_single("GO:0008150", method="ontology-term")
    second, _ = interface.fetch_single("GO:0008150", method="ontology-term")

    assert len(mocked_responses.calls) == 1
    assert first == second
