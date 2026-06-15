"""Offline tests for the PubChem interface (PUG-View path)."""

from __future__ import annotations

import pytest
from niquests_mock import startswith

from bioseq_dl.core.interfaces.pubchem import PubChemInterface
from tests._helpers import load_fixture

# Note the double slash: API_URL ends with "/" and the pug_view branch prepends "/pug_view".
COMPOUND_URL = "https://pubchem.ncbi.nlm.nih.gov/rest//pug_view/data/compound/444444/JSON"


@pytest.fixture
def interface(tmp_path):
    return PubChemInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_builds_url_and_returns_record(interface, niquests_mock):
    body = load_fixture("pubchem", "pug_view_compound")
    niquests_mock.get(url=startswith(COMPOUND_URL)).respond(status_code=200, json=body)

    result = interface.fetch({"cid": "444444"}, method="pug_view/compound", option="default")

    assert result == body
    assert len(niquests_mock.calls) == 1
    assert niquests_mock.calls[0].request.url == COMPOUND_URL


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("pubchem", "pug_view_compound")
    parsed = interface.parse(
        body, fields_to_extract={"default": {"title": "Record.RecordTitle"}}, option="default"
    )

    assert parsed == {"title": body["Record"]["RecordTitle"]}


def test_fetch_single_round_trips_through_cache(interface, niquests_mock):
    body = load_fixture("pubchem", "pug_view_compound")
    niquests_mock.get(url=startswith(COMPOUND_URL)).respond(status_code=200, json=body)

    query = {"cid": "444444"}
    first, _ = interface.fetch_single(query, method="pug_view/compound", option="default")
    second, _ = interface.fetch_single(query, method="pug_view/compound", option="default")

    assert len(niquests_mock.calls) == 1
    assert first == second
