"""Pure ChEBI query builder utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from bioseq_dl.core.workflow.chebi_query_catalog import get_chebi_query_builder_field_catalog
from bioseq_dl.core.workflow.query_interpreter import split_quoted_csv_values, strip_surrounding_quotes

if TYPE_CHECKING:
    from collections.abc import Sequence

RANGE_VALUE_COUNT = 2


@dataclass(frozen=True)
class ChEBIQueryBuilderRow:
    """One row in a ChEBI resource-specific query builder."""

    resource: str
    field: str
    operator: str
    value: str
    secondary_value: str | None = None


def normalize_chebi_resource(resource: str) -> str:
    """Normalize a ChEBI resource key."""
    return str(resource).strip().lower()


def normalize_chebi_field(field: str) -> str:
    """Normalize a ChEBI field key."""
    normalized = str(field).strip().lower()
    if normalized == "relation":
        return "ontology_relation"
    if normalized == "term":
        return "ontology_term"
    return normalized


def normalize_chebi_operator(operator: str) -> str:
    """Normalize a ChEBI operator or search mode."""
    return str(operator).strip().lower()


def quote_chebi_value(value: str) -> str:
    """Quote a ChEBI query value."""
    cleaned = strip_surrounding_quotes(str(value))
    escaped = cleaned.replace('"', '\\"')
    return f'"{escaped}"'


def split_chebi_builder_values(value: str) -> list[str]:
    """Split comma-separated ChEBI builder values."""
    return [
        strip_surrounding_quotes(item)
        for item in split_quoted_csv_values(str(value))
        if strip_surrounding_quotes(item)
    ]


def validate_chebi_range_value(value: str, field: str) -> None:
    """Validate a ChEBI range builder value."""
    values = split_chebi_builder_values(value)
    if len(values) != RANGE_VALUE_COUNT:
        msg = f"ChEBI field '{field}' range requires exactly two comma-separated values."
        raise ValueError(msg)
    for item in values:
        try:
            float(item)
        except ValueError as exc:
            msg = f"ChEBI field '{field}' range values must be numeric."
            raise ValueError(msg) from exc


def validate_chebi_builder_rows(rows: Sequence[ChEBIQueryBuilderRow]) -> None:
    """Validate ChEBI query builder rows."""
    if not rows:
        msg = "ChEBI query builder requires at least one condition."
        raise ValueError(msg)

    selected_resource: str | None = None
    for row in rows:
        resource = normalize_chebi_resource(row.resource)
        if selected_resource is None:
            selected_resource = resource
        elif resource != selected_resource:
            msg = "All rows in one ChEBI query builder must use the same resource."
            raise ValueError(msg)

        catalog = get_chebi_query_builder_field_catalog(resource)
        field = normalize_chebi_field(row.field)
        if field not in catalog:
            msg = f"ChEBI field '{row.field}' is not supported for resource '{row.resource}'."
            raise ValueError(msg)
        if resource == "ontology" and field != "ontology_relation":
            msg = "ChEBI ontology builder rows must use the ontology_relation field."
            raise ValueError(msg)

        operator = normalize_chebi_operator(row.operator)
        if operator not in catalog[field].supported_operators:
            msg = f"ChEBI operator '{row.operator}' is not supported for field '{field}'."
            raise ValueError(msg)

        if not strip_surrounding_quotes(str(row.value)).strip():
            msg = "ChEBI query builder value is required."
            raise ValueError(msg)
        if catalog[field].supports_range:
            validate_chebi_range_value(row.value, field)
        if resource == "ontology" and not str(row.secondary_value or "").strip():
            msg = "ChEBI ontology builder requires a term value."
            raise ValueError(msg)

    if selected_resource in {"ontology", "structure"} and len(rows) != 1:
        msg = f"ChEBI {selected_resource} builder requires exactly one condition."
        raise ValueError(msg)


def build_chebi_entity_fragment(row: ChEBIQueryBuilderRow) -> str:
    """Build one ChEBI entity query fragment."""
    field = normalize_chebi_field(row.field)
    operator = normalize_chebi_operator(row.operator)
    value = strip_surrounding_quotes(str(row.value)).strip()
    if operator == "contains" and field == "name":
        return f"name_contains={quote_chebi_value(value)}"
    if operator == "range":
        return f"{field}_range={','.join(split_chebi_builder_values(value))}"
    if field in {"name", "formula"}:
        return f"{field}={quote_chebi_value(value)}"
    return f"{field}={value}"


def build_chebi_ontology_fragments(row: ChEBIQueryBuilderRow) -> list[str]:
    """Build ChEBI ontology query fragments."""
    relation = strip_surrounding_quotes(str(row.value)).strip()
    term = strip_surrounding_quotes(str(row.secondary_value or "")).strip()
    return [f"relation={relation}", f"term={term}"]


def build_chebi_structure_fragment(row: ChEBIQueryBuilderRow) -> str:
    """Build one ChEBI structure query fragment."""
    field = normalize_chebi_field(row.field)
    value = strip_surrounding_quotes(str(row.value)).strip()
    return f"{field}={quote_chebi_value(value)}"


def build_chebi_query_fragments(rows: Sequence[ChEBIQueryBuilderRow]) -> list[str]:
    """Build ChEBI interpreted-query fragments from validated rows."""
    resource = normalize_chebi_resource(rows[0].resource)
    if resource == "ontology":
        return build_chebi_ontology_fragments(rows[0])
    if resource == "structure":
        return [build_chebi_structure_fragment(rows[0])]
    return [build_chebi_entity_fragment(row) for row in rows]


def build_chebi_friendly_query(rows: Sequence[ChEBIQueryBuilderRow]) -> str:
    """Build a human-readable ChEBI query preview."""
    return build_chebi_interpreted_query(rows)


def build_chebi_interpreted_query(rows: Sequence[ChEBIQueryBuilderRow]) -> str:
    """Build the final ChEBI query.value string from query builder rows."""
    validate_chebi_builder_rows(rows)
    resource = normalize_chebi_resource(rows[0].resource)
    fragments = build_chebi_query_fragments(rows)
    return f"chebi.{resource}:" + " AND ".join(fragments)
