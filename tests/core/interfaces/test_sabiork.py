"""Offline tests for the SABIO-RK interface (TSV export responses)."""

from __future__ import annotations

import pytest
from niquests_mock import startswith

from bioseq_dl.core.interfaces.sabiork import SabiorkInterface
from tests._helpers import load_fixture
from tests.core.interfaces._contract import CachingContract, HttpErrorContract

EXPORT_URL = "https://sabiork.h-its.org/sabioRestWebServices/kineticlawsExportTsv"


@pytest.fixture
def interface(tmp_path):
    return SabiorkInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_parses_tsv_into_records(interface, niquests_mock):
    text = load_fixture("sabiork", "kineticlaws")
    niquests_mock.post(url=startswith(EXPORT_URL)).respond(status_code=200, text=text)

    result = interface.fetch({"UniProtKB_AC": "P00330"}, method="kineticlaws")

    assert isinstance(result, list)
    assert result  # at least one kinetic-law row
    assert result[0]["EntryID"]
    assert "UniprotID" in result[0]
    assert niquests_mock.calls[0].request.url.startswith(EXPORT_URL)


def test_parse_extracts_requested_fields(interface):
    record = {"EntryID": "12345", "Organism": "Homo sapiens", "ECNumber": "1.1.1.1"}
    parsed = interface.parse(record, fields_to_extract=["EntryID", "ECNumber"])

    assert parsed == {"EntryID": "12345", "ECNumber": "1.1.1.1"}


class TestSabiorkContract(CachingContract, HttpErrorContract):
    INTERFACE_URL = EXPORT_URL
    QUERY = {"UniProtKB_AC": "P00330"}
    METHOD = "kineticlaws"
    FIXTURE = ("sabiork", "kineticlaws")
    HTTP_METHOD = "post"
    BODY_IS_TEXT = True
    ERROR_RETURNS_EMPTY = True
