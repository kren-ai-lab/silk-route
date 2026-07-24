"""Parse ChEBI query-builder strings into request-plan dictionaries."""

from __future__ import annotations

import re

from silkroute.core.workflow.chebi_query_catalog import (
    ENTITY_QUERY_MODEL,
    get_chebi_query_builder_resource_catalog,
)
from silkroute.core.workflow.query_prefixes import (
    is_source_prefixed_query,
    split_and_conditions,
    split_field_value_condition,
)

CHEBI_QUERY_PATTERN = re.compile(r"^chebi\.(?P<resource>[a-z_]+):(?P<body>.+)$", re.IGNORECASE)
CHEBI_BUILDER_QUERY_PREFIXES = ("chebi.entity:",)
CHEBI_ID_PATTERN = re.compile(r"^CHEBI:\d+$")

ENTITY_FIELD_NAMES = ("chebi_id", "name", "name_contains")
ENTITY_FIELDS = frozenset(ENTITY_FIELD_NAMES)


def is_chebi_prefixed_query(query: str) -> bool:
    """Return whether the query uses an executable ChEBI builder prefix."""
    return is_source_prefixed_query(query, "chebi")


def get_chebi_prefixed_query_resource(query: str) -> str | None:
    """Return the ChEBI resource name from a prefixed query, if present."""
    match = CHEBI_QUERY_PATTERN.match(str(query or "").strip())
    if not match:
        return None
    return match.group("resource").lower()


def parse_chebi_entity_parameters(fragments: list[str]) -> dict[str, object]:
    """Parse executable ChEBI entity search parameters."""
    if len(fragments) != 1:
        msg = "ChEBI entity queries require exactly one executable condition."
        raise ValueError(msg)
    field, value = split_field_value_condition(fragments[0], "ChEBI")
    if field not in ENTITY_FIELDS:
        supported = ", ".join(ENTITY_FIELD_NAMES)
        msg = f"Unsupported ChEBI entity field '{field}'. Supported fields are: {supported}."
        raise ValueError(msg)
    if field == "chebi_id" and not CHEBI_ID_PATTERN.fullmatch(value):
        msg = "ChEBI IDs must use the CHEBI:<digits> format."
        raise ValueError(msg)
    return {field: value}


def parse_chebi_query_builder_string(query: str) -> dict[str, object]:
    """Parse a ChEBI query-builder string into a pure request plan."""
    match = CHEBI_QUERY_PATTERN.match(str(query).strip())
    if not match:
        msg = "ChEBI query builder strings must start with 'chebi.<resource>:'."
        raise ValueError(msg)

    resources = get_chebi_query_builder_resource_catalog()
    resource_key = match.group("resource").lower()
    if resource_key not in resources:
        supported = ", ".join(resources)
        msg = f"Unsupported ChEBI resource '{resource_key}'. Supported resources are: {supported}."
        raise ValueError(msg)

    fragments = split_and_conditions(match.group("body"))
    if not fragments:
        msg = "ChEBI query builder string must contain at least one condition."
        raise ValueError(msg)

    return {
        "source": "chebi",
        "resource": resource_key,
        "query_model": ENTITY_QUERY_MODEL,
        "parameters": parse_chebi_entity_parameters(fragments),
    }
