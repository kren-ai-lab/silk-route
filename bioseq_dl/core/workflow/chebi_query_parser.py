"""Parse ChEBI query-builder strings into request-plan dictionaries."""

from __future__ import annotations

import math
import re

from bioseq_dl.core.workflow.chebi_query_catalog import (
    ENTITY_SEARCH_MODEL,
    ONTOLOGY_SEARCH_MODEL,
    STRUCTURE_SEARCH_MODEL,
    get_chebi_query_builder_resource_catalog,
)
from bioseq_dl.core.workflow.query_prefixes import is_source_prefixed_query

CHEBI_QUERY_PATTERN = re.compile(r"^chebi\.(?P<resource>[a-z_]+):(?P<body>.+)$")
CHEBI_BUILDER_QUERY_PREFIXES = ("chebi.entity:", "chebi.ontology:", "chebi.structure:")
CHEBI_ID_PATTERN = re.compile(r"^CHEBI:\d+$")
MIN_QUOTED_VALUE_LENGTH = 2
CHEBI_STAR_MIN = 1
CHEBI_STAR_MAX = 3
RANGE_VALUE_COUNT = 2

ENTITY_FIELD_NAMES = (
    "chebi_id",
    "name_contains",
    "name",
    "formula",
    "average_mass_range",
    "monoisotopic_mass_range",
    "charge_range",
    "database_xref",
    "star",
)
ONTOLOGY_FIELD_NAMES = ("relation", "term")
STRUCTURE_FIELD_NAMES = ("connectivity", "substructure", "similarity")
ENTITY_FIELDS = frozenset(ENTITY_FIELD_NAMES)
ONTOLOGY_FIELDS = frozenset(ONTOLOGY_FIELD_NAMES)
STRUCTURE_FIELDS = frozenset(STRUCTURE_FIELD_NAMES)


def is_chebi_prefixed_query(query: str) -> bool:
    """Return whether the query uses a ChEBI builder prefix."""
    normalized = str(query or "").strip().lower()
    return is_source_prefixed_query(query, "chebi") and normalized.startswith(CHEBI_BUILDER_QUERY_PREFIXES)


def format_chebi_supported_fields(fields: tuple[str, ...]) -> str:
    """Format supported ChEBI executable fields for an error message."""
    return ", ".join(fields)


def get_chebi_prefixed_query_resource(query: str) -> str | None:
    """Return the ChEBI resource name from a prefixed query, if present."""
    match = CHEBI_QUERY_PATTERN.match(str(query or "").strip())
    if not match:
        return None
    return match.group("resource")


def strip_chebi_value_quotes(value: str) -> str:
    """Strip one matching pair of surrounding quotes from a ChEBI value."""
    stripped = value.strip()
    if len(stripped) >= MIN_QUOTED_VALUE_LENGTH and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        return stripped[1:-1]
    return stripped


def split_chebi_conditions(body: str) -> list[str]:
    """Split a ChEBI query-builder body into AND-separated conditions."""
    return [fragment.strip() for fragment in body.split(" AND ") if fragment.strip()]


def split_chebi_condition(fragment: str) -> tuple[str, str]:
    """Split one ChEBI query condition into field and value."""
    if "=" not in fragment:
        msg = f"Invalid ChEBI query condition '{fragment}'."
        raise ValueError(msg)
    field, value = fragment.split("=", 1)
    field = field.strip()
    value = strip_chebi_value_quotes(value)
    if not field or not value:
        msg = f"Invalid ChEBI query condition '{fragment}'."
        raise ValueError(msg)
    return field, value


def parse_chebi_number(value: str, field: str) -> float:
    """Parse a numeric ChEBI value."""
    try:
        parsed = float(value)
    except ValueError as exc:
        msg = f"ChEBI {field} values must be numeric."
        raise ValueError(msg) from exc
    if not math.isfinite(parsed):
        msg = f"ChEBI {field} values must be finite numbers."
        raise ValueError(msg)
    return parsed


def parse_chebi_numeric_range(value: str, field: str) -> tuple[float, float]:
    """Parse and validate a ChEBI numeric range."""
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != RANGE_VALUE_COUNT or not all(parts):
        msg = f"ChEBI {field} must be a comma-separated low,high range."
        raise ValueError(msg)
    low = parse_chebi_number(parts[0], field)
    high = parse_chebi_number(parts[1], field)
    if low > high:
        msg = f"ChEBI {field} low value must be less than or equal to high value."
        raise ValueError(msg)
    return low, high


def parse_chebi_int_range(value: str, field: str) -> tuple[int, int]:
    """Parse and validate a ChEBI integer range."""
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != RANGE_VALUE_COUNT or not all(parts):
        msg = f"ChEBI {field} must be a comma-separated low,high range."
        raise ValueError(msg)
    if not all(re.fullmatch(r"[+-]?\d+", part) for part in parts):
        msg = f"ChEBI {field} values must be integers."
        raise ValueError(msg)
    low = int(parts[0])
    high = int(parts[1])
    if low > high:
        msg = f"ChEBI {field} low value must be less than or equal to high value."
        raise ValueError(msg)
    return low, high


