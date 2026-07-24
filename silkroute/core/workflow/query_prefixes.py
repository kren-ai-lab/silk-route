"""Source-prefixed workflow query helpers."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from silkroute.core.workflow.query_interpreter import strip_surrounding_quotes

if TYPE_CHECKING:
    from collections.abc import Iterable

SOURCE_QUERY_PREFIX_PATTERN = re.compile(r"^(?P<source>[a-z][a-z0-9_]*)\.[a-z_]+:")


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


def split_and_conditions(body: str) -> list[str]:
    """Split a source query-builder body into AND-separated conditions."""
    return [fragment.strip() for fragment in body.split(" AND ") if fragment.strip()]


def split_field_value_condition(fragment: str, source_label: str) -> tuple[str, str]:
    """Split one ``field=value`` condition, raising with the source label if malformed."""
    if "=" not in fragment:
        msg = f"Invalid {source_label} query condition '{fragment}'."
        raise ValueError(msg)
    field, value = fragment.split("=", 1)
    field = field.strip()
    value = strip_surrounding_quotes(value)
    if not field or not value:
        msg = f"Invalid {source_label} query condition '{fragment}'."
        raise ValueError(msg)
    return field, value
