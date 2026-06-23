"""Shared helpers for the offline interface test suite.

Fixtures are frozen raw API responses captured once (see ``tests/_capture``)
and committed under ``tests/fixtures/<api>/<case>.json``. Tests replay them
through ``responses`` so the default test run never touches the network.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

from bioseq_dl.core.interfaces.base import BaseAPIInterface

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def fixture_path(api: str, case: str) -> Path:
    """Return the path to a fixture file (``tests/fixtures/<api>/<case>.json``)."""
    return FIXTURES_DIR / api / f"{case}.json"


def load_fixture(api: str, case: str) -> Any:
    """Load a frozen API response fixture as parsed JSON.

    Return type is ``Any``: fixtures are heterogeneous (dict, list, or a JSON
    string for text APIs like KEGG/SABIO-RK), and tests index/call into them
    freely.
    """
    with fixture_path(api, case).open() as f:
        return json.load(f)


def load_fixture_text(api: str, case: str) -> str:
    """Load a fixture file as raw text (for non-JSON APIs such as KEGG)."""
    return fixture_path(api, case).read_text()


class FakeRecordsInterface(BaseAPIInterface):
    """Minimal offline ``BaseAPIInterface`` for engine-level tests.

    ``fetch`` turns each id of a (comma-joined string or list) query into a
    synthetic ``{"id": x, "value": "val<x>"}`` record and appends the id list it
    was called with to ``fetch_calls`` — enough to exercise caching, batching and
    provenance without a network or a real parser.
    """

    API_NAME = "Fake"
    METHODS: ClassVar[dict[str, Any]] = {
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
