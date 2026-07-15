"""Source-prefixed workflow query helpers."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

SOURCE_QUERY_PREFIX_PATTERN = re.compile(r"^(?P<source>[a-z][a-z0-9_]*)\.[a-z_]+:")
SUPPORTED_SOURCE_PREFIXES = ("chembl", "pubchem", "chebi")


def get_query_source_prefix(query: str) -> str | None:
    """Return the source prefix for a builder query, if present."""
    match = SOURCE_QUERY_PREFIX_PATTERN.match(str(query or "").strip().lower())
    if not match:
        return None
    return match.group("source")


def is_source_prefixed_query(query: str, source: str) -> bool:
    """Return whether a query starts with a source-specific builder prefix."""
    return get_query_source_prefix(query) == str(source or "").strip().lower()


def is_any_source_prefixed_query(query: str, sources: Iterable[str]) -> bool:
    """Return whether a query starts with any source in an iterable."""
    source = get_query_source_prefix(query)
    if source is None:
        return False
    return source in {str(candidate or "").strip().lower() for candidate in sources}


def is_supported_source_prefixed_query(query: str) -> bool:
    """Return whether a query uses a source prefix recognized by workflow planning."""
    return is_any_source_prefixed_query(query, SUPPORTED_SOURCE_PREFIXES)
