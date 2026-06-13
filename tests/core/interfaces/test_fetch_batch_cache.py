"""Regression test for fetch_batch partial-cache handling.

When a batch query decomposes into several subqueries and only some are cached,
the whole query was marked for refetch *and* the cached subqueries were appended
separately, duplicating them in the output.
"""

from __future__ import annotations

import pytest

from bioseq_dl.core.interfaces.base import BaseAPIInterface


class FakeInterface(BaseAPIInterface):
    API_NAME = "Fake"
    METHODS = {
        "get": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {"id": (str, None, True)},
            "group_queries": ["id"],
            "separator": ",",
        }
    }

    def __init__(self, **kwargs):
        super().__init__(min_wait=0, max_wait=0, use_config=False, **kwargs)
        self.fetch_calls: list[list[str]] = []

    def fetch(self, query, *, method="get", **kwargs):
        raw = query["id"] if isinstance(query, dict) else query
        ids = raw.split(",") if isinstance(raw, str) else list(raw)
        self.fetch_calls.append(ids)
        return [{"id": x, "value": f"val{x}"} for x in ids]

    def parse(self, data, fields_to_extract, **kwargs):
        return data

    def query_usage(self) -> str:
        return "usage"


@pytest.fixture
def interface(tmp_path):
    return FakeInterface(cache_dir=str(tmp_path))


def _collect_ids(obj) -> list[str]:
    """Recursively gather every record's ``id`` from a nested result structure."""
    found = []
    if isinstance(obj, dict):
        if "id" in obj:
            found.append(obj["id"])
        else:
            for v in obj.values():
                found.extend(_collect_ids(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_collect_ids(item))
    return found


def test_partial_cache_does_not_duplicate_or_refetch(interface):
    # Warm the cache for a and b.
    interface.fetch_batch([{"id": ["a", "b"]}], method="get", parse=True)
    assert interface.fetch_calls == [["a", "b"]]

    interface.fetch_calls.clear()

    # Now request a, b (cached) and c (missing).
    batch, _ = interface.fetch_batch([{"id": ["a", "b", "c"]}], method="get", parse=True)

    # Only the missing subquery is fetched; a and b are served from cache.
    assert interface.fetch_calls == [["c"]]

    # Every id appears exactly once -- no duplication of the cached subqueries.
    assert sorted(_collect_ids(batch)) == ["a", "b", "c"]
