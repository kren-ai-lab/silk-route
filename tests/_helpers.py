"""Shared helpers for the offline interface test suite.

Fixtures are frozen raw API responses captured once (see ``tests/_capture``)
and committed under ``tests/fixtures/<api>/<case>.json``. Tests replay them
through ``responses`` so the default test run never touches the network.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
