"""Source-prefixed workflow query helpers."""

from __future__ import annotations

import re

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


def is_supported_source_prefixed_query(query: str) -> bool:
    """Return whether a query uses a source prefix recognized by workflow planning."""
    source = get_query_source_prefix(query)
    return source in SUPPORTED_SOURCE_PREFIXES
