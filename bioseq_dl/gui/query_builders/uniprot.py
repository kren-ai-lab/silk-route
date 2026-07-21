"""Pure UniProt query builder utilities for future GUI rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from bioseq_dl.core.workflow.query_field_catalog import (
    UniProtQueryFieldCatalogEntry,
    get_uniprot_query_builder_field_catalog,
)
from bioseq_dl.core.workflow.query_interpreter import (
    build_default_uniprot_interpreter,
    split_quoted_csv_values,
    strip_surrounding_quotes,
)
from bioseq_dl.gui.query_builders.common import format_builder_row_error

if TYPE_CHECKING:
    from collections.abc import Sequence

ALLOWED_CONNECTORS = {"AND", "OR"}
ALLOWED_MATCH_MODES = {"any", "all", "not"}
READABLE_MATCH_MODES = "any, all, or not"


@dataclass(frozen=True)
class UniProtQueryBuilderRow:
    """One row in the future UniProt advanced query builder."""

    connector: str | None
    field: str
    values: str
    match_mode: str


def normalize_query_builder_connector(connector: str | None) -> str | None:
    """Normalize a query builder connector value."""
    if connector is None:
        return None
    normalized = str(connector).strip().upper()
    return normalized or None


def normalize_query_builder_field(field: str) -> str:
    """Normalize a query builder field key."""
    return str(field).strip().lower()


def normalize_query_builder_match_mode(match_mode: str) -> str:
    """Normalize a query builder match mode."""
    return str(match_mode).strip().lower()


def quote_uniprot_friendly_value(value: str) -> str:
    """Quote a friendly query value when it contains whitespace."""
    cleaned = strip_surrounding_quotes(value)
    if any(char.isspace() for char in cleaned):
        escaped = cleaned.replace('"', '\\"')
        return f'"{escaped}"'
    return cleaned


def format_uniprot_friendly_values(values: str) -> str:
    """Format comma-separated row values for friendly UniProt query syntax."""
    parts = [strip_surrounding_quotes(part) for part in split_quoted_csv_values(values)]
    return ",".join(quote_uniprot_friendly_value(part) for part in parts)


def get_uniprot_query_builder_field_metadata(field: str) -> UniProtQueryFieldCatalogEntry:
    """Return metadata for one field visible in the UniProt query builder."""
    normalized_field = normalize_query_builder_field(field)
    catalog = get_uniprot_query_builder_field_catalog()
    if normalized_field not in catalog:
        msg = f"Field '{field}' is not supported by the UniProt query builder."
        raise ValueError(msg)
    return catalog[normalized_field]


def validate_uniprot_query_builder_rows(rows: Sequence[UniProtQueryBuilderRow]) -> None:
    """Validate future UniProt query builder rows."""
    catalog = get_uniprot_query_builder_field_catalog()
    for index, row in enumerate(rows):
        connector = normalize_query_builder_connector(row.connector)
        if index == 0:
            if connector is not None:
                msg = format_builder_row_error(index, "connector is not used for the first condition.")
                raise ValueError(msg)
        elif connector not in ALLOWED_CONNECTORS:
            msg = format_builder_row_error(index, "connector must be AND or OR.")
            raise ValueError(msg)

        field = normalize_query_builder_field(row.field)
        if field not in catalog:
            msg = format_builder_row_error(
                index,
                "field is not supported by the UniProt query builder.",
            )
            raise ValueError(msg)

        match_mode = normalize_query_builder_match_mode(row.match_mode)
        if match_mode not in ALLOWED_MATCH_MODES:
            msg = format_builder_row_error(
                index,
                f"match mode must be {READABLE_MATCH_MODES}.",
            )
            raise ValueError(msg)
        if match_mode not in catalog[field].supported_match_modes:
            msg = format_builder_row_error(
                index,
                f"field '{field}' does not support match mode '{match_mode}'.",
            )
            raise ValueError(msg)

        if not split_quoted_csv_values(row.values):
            msg = format_builder_row_error(index, "values are required.")
            raise ValueError(msg)


def build_uniprot_friendly_query(rows: Sequence[UniProtQueryBuilderRow]) -> str:
    """Build a friendly UniProt query string from advanced query builder rows."""
    validate_uniprot_query_builder_rows(rows)
    fragments: list[str] = []
    for index, row in enumerate(rows):
        connector = normalize_query_builder_connector(row.connector)
        field = normalize_query_builder_field(row.field)
        match_mode = normalize_query_builder_match_mode(row.match_mode)
        values = format_uniprot_friendly_values(row.values)
        fragment = f"{field}_{match_mode}:{values}"
        if index > 0 and connector:
            fragments.append(connector)
        fragments.append(fragment)
    return " ".join(fragments)


def build_uniprot_interpreted_query(rows: Sequence[UniProtQueryBuilderRow]) -> str:
    """Build the final interpreted UniProt query string from advanced query builder rows."""
    friendly_query = build_uniprot_friendly_query(rows)
    interpreter = build_default_uniprot_interpreter()
    return interpreter.interpret(friendly_query)
