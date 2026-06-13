"""Offline tests for the PDB (Protein Data Bank) interface."""

from __future__ import annotations

import pytest
import responses

from bioseq_dl.core.interfaces.proteindatabank import PDBInterface
from tests._helpers import load_fixture

ENTRY_URL = "https://data.rcsb.org/rest/v1/core/entry/4HHB"


@pytest.fixture
def interface(tmp_path):
    # download_structures=False: avoid the extra structure-file download in fetch_single.
    return PDBInterface(
        download_structures=False,
        cache_dir=str(tmp_path),
        config_dir=str(tmp_path),
        min_wait=0,
        max_wait=0,
        use_config=False,
    )


def test_fetch_builds_url_and_returns_entry(interface, mocked_responses):
    body = load_fixture("pdb", "entry")
    mocked_responses.add(responses.GET, ENTRY_URL, json=body, status=200)

    result = interface.fetch("4HHB", method="entry")

    assert result == body
    assert len(mocked_responses.calls) == 1
    assert mocked_responses.calls[0].request.url == ENTRY_URL


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("pdb", "entry")
    parsed = interface.parse(body, fields_to_extract={"id": "rcsb_id", "title": "struct.title"})

    assert parsed == {"id": body["rcsb_id"], "title": body["struct"]["title"]}


def test_fetch_single_round_trips_through_cache(interface, mocked_responses):
    body = load_fixture("pdb", "entry")
    mocked_responses.add(responses.GET, ENTRY_URL, json=body, status=200)

    first, _ = interface.fetch_single("4HHB", method="entry")
    second, _ = interface.fetch_single("4HHB", method="entry")

    assert len(mocked_responses.calls) == 1
    assert first == second
