"""Offline tests for the PANTHER interface."""

from __future__ import annotations

import pytest
from niquests_mock import startswith

from silkroute.core.interfaces.panther import PantherInterface
from tests._helpers import load_fixture
from tests.core.interfaces._contract import CachingContract, HttpErrorContract

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


class TestPantherContract(CachingContract, HttpErrorContract):
    INTERFACE_URL = GENEINFO_URL
    QUERY = {"geneInputList": "TP53", "organism": "9606"}
    METHOD = "geneinfo"
    FIXTURE = ("panther", "geneinfo")
    HTTP_METHOD = "post"
