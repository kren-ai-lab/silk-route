"""Tests for the InterPro interface that do not require network access."""

from __future__ import annotations

from bioseq_dl.constants.interpro import data_types, db_types, entry_integration_types
from bioseq_dl.core.interfaces.interpro import InterproInterface


def test_query_usage_does_not_raise_nameerror(tmp_path):
    # Regression: query_usage referenced an unimported `data_types` -> NameError.
    interface = InterproInterface(cache_dir=str(tmp_path), config_dir=str(tmp_path))
    usage = interface.query_usage()

    assert isinstance(usage, str)
    assert data_types[0] in usage
    assert db_types["entry"][0] in usage
    assert entry_integration_types[0] in usage
