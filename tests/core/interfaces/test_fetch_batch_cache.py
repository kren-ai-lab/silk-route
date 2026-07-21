"""Regression test for fetch_batch partial-cache handling.

When a batch query decomposes into several subqueries and only some are cached,
the whole query was marked for refetch *and* the cached subqueries were appended
separately, duplicating them in the output.
"""

from __future__ import annotations

import pytest

from tests._helpers import FakeRecordsInterface


@pytest.fixture
def interface(tmp_path):
    return FakeRecordsInterface(cache_dir=str(tmp_path))


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


def test_fetch_batch_records_metadata_for_bare_value_override(tmp_path):
    # A fetch_single override returning a bare (non-tuple) value is still tracked as fetched.
    class BareInterface(FakeRecordsInterface):
        def fetch_single(self, query, parse=False, *args, **kwargs):
            return f"bare-{query}"

    iface = BareInterface(cache_dir=str(tmp_path))
    data, metadata = iface.fetch_batch(["x", "y"], method="get")

    assert set(data) == {"bare-x", "bare-y"}
    fetched_ids = metadata.get("fetched", {}).get("ids", [])
    assert len(fetched_ids) == 2
