"""Pure ChEBI query builder utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass

from bioseq_dl.core.workflow.chebi_query_catalog import get_chebi_query_builder_field_catalog
from bioseq_dl.core.workflow.query_interpreter import strip_surrounding_quotes
from bioseq_dl.gui.query_builders.common import quote_builder_value

CHEBI_ID_PATTERN = re.compile(r"^CHEBI:\d+$")


@dataclass(frozen=True)
class ChEBIQueryBuilderRow:
    """One row in a ChEBI entity query builder."""

    resource: str
    field: str
    value: str


def normalize_chebi_resource(resource: str) -> str:
    """Normalize a ChEBI resource key."""
    return str(resource).strip().lower()


def normalize_chebi_field(field: str) -> str:
    """Normalize a ChEBI field key."""
    return str(field).strip().lower()


def validate_chebi_builder_row(row: ChEBIQueryBuilderRow) -> None:
    """Validate one ChEBI query builder row."""
    resource = normalize_chebi_resource(row.resource)
    catalog = get_chebi_query_builder_field_catalog(resource)
    field = normalize_chebi_field(row.field)
    if field not in catalog:
        supported = ", ".join(catalog)
        msg = f"Unsupported ChEBI {resource} field '{row.field}'. Supported fields are: {supported}."
        raise ValueError(msg)

    value = strip_surrounding_quotes(str(row.value)).strip()
    if not value:
        msg = "ChEBI query builder value is required."
        raise ValueError(msg)
    if field == "chebi_id" and not CHEBI_ID_PATTERN.fullmatch(value):
        msg = "ChEBI IDs must use the CHEBI:<digits> format."
        raise ValueError(msg)


def build_chebi_parameter_fragment(row: ChEBIQueryBuilderRow) -> str:
    """Build one ChEBI interpreted-query parameter fragment."""
    field = normalize_chebi_field(row.field)
    value = strip_surrounding_quotes(str(row.value)).strip()
    if field == "chebi_id":
        return f"{field}={value}"
    return f"{field}={quote_builder_value(value)}"


def build_chebi_friendly_query(row: ChEBIQueryBuilderRow) -> str:
    """Build a human-readable ChEBI query preview."""
    return build_chebi_interpreted_query(row)


def build_chebi_interpreted_query(row: ChEBIQueryBuilderRow) -> str:
    """Build the final ChEBI query.value string from a query builder row."""
    validate_chebi_builder_row(row)
    resource = normalize_chebi_resource(row.resource)
    return f"chebi.{resource}:{build_chebi_parameter_fragment(row)}"
