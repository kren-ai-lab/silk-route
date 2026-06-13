"""Offline tests for the PRIDE interface."""

from __future__ import annotations

import pytest
import responses

from bioseq_dl.core.interfaces.pride import PrideInterface
from tests._helpers import load_fixture

PROJECT_URL = "https://www.ebi.ac.uk/pride/ws/archive/v3/projects/PXD000001"


@pytest.fixture
def interface(tmp_path):
    return PrideInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_builds_url_and_returns_project(interface, mocked_responses):
    body = load_fixture("pride", "project")
    mocked_responses.add(responses.GET, PROJECT_URL, json=body, status=200)

    result = interface.fetch("PXD000001", method="projects")

    assert result == body
    assert len(mocked_responses.calls) == 1
    assert mocked_responses.calls[0].request.url.startswith(PROJECT_URL)


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("pride", "project")
    parsed = interface.parse(body, fields_to_extract=["accession", "title"])

    assert parsed == {"accession": body["accession"], "title": body["title"]}


def test_fetch_single_round_trips_through_cache(interface, mocked_responses):
    body = load_fixture("pride", "project")
    mocked_responses.add(responses.GET, PROJECT_URL, json=body, status=200)

    first, _ = interface.fetch_single("PXD000001", method="projects")
    second, _ = interface.fetch_single("PXD000001", method="projects")

    assert len(mocked_responses.calls) == 1
    assert first == second
