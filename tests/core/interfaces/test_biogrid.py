"""Offline tests for the BioGRID interface.

The access key is supplied explicitly so no network credentials are needed; the
frozen body is replayed via ``responses``.
"""

from __future__ import annotations

import pytest
import responses

from bioseq_dl.core.interfaces.biogrid import BioGRIDInterface
from tests._helpers import load_fixture

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


def test_fetch_converts_keyed_dict_to_list(interface, mocked_responses):
    body = load_fixture("biogrid", "interactions")
    mocked_responses.add(responses.GET, INTERACTIONS_URL, json=body, status=200)

    result = interface.fetch({"geneList": "TP53", "taxId": "9606"}, method="interactions")

    # BioGRID returns a dict keyed by interaction id; fetch flattens it to a list.
    assert result == list(body.values())
    assert len(mocked_responses.calls) == 1


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("biogrid", "interactions")
    interaction = next(iter(body.values()))
    parsed = interface.parse(interaction, fields_to_extract=["OFFICIAL_SYMBOL_A", "OFFICIAL_SYMBOL_B"])

    assert parsed == {k: interaction[k] for k in ("OFFICIAL_SYMBOL_A", "OFFICIAL_SYMBOL_B")}


def test_fetch_single_round_trips_through_cache(interface, mocked_responses):
    body = load_fixture("biogrid", "interactions")
    mocked_responses.add(responses.GET, INTERACTIONS_URL, json=body, status=200)

    query = {"geneList": "TP53", "taxId": "9606"}
    first, _ = interface.fetch_single(query, method="interactions")
    second, _ = interface.fetch_single(query, method="interactions")

    # accessKey is excluded from the cache key, so the second call hits the cache.
    assert len(mocked_responses.calls) == 1
    assert first == second
