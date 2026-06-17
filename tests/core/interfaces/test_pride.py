"""Offline tests for the PRIDE interface."""

from __future__ import annotations

import pytest
from niquests_mock import startswith

from bioseq_dl.core.interfaces.pride import PrideInterface
from tests._helpers import load_fixture

PROJECT_URL = "https://www.ebi.ac.uk/pride/ws/archive/v3/projects/PXD000001"


@pytest.fixture
def interface(tmp_path):
    return PrideInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_builds_url_and_returns_project(interface, niquests_mock):
    body = load_fixture("pride", "project")
    niquests_mock.get(url=startswith(PROJECT_URL)).respond(status_code=200, json=body)

    result = interface.fetch("PXD000001", method="projects")

    assert result == body
    assert len(niquests_mock.calls) == 1
    assert niquests_mock.calls[0].request.url.startswith(PROJECT_URL)


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("pride", "project")
    parsed = interface.parse(body, fields_to_extract=["accession", "title"])

    assert parsed == {"accession": body["accession"], "title": body["title"]}


def test_fetch_single_round_trips_through_cache(interface, niquests_mock):
    body = load_fixture("pride", "project")
    niquests_mock.get(url=startswith(PROJECT_URL)).respond(status_code=200, json=body)

    first, _ = interface.fetch_single("PXD000001", method="projects")
    second, _ = interface.fetch_single("PXD000001", method="projects")

    assert len(niquests_mock.calls) == 1
    assert first == second


def test_fetch_returns_empty_on_http_error(interface, niquests_mock):
    niquests_mock.get(url=startswith(PROJECT_URL)).respond(status_code=500, json={"error": "boom"})

    assert interface.fetch("PXD000001", method="projects") == {}
