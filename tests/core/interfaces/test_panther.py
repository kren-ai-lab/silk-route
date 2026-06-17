"""Offline tests for the PANTHER interface."""

from __future__ import annotations

import pytest
from niquests_mock import startswith

from bioseq_dl.core.exceptions import RequestError
from bioseq_dl.core.interfaces.panther import PantherInterface
from tests._helpers import load_fixture

GENEINFO_URL = "https://pantherdb.org/services/oai/pantherdb/geneinfo"


@pytest.fixture
def interface(tmp_path):
    return PantherInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


def test_fetch_unwraps_mapped_genes(interface, niquests_mock):
    body = load_fixture("panther", "geneinfo")
    niquests_mock.post(url=startswith(GENEINFO_URL)).respond(status_code=200, json=body)

    result = interface.fetch({"geneInputList": "TP53", "organism": "9606"}, method="geneinfo")

    # fetch drills into search.mapped_genes.gene.
    assert result == body["search"]["mapped_genes"]["gene"]
    assert len(niquests_mock.calls) == 1


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("panther", "geneinfo")
    # For a single input gene, PANTHER returns one gene object (a dict).
    gene = body["search"]["mapped_genes"]["gene"]
    parsed = interface.parse(gene, fields_to_extract=["accession", "family_id"])

    assert parsed == {k: gene[k] for k in ("accession", "family_id")}


def test_fetch_single_round_trips_through_cache(interface, niquests_mock):
    body = load_fixture("panther", "geneinfo")
    niquests_mock.post(url=startswith(GENEINFO_URL)).respond(status_code=200, json=body)

    query = {"geneInputList": "TP53", "organism": "9606"}
    first, _ = interface.fetch_single(query, method="geneinfo")
    second, _ = interface.fetch_single(query, method="geneinfo")

    assert len(niquests_mock.calls) == 1
    assert first == second


def test_fetch_raises_on_http_error(interface, niquests_mock):
    niquests_mock.post(url=startswith(GENEINFO_URL)).respond(status_code=500, json={"error": "boom"})

    with pytest.raises(RequestError):
        interface.fetch({"geneInputList": "TP53", "organism": "9606"}, method="geneinfo")
