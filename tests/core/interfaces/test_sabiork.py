"""Offline tests for the SABIO-RK interface (JSON export responses)."""

from __future__ import annotations

import json
import math
from typing import ClassVar

import pytest
from niquests_mock import build_response, startswith

from silkroute.core.interfaces.sabiork import SabiorkInterface
from tests._helpers import load_fixture
from tests.core.interfaces._contract import CachingContract, HttpErrorContract

EXPORT_URL = "https://sabiork.h-its.org/export-api/sabio/kinlaw-entry/json"


@pytest.fixture
def interface(tmp_path):
    return SabiorkInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_flattens_json_into_records(interface, niquests_mock):
    payload = load_fixture("sabiork", "kineticlaws")
    niquests_mock.post(url=startswith(EXPORT_URL)).respond(status_code=200, json=payload)

    result = interface.fetch({"UniProtKB_AC": "P00330"}, method="kineticlaws")

    assert isinstance(result, list)
    assert result  # at least one kinetic-law row
    assert result[0]["EntryID"]
    assert "UniprotID" in result[0]
    assert niquests_mock.calls[0].request.url.startswith(EXPORT_URL)


def test_fetch_prefers_normalized_parameter_values(interface, niquests_mock):
    # The Export API ships both raw and normalized (n_*) parameter values; the
    # normalized ones win, so rows carry SI-converted numbers and unit names.
    payload = load_fixture("sabiork", "kineticlaws")
    parameters = [p for entry in payload["data"] for p in entry["kineticlaw"]["parameter"]]
    niquests_mock.post(url=startswith(EXPORT_URL)).respond(status_code=200, json=payload)

    result = interface.fetch({"UniProtKB_AC": "P00330"}, method="kineticlaws")

    assert len(result) == len(parameters)  # one row per parameter, in payload order
    pairs = list(zip(result, parameters, strict=True))
    assert all(row["parameter.name"] == p["name"] for row, p in pairs)

    # A null n_* legitimately falls back to the raw value, so only the parameters
    # whose normalized value diverges prove the preference. Assert the fixture
    # still carries such cases -- otherwise this test would be vacuous.
    for column, normalized_key, raw_key in (
        ("parameter.startValue", "n_start_value", "start_value"),
        ("parameter.endValue", "n_end_value", "end_value"),
    ):
        divergent = [
            (row, p)
            for row, p in pairs
            if p[normalized_key] is not None and p[normalized_key] != p.get(raw_key)
        ]
        assert divergent, f"fixture carries no divergent {normalized_key}"
        for row, parameter in divergent:
            assert row[column] == parameter[normalized_key]

    divergent_units = [
        (row, p)
        for row, p in pairs
        if p["unit"]["n_name"] is not None and p["unit"]["n_name"] != p["unit"].get("name")
    ]
    assert divergent_units, "fixture carries no divergent unit.n_name"
    for row, parameter in divergent_units:
        assert row["parameter.unit"] == parameter["unit"]["n_name"]


def paginate_fixture(page_size: int) -> dict[int, dict]:
    """Split the captured single-page response into the pages the API would return.

    Verified against real ``page_size=1`` captures: this reproduces those bodies
    exactly, envelope included, so the pages stay real without storing the same
    entries in a second fixture.
    """
    entries = load_fixture("sabiork", "kineticlaws")["data"]
    total_pages = math.ceil(len(entries) / page_size)
    return {
        page: {
            "meta": {
                "page": page,
                "page_size": page_size,
                "total_count": len(entries),
                "total_pages": total_pages,
            },
            "data": entries[(page - 1) * page_size : page * page_size],
        }
        for page in range(1, total_pages + 1)
    }


def test_fetch_follows_export_api_pagination(interface, niquests_mock):
    pages = paginate_fixture(page_size=1)
    assert len(pages) > 1  # a single-page split would not exercise the loop
    requested: list[int] = []

    def serve_requested_page(request):
        page = json.loads(request.body)["page"]
        requested.append(page)
        return build_response(request, status_code=200, json=pages[page])

    niquests_mock.post(url=startswith(EXPORT_URL)).mock(side_effect=serve_requested_page)

    result = interface.fetch({"UniProtKB_AC": "P00330"}, method="kineticlaws", page_size=1)

    assert requested == [1, 2]  # stopped at meta.total_pages, no page 3
    entry_ids = {row["EntryID"] for row in result}
    assert entry_ids == {entry["id"] for page in pages.values() for entry in page["data"]}


def test_fetch_stops_at_max_pages(interface, niquests_mock):
    page_one = paginate_fixture(page_size=1)[1]
    assert page_one["meta"]["total_pages"] > 1  # the cap, not exhaustion, must end the loop
    route = niquests_mock.post(url=startswith(EXPORT_URL)).respond(status_code=200, json=page_one)

    result = interface.fetch({"UniProtKB_AC": "P00330"}, method="kineticlaws", page_size=1, max_pages=1)

    assert route.call_count == 1
    assert {row["EntryID"] for row in result} == {entry["id"] for entry in page_one["data"]}


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
    ERROR_RETURNS_EMPTY = True
    ERROR_EMPTY_VALUE: ClassVar[list] = []  # fetch returns a list of records
