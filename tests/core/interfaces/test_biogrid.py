"""Offline tests for the BioGRID interface.

The access key is supplied explicitly so no network credentials are needed; the
frozen body is replayed via ``responses``.
"""

from __future__ import annotations

import pytest
from niquests_mock import startswith

from bioseq_dl.core.interfaces.biogrid import BioGRIDInterface
from tests._helpers import load_fixture
from tests.core.interfaces._contract import CachingContract

INTERACTIONS_URL = "https://webservice.thebiogrid.org/interactions"


@pytest.fixture
def interface(tmp_path):
    return BioGRIDInterface(
        api_key="FAKEKEY",
        cache_dir=str(tmp_path),
        config_dir=str(tmp_path),
        min_wait=0,
        max_wait=0,
        use_config=False,
    )


def test_fetch_converts_keyed_dict_to_list(interface, niquests_mock):
    body = load_fixture("biogrid", "interactions")
    niquests_mock.get(url=startswith(INTERACTIONS_URL)).respond(status_code=200, json=body)

    result = interface.fetch({"geneList": "TP53", "taxId": "9606"}, method="interactions")

    # BioGRID returns a dict keyed by interaction id; fetch flattens it to a list.
    assert result == list(body.values())
    assert len(niquests_mock.calls) == 1


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("biogrid", "interactions")
    interaction = next(iter(body.values()))
    parsed = interface.parse(interaction, fields_to_extract=["OFFICIAL_SYMBOL_A", "OFFICIAL_SYMBOL_B"])

    assert parsed == {k: interaction[k] for k in ("OFFICIAL_SYMBOL_A", "OFFICIAL_SYMBOL_B")}


class TestBiogridContract(CachingContract):
    # accessKey is excluded from the cache key, so the second call hits the cache.
    INTERFACE_URL = INTERACTIONS_URL
    QUERY = {"geneList": "TP53", "taxId": "9606"}
    METHOD = "interactions"
    FIXTURE = ("biogrid", "interactions")
