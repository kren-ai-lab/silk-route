"""Offline tests for the PathwayCommons interface."""

from __future__ import annotations

import logging

import pytest
from niquests_mock import startswith

from silkroute.core.exceptions import RequestError
from silkroute.core.interfaces.pathwaycommons import PathwayCommonsInterface
from tests._helpers import load_fixture
from tests.core.interfaces._contract import CachingContract, HttpErrorContract

FETCH_URL = "https://www.pathwaycommons.org/pc2/v2/fetch"
TOP_PATHWAYS_URL = "https://www.pathwaycommons.org/pc2/v2/top_pathways"
NEIGHBORHOOD_URL = "https://www.pathwaycommons.org/pc2/v2/neighborhood"


@pytest.fixture
def interface(tmp_path):
    return PathwayCommonsInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_unwraps_graph(interface, niquests_mock):
    body = load_fixture("pathwaycommons", "fetch")
    niquests_mock.post(url=startswith(FETCH_URL)).respond(status_code=200, json=body)

    result = interface.fetch({"uri": ["uniprot:P04637"]}, method="fetch")

    # fetch unwraps the JSON-LD "@graph" envelope.
    assert result == body["@graph"]
    assert len(niquests_mock.calls) == 1


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("pathwaycommons", "fetch")
    record = body["@graph"][0]
    parsed = interface.parse(record, fields_to_extract=["@id", "@type"])

    assert parsed == {k: record[k] for k in ("@id", "@type")}


def test_fetch_unwraps_search_hit(interface, niquests_mock):
    body = {"searchHit": [{"uri": "http://identifiers.org/reactome/R-HSA-1"}]}
    niquests_mock.post(url=startswith(TOP_PATHWAYS_URL)).respond(status_code=200, json=body)

    result = interface.fetch({"q": "TP53"}, method="top_pathways")

    assert result == body["searchHit"]


def test_fetch_unwraps_neighborhood_graph(interface, niquests_mock):
    body = {"@graph": [{"@id": "http://identifiers.org/uniprot/P12345"}]}
    niquests_mock.post(url=startswith(NEIGHBORHOOD_URL)).respond(status_code=200, json=body)

    result = interface.fetch({"source": ["P12345"], "organism": ["9606"]}, method="neighborhood")

    assert result == body["@graph"]


def test_fetch_single_502_is_request_failure_with_one_concise_error(interface, niquests_mock, caplog):
    niquests_mock.post(url=startswith(NEIGHBORHOOD_URL)).respond(
        status_code=502, json={"error": "Bad Gateway"}
    )

    with caplog.at_level(logging.ERROR, logger="silkroute.interfaces.base"):
        result, metadata = interface.fetch_single(
            {"source": ["A0A059ZRB8"], "organism": ["9606"]},
            method="neighborhood",
        )

    errors = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert result == {}
    assert metadata["failed"]["reasons"] == ["request_error"]
    assert len(errors) == 1
    assert errors[0].exc_info is None
    assert "PathwayCommons request failed: 502 Bad Gateway" in errors[0].getMessage()
    assert "method=neighborhood, source=A0A059ZRB8" in errors[0].getMessage()
    assert "identifier not found" not in errors[0].getMessage()


@pytest.mark.parametrize("status_code", [500, 503])
def test_other_server_errors_still_raise_request_error(interface, niquests_mock, caplog, status_code):
    niquests_mock.post(url=startswith(NEIGHBORHOOD_URL)).respond(
        status_code=status_code, json={"error": "service unavailable"}
    )

    with caplog.at_level(logging.ERROR, logger="silkroute.interfaces.base"), pytest.raises(RequestError):
        interface.fetch({"source": ["P12345"], "organism": ["9606"]}, method="neighborhood")

    errors = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert errors[0].exc_info is None


def test_fetch_missing_required_param_raises(interface):
    with pytest.raises(ValueError, match="uri"):
        interface.fetch({"uri": []}, method="fetch")


class TestPathwaycommonsContract(CachingContract, HttpErrorContract):
    INTERFACE_URL = FETCH_URL
    QUERY = {"uri": ["uniprot:P04637"]}
    METHOD = "fetch"
    FIXTURE = ("pathwaycommons", "fetch")
    HTTP_METHOD = "post"
