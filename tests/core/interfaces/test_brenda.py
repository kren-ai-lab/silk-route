"""Offline tests for the BRENDA interface (SOAP / zeep client boundary).

BRENDA talks SOAP via ``zeep``. We mock the zeep client at the boundary so no
WSDL is fetched and no SOAP call is made.
"""

from __future__ import annotations

import pytest

import bioseq_dl.core.interfaces.brenda as brenda_mod
from bioseq_dl.core.interfaces.brenda import BrendaInterface
from tests._helpers import load_fixture


class _FakeService:
    def __init__(self, payload):
        self._payload = payload
        self.calls = 0

    def getKmValue(self, *args):
        self.calls += 1
        return self._payload


class _FakeClient:
    """Stand-in for zeep.Client: no network, exposes a .service with the method."""

    def __init__(self, wsdl, payload):
        self.service = _FakeService(payload)


@pytest.fixture
def interface(tmp_path, monkeypatch):
    payload = load_fixture("brenda", "getKmValue")
    monkeypatch.setattr(brenda_mod, "Client", lambda wsdl: _FakeClient(wsdl, payload))
    iface = BrendaInterface(
        email="test@example.com",
        password="secret",  # noqa: S106 - test stub, not a real credential
        cache_dir=str(tmp_path),
        config_dir=str(tmp_path),
        use_config=False,
    )
    # The ctor hardcodes min_wait/max_wait; zero them so _delay does not sleep.
    iface.min_wait = iface.max_wait = 0
    return iface


def test_fetch_returns_serialized_records(interface):
    result = interface.fetch({"ecNumber": "1.1.1.1", "organism": "Homo sapiens"}, method="getKmValue")

    assert isinstance(result, list)
    assert result[0]["ecNumber"] == "1.1.1.1"
    assert "substrate" in result[0]
    assert interface.client.service.calls == 1


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("brenda", "getKmValue")
    parsed = interface.parse(body[0], fields_to_extract=["ecNumber", "kmValue", "organism"])

    assert parsed == {k: body[0][k] for k in ("ecNumber", "kmValue", "organism")}


def test_fetch_single_round_trips_through_cache(interface):
    query = {"ecNumber": "1.1.1.1", "organism": "Homo sapiens"}
    first, _ = interface.fetch_single(query, method="getKmValue")
    second, _ = interface.fetch_single(query, method="getKmValue")

    # Second call served from cache: the SOAP method is only invoked once.
    assert interface.client.service.calls == 1
    assert first == second
