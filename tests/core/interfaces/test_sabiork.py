"""Offline tests for the SABIO-RK interface (TSV export responses)."""

from __future__ import annotations

import pytest
import responses

from bioseq_dl.core.interfaces.sabiork import SabiorkInterface
from tests._helpers import load_fixture

EXPORT_URL = "https://sabiork.h-its.org/sabioRestWebServices/kineticlawsExportTsv"


@pytest.fixture
def interface(tmp_path):
    return SabiorkInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_parses_tsv_into_records(interface, mocked_responses):
    text = load_fixture("sabiork", "kineticlaws")
    mocked_responses.add(responses.POST, EXPORT_URL, body=text, status=200)

    result = interface.fetch({"UniProtKB_AC": "P00330"}, method="kineticlaws")

    assert isinstance(result, list)
    assert result  # at least one kinetic-law row
    assert result[0]["EntryID"]
    assert "UniprotID" in result[0]
    assert mocked_responses.calls[0].request.url.startswith(EXPORT_URL)


def test_parse_extracts_requested_fields(interface):
    record = {"EntryID": "12345", "Organism": "Homo sapiens", "ECNumber": "1.1.1.1"}
    parsed = interface.parse(record, fields_to_extract=["EntryID", "ECNumber"])

    assert parsed == {"EntryID": "12345", "ECNumber": "1.1.1.1"}


def test_fetch_single_round_trips_through_cache(interface, mocked_responses):
    text = load_fixture("sabiork", "kineticlaws")
    mocked_responses.add(responses.POST, EXPORT_URL, body=text, status=200)

    query = {"UniProtKB_AC": "P00330"}
    first, _ = interface.fetch_single(query, method="kineticlaws")
    second, _ = interface.fetch_single(query, method="kineticlaws")

    assert len(mocked_responses.calls) == 1
    assert first == second
