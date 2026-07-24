"""Offline tests for the RefSeq interface (NCBI Entrez client boundary).

RefSeq uses Bio.Entrez (efetch/read), not HTTP we can intercept with responses.
We mock at the Entrez boundary.
"""

from __future__ import annotations

import pytest

import silkroute.core.interfaces.refseq as refseq_mod
from silkroute.core.interfaces.refseq import RefSeqInterface
from tests._helpers import load_fixture


class _FakeHandle:
    def close(self):
        pass


@pytest.fixture
def interface(tmp_path, monkeypatch):
    records = load_fixture("refseq", "protein")
    state = {"reads": 0}

    def fake_efetch(db, id, retmode):  # noqa: A002  # mirrors Bio.Entrez.efetch(id=...) keyword
        return _FakeHandle()

    def fake_read(handle):
        state["reads"] += 1
        return records

    monkeypatch.setattr(refseq_mod.Entrez, "efetch", fake_efetch)
    monkeypatch.setattr(refseq_mod.Entrez, "read", fake_read)

    iface = RefSeqInterface(
        email="test@example.com",
        cache_dir=str(tmp_path),
        config_dir=str(tmp_path),
        min_wait=0,
        max_wait=0,
        use_config=False,
    )
    iface._read_state = state  # ty: ignore  # type: ignore[missing-attribute]  # injected state
    return iface


def test_fetch_returns_native_records(interface):
    result = interface.fetch("NP_000537", method="protein")

    assert isinstance(result, list)
    assert result[0]["GBSeq_locus"] == "NP_000537"


def test_parse_extracts_requested_fields(interface):
    records = load_fixture("refseq", "protein")
    parsed = interface.parse(records[0], fields_to_extract=["GBSeq_locus", "GBSeq_organism"])

    assert parsed == {"GBSeq_locus": "NP_000537", "GBSeq_organism": "Homo sapiens"}


def test_fetch_single_round_trips_through_cache(interface):
    first, _ = interface.fetch_single("NP_000537", method="protein")
    second, _ = interface.fetch_single("NP_000537", method="protein")

    # Second call served from cache: Entrez.read is only invoked once.
    assert interface._read_state["reads"] == 1
    assert first == second
