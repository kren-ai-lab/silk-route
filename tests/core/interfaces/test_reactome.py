"""Offline tests for the Reactome interface."""

from __future__ import annotations

import pytest

from bioseq_dl.core.exceptions import ConfigError
from bioseq_dl.core.interfaces.reactome import ReactomeInterface


@pytest.fixture
def interface(tmp_path):
    return ReactomeInterface(cache_dir=str(tmp_path), config_dir=str(tmp_path))


def test_validate_query_accepts_valid_id(interface):
    # Should not raise.
    interface.validate_query({"id": "R-HSA-123456"})


@pytest.mark.parametrize(
    "query",
    [
        {"id": ""},
        {"id": "   "},
        {"id": 123},
        {"species": ""},
        {"onlyDiagrammed": "yes"},
    ],
)
def test_validate_query_raises_on_invalid(interface, query):
    # Regression: previously returned {} and the caller silently proceeded.
    with pytest.raises(ConfigError):
        interface.validate_query(query)