def parse_chebi_star(value: str) -> int:
    """Parse a ChEBI star rating value."""
    if not re.fullmatch(r"\d+", value):
        msg = "ChEBI star must be an integer from 1 to 3."
        raise ValueError(msg)
    star = int(value)
    if star < CHEBI_STAR_MIN or star > CHEBI_STAR_MAX:
        msg = "ChEBI star must be an integer from 1 to 3."
        raise ValueError(msg)
    return star


def normalize_chebi_entity_parameter(field: str, value: str) -> tuple[str, object]:
    """Normalize one ChEBI entity search parameter."""
    if field == "chebi_id":
        if not CHEBI_ID_PATTERN.fullmatch(value):
            msg = "ChEBI IDs must use the CHEBI:<digits> format."
            raise ValueError(msg)
        return field, value
    if field in {"name_contains", "name", "formula", "database_xref"}:
        return field, value
    if field in {"average_mass_range", "monoisotopic_mass_range"}:
        low, high = parse_chebi_numeric_range(value, field)
        return field, (low, high)
    if field == "charge_range":
        low, high = parse_chebi_int_range(value, field)
        return field, (low, high)
    if field == "star":
        return field, parse_chebi_star(value)
    msg = f"Unsupported ChEBI entity field '{field}'."
    raise ValueError(msg)


def parse_chebi_entity_parameters(fragments: list[str]) -> dict[str, object]:
    """Parse ChEBI entity search parameters."""
    parameters: dict[str, object] = {}
    for fragment in fragments:
        field, value = split_chebi_condition(fragment)
        if field not in ENTITY_FIELDS:
            supported = format_chebi_supported_fields(ENTITY_FIELD_NAMES)
            msg = f"Unsupported ChEBI entity field '{field}'. Supported fields are: {supported}."
            raise ValueError(msg)
        normalized_field, normalized_value = normalize_chebi_entity_parameter(field, value)
        parameters[normalized_field] = normalized_value
    return parameters


def parse_chebi_ontology_parameters(fragments: list[str]) -> dict[str, object]:
    """Parse ChEBI ontology search parameters."""
    parameters: dict[str, object] = {}
    for fragment in fragments:
        field, value = split_chebi_condition(fragment)
        if field not in ONTOLOGY_FIELDS:
            supported = format_chebi_supported_fields(ONTOLOGY_FIELD_NAMES)
            msg = f"Unsupported ChEBI ontology field '{field}'. Supported fields are: {supported}."
            raise ValueError(msg)
        parameters[field] = value
    if "relation" not in parameters or "term" not in parameters:
        msg = "ChEBI ontology queries require relation and term."
        raise ValueError(msg)
    return parameters


def parse_chebi_structure_parameters(fragments: list[str]) -> dict[str, object]:
    """Parse ChEBI structure search parameters."""
    if len(fragments) != 1:
        msg = "ChEBI structure queries require exactly one structure condition."
        raise ValueError(msg)
    field, value = split_chebi_condition(fragments[0])
    if field not in STRUCTURE_FIELDS:
        supported = format_chebi_supported_fields(STRUCTURE_FIELD_NAMES)
        msg = f"Unsupported ChEBI structure field '{field}'. Supported fields are: {supported}."
        raise ValueError(msg)
    return {field: value}


def parse_chebi_query_builder_string(query: str) -> dict[str, object]:
    """Parse a ChEBI query-builder string into a pure request plan."""
    match = CHEBI_QUERY_PATTERN.match(str(query).strip())
    if not match:
        msg = "ChEBI query builder strings must start with 'chebi.<resource>:'."
        raise ValueError(msg)

    resources = get_chebi_query_builder_resource_catalog()
    resource_key = match.group("resource")
    if resource_key not in resources:
        supported = ", ".join(resources)
        msg = f"Unsupported ChEBI resource '{resource_key}'. Supported resources are: {supported}."
        raise ValueError(msg)

    fragments = split_chebi_conditions(match.group("body"))
    if not fragments:
        msg = "ChEBI query builder string must contain at least one condition."
        raise ValueError(msg)

    if resource_key == "entity":
        parameters = parse_chebi_entity_parameters(fragments)
        query_model = ENTITY_SEARCH_MODEL
    elif resource_key == "ontology":
        parameters = parse_chebi_ontology_parameters(fragments)
        query_model = ONTOLOGY_SEARCH_MODEL
    elif resource_key == "structure":
        parameters = parse_chebi_structure_parameters(fragments)
        query_model = STRUCTURE_SEARCH_MODEL
    else:
        supported = ", ".join(resources)
        msg = f"Unsupported ChEBI resource '{resource_key}'. Supported resources are: {supported}."
        raise ValueError(msg)

    return {
        "source": "chebi",
        "resource": resource_key,
        "query_model": query_model,
        "parameters": parameters,
    }
