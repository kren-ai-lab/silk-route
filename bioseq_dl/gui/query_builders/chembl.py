"""Pure ChEMBL query builder utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from bioseq_dl.core.workflow.chembl_query_catalog import (
    FLAT_PARAMETERS_MODEL,
    OPERATOR_SUFFIXES,
    get_chembl_query_builder_field_catalog,
    get_chembl_query_builder_resource_catalog,
)
from bioseq_dl.core.workflow.query_interpreter import split_quoted_csv_values, strip_surrounding_quotes

if TYPE_CHECKING:
    from collections.abc import Sequence

RANGE_VALUE_COUNT = 2


@dataclass(frozen=True)
class ChEMBLFilterQueryBuilderRow:
    """One row in a ChEMBL resource-specific query builder."""

    resource: str
    field: str
    filter_type: str
    value: str


def normalize_chembl_resource(resource: str) -> str:
    """Normalize a ChEMBL resource key."""
    return str(resource).strip().lower()


def normalize_chembl_field(field: str) -> str:
    """Normalize a ChEMBL field key."""
    return str(field).strip()


def normalize_chembl_filter_type(filter_type: str) -> str:
    """Normalize a ChEMBL filter type or operator."""
    return str(filter_type).strip().lower()


def split_chembl_builder_values(value: str) -> list[str]:
    """Split comma-separated ChEMBL builder values and strip surrounding quotes."""
    return [
        strip_surrounding_quotes(item)
        for item in split_quoted_csv_values(str(value))
        if strip_surrounding_quotes(item)
    ]


def format_chembl_builder_row_error(row_index: int, message: str) -> str:
    """Return a user-facing ChEMBL builder validation error."""
    return f"Row {row_index + 1}: {message}"


def validate_chembl_builder_rows(rows: Sequence[ChEMBLFilterQueryBuilderRow]) -> None:
    """Validate ChEMBL query builder rows."""
    resources = get_chembl_query_builder_resource_catalog()
    selected_resource: str | None = None
    if not rows:
        msg = "ChEMBL query builder requires at least one condition."
        raise ValueError(msg)

    for index, row in enumerate(rows):
        resource = normalize_chembl_resource(row.resource)
        if resource not in resources:
            msg = format_chembl_builder_row_error(index, f"resource '{row.resource}' is not supported.")
            raise ValueError(msg)
        if selected_resource is None:
            selected_resource = resource
        elif resource != selected_resource:
            msg = format_chembl_builder_row_error(
                index,
                "all rows in one ChEMBL query builder must use the same resource.",
            )
            raise ValueError(msg)

        fields = get_chembl_query_builder_field_catalog(resource)
        field = normalize_chembl_field(row.field)
        if field not in fields:
            msg = format_chembl_builder_row_error(index, f"field '{row.field}' is not supported.")
            raise ValueError(msg)

        filter_type = normalize_chembl_filter_type(row.filter_type)
        if filter_type not in fields[field].allowed_operators:
            msg = format_chembl_builder_row_error(
                index,
                f"operator '{row.filter_type}' is not allowed for field '{field}'.",
            )
            raise ValueError(msg)

        values = split_chembl_builder_values(row.value)
        if not values:
            msg = format_chembl_builder_row_error(index, "value is required.")
            raise ValueError(msg)
        if filter_type == "range" and len(values) != RANGE_VALUE_COUNT:
            msg = format_chembl_builder_row_error(index, "range requires exactly two comma-separated values.")
            raise ValueError(msg)
        if filter_type == "in" and not values:
            msg = format_chembl_builder_row_error(index, "in requires at least one value.")
            raise ValueError(msg)


def build_chembl_parameter_fragment(row: ChEMBLFilterQueryBuilderRow) -> str:
    """Build one ChEMBL interpreted-query field fragment.

    Operator suffixes follow ChEMBL-style filter names: exact has no suffix,
    while operators such as icontains, in, gte, and range map to __icontains,
    __in, __gte, and __range respectively.
    """
    field = normalize_chembl_field(row.field)
    filter_type = normalize_chembl_filter_type(row.filter_type)
    suffix = OPERATOR_SUFFIXES[filter_type]
    values = ",".join(split_chembl_builder_values(row.value))
    return f"{field}{suffix}={values}"


def build_chembl_friendly_query(rows: Sequence[ChEMBLFilterQueryBuilderRow]) -> str:
    """Build a human-readable ChEMBL query preview."""
    return build_chembl_interpreted_query(rows)


def build_chembl_interpreted_query(rows: Sequence[ChEMBLFilterQueryBuilderRow]) -> str:
    """Build the final ChEMBL query.value string from query builder rows."""
    validate_chembl_builder_rows(rows)
    resource = normalize_chembl_resource(rows[0].resource)
    fragments = [build_chembl_parameter_fragment(row) for row in rows]
    return f"chembl.{resource}:" + " AND ".join(fragments)


def get_chembl_builder_query_model(resource: str) -> str:
    """Return the ChEMBL query model for one builder resource."""
    resources = get_chembl_query_builder_resource_catalog()
    normalized_resource = normalize_chembl_resource(resource)
    if normalized_resource not in resources:
        msg = f"Unsupported ChEMBL query resource '{resource}'."
        raise ValueError(msg)
    return resources[normalized_resource].query_model


def is_chembl_flat_parameter_resource(resource: str) -> bool:
    """Return whether a ChEMBL resource uses flat parameters."""
    return get_chembl_builder_query_model(resource) == FLAT_PARAMETERS_MODEL
