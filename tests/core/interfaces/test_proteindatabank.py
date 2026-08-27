"""Offline tests for the PDB (Protein Data Bank) interface."""

from __future__ import annotations

import logging

import pytest
from niquests_mock import startswith

from silkroute.core.exceptions import RequestError
from silkroute.core.interfaces.base import BaseAPIInterface
from silkroute.core.interfaces.proteindatabank import PDBInterface
from silkroute.core.metadata import FetchMetadata
from tests._helpers import load_fixture
from tests.core.interfaces._contract import CachingContract, HttpErrorContract

ENTRY_URL = "https://data.rcsb.org/rest/v1/core/entry/4HHB"
MISSING_ENTRY_URL = "https://data.rcsb.org/rest/v1/core/entry/4DDA"


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


def test_fetch_builds_url_and_returns_entry(interface, niquests_mock):
    body = load_fixture("pdb", "entry")
    niquests_mock.get(url=startswith(ENTRY_URL)).respond(status_code=200, json=body)

    result = interface.fetch("4HHB", method="entry")

    assert result == body
    assert len(niquests_mock.calls) == 1
    assert niquests_mock.calls[0].request.url == ENTRY_URL


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("pdb", "entry")
    parsed = interface.parse(body, fields_to_extract={"id": "rcsb_id", "title": "struct.title"})

    assert parsed == {"id": body["rcsb_id"], "title": body["struct"]["title"]}


def test_missing_entry_is_recoverable_without_normal_level_traceback(interface, niquests_mock, caplog):
    niquests_mock.get(url=startswith(MISSING_ENTRY_URL)).respond(
        status_code=404, json={"status": 404, "message": "Not Found"}
    )

    with caplog.at_level(logging.ERROR, logger="silkroute.interfaces.base"):
        result, metadata = interface.fetch_single({"id": "4DDA"}, method="entry")

    errors = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert result == {}
    assert metadata["failed"]["reasons"] == ["request_error"]
    assert len(errors) == 1
    assert errors[0].exc_info is None
    assert errors[0].getMessage() == "PDB request failed: 404 Not Found (method=entry, source=4DDA)"
    assert "Traceback (most recent call last)" not in caplog.text


def test_missing_entry_keeps_exception_details_at_debug(interface, niquests_mock, caplog):
    niquests_mock.get(url=startswith(MISSING_ENTRY_URL)).respond(
        status_code=404, json={"status": 404, "message": "Not Found"}
    )

    with (
        caplog.at_level(logging.DEBUG, logger="silkroute.interfaces.base"),
        pytest.raises(RequestError),
    ):
        interface.fetch({"id": "4DDA"}, method="entry")

    details = [record for record in caplog.records if record.getMessage() == "HTTP request failure details"]
    assert len(details) == 1
    assert details[0].exc_info is not None
    assert details[0].exc_info[0].__name__ == "HTTPError"
    assert MISSING_ENTRY_URL in caplog.text
    assert "Traceback (most recent call last)" in caplog.text


def test_unrelated_client_error_still_propagates(interface, niquests_mock):
    niquests_mock.get(url=startswith(ENTRY_URL)).respond(
        status_code=400, json={"status": 400, "message": "Bad Request"}
    )

    with pytest.raises(RequestError):
        interface.fetch("4HHB", method="entry")


def test_download_batch_fetches_dict_queries(monkeypatch, tmp_path):
    interface = PDBInterface(
        download_structures=True,
        cache_dir=str(tmp_path),
        config_dir=str(tmp_path),
        min_wait=0,
        max_wait=0,
        use_config=False,
    )

    fetched = []

    def fake_single(self, query, parse=False, *args, **kwargs):
        fetched.append(query)
        pdb_id = query if isinstance(query, str) else query.get("id")
        return [{"id": pdb_id}], FetchMetadata().to_dict()

    downloaded = []
    monkeypatch.setattr(BaseAPIInterface, "fetch_single", fake_single)
    monkeypatch.setattr(interface, "fetch_structure", lambda pid: downloaded.append(pid) or f"/x/{pid}.pdb")
    monkeypatch.setattr(interface, "_display_downloaded_structure_path", lambda path: path)

    interface.fetch_batch(["4HHB", {"id": "1ABC"}])

    # Both the string and the dict query are fetched (dict is no longer silently dropped).
    assert "4HHB" in fetched
    assert {"id": "1ABC"} in fetched
    # Structure download is attempted only for the string PDB id.
    assert downloaded == ["4HHB"]


class TestPdbContract(CachingContract, HttpErrorContract):
    INTERFACE_URL = ENTRY_URL
    QUERY = "4HHB"
    METHOD = "entry"
    FIXTURE = ("pdb", "entry")
