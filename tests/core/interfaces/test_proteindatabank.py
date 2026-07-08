"""Offline tests for the PDB (Protein Data Bank) interface."""

from __future__ import annotations

import copy
import logging

import pandas as pd
import pytest
import responses

from bioseq_dl.core.interfaces.proteindatabank import PDBInterface
from tests._helpers import load_fixture

ENTRY_URL = "https://data.rcsb.org/rest/v1/core/entry/4HHB"
SECOND_ENTRY_URL = "https://data.rcsb.org/rest/v1/core/entry/1ABC"
STRUCTURE_URL = "https://files.rcsb.org/download/4HHB.pdb"
SECOND_STRUCTURE_URL = "https://files.rcsb.org/download/1ABC.pdb"


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


def test_fetch_structure_404_warns_without_error_traceback(tmp_path, mocked_responses, caplog):
    interface = PDBInterface(
        download_structures=True,
        cache_dir=str(tmp_path),
        config_dir=str(tmp_path),
        output_dir=str(tmp_path / "structures"),
        min_wait=0,
        max_wait=0,
        use_config=False,
    )
    mocked_responses.add(responses.GET, STRUCTURE_URL, status=404)

    with caplog.at_level(logging.WARNING):
        result = interface.fetch_structure("4HHB")

    assert result == ""
    assert "PDB structure file not found for 4HHB" in caplog.text
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert not [record for record in caplog.records if record.exc_info]


def test_fetch_batch_mixed_cached_and_uncached_downloads_structures_once(
    tmp_path,
    mocked_responses,
):
    interface = PDBInterface(
        download_structures=False,
        cache_dir=str(tmp_path / "cache"),
        config_dir=str(tmp_path / "config"),
        output_dir=str(tmp_path / "structures"),
        min_wait=0,
        max_wait=0,
        use_config=False,
    )
    body = load_fixture("pdb", "entry")
    second_body = copy.deepcopy(body)
    second_body["rcsb_id"] = "1ABC"
    second_body["entry"]["id"] = "1ABC"

    mocked_responses.add(responses.GET, ENTRY_URL, json=body, status=200)
    cached, _ = interface.fetch_single("4HHB", method="entry", format="dataframe")
    assert isinstance(cached, pd.DataFrame)

    interface.download_structures = True
    mocked_responses.add(responses.GET, STRUCTURE_URL, body=b"HEADER 4HHB", status=200)
    mocked_responses.add(responses.GET, SECOND_STRUCTURE_URL, body=b"HEADER 1ABC", status=200)
    mocked_responses.add(responses.GET, SECOND_ENTRY_URL, json=second_body, status=200)

    batch, metadata = interface.fetch_batch(["4HHB", "1ABC"], method="entry", format="dataframe")

    assert isinstance(batch, pd.DataFrame)
    assert set(batch["rcsb_id"].tolist()) == {"4HHB", "1ABC"}
    assert metadata["data_info"]["total_entries"] == 2
    assert [call.request.url for call in mocked_responses.calls].count(STRUCTURE_URL) == 1
    assert [call.request.url for call in mocked_responses.calls].count(SECOND_STRUCTURE_URL) == 1
