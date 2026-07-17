"""Pure ChEMBL query builder utilities."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from bioseq_dl.core.workflow.chembl_query_catalog import (
    OPERATOR_SUFFIXES,
    get_chembl_query_builder_field_catalog,
    get_chembl_query_builder_resource_catalog,
)
from bioseq_dl.core.workflow.query_interpreter import (
    normalize_standard_units,
    split_quoted_csv_values,
    strip_surrounding_quotes,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

RANGE_VALUE_COUNT = 2
CHEMBL_IC50_BUILDER_KEY = "chembl_ic50"
IC50_BUILDER_TYPE = "ic50_activity"
IC50_CONDITIONS = (
    "range",
    "less_than",
    "less_than_or_equal",
    "greater_than",
    "greater_than_or_equal",
    "exact",
)
IC50_STANDARD_UNITS = ("nM", "uM", "mM", "pM")
IC50_CONDITION_OPERATOR = {
    "less_than": "<",
    "less_than_or_equal": "<=",
    "greater_than": ">",
    "greater_than_or_equal": ">=",
    "exact": "",
}
IC50_FRIENDLY_CONDITION = {
    "less_than": "less than",
    "less_than_or_equal": "less than or equal to",
    "greater_than": "greater than",
    "greater_than_or_equal": "greater than or equal to",
    "exact": "equal to",
}


@dataclass(frozen=True)
class ChEMBLFilterQueryBuilderRow:
    """One row in a ChEMBL resource-specific query builder."""

    resource: str
    field: str
    filter_type: str
    value: str


@dataclass(frozen=True)
class ChEMBLIC50QueryBuilderRow:
    """One row in the dedicated ChEMBL IC50 activity builder."""

    condition: str = "range"
    minimum: int | float | None = 0
    maximum: int | float | None = 10
    value: int | float | None = None
    unit: str = "nM"


def get_chembl_ic50_query_builder_field_catalog() -> dict[str, object]:
    """Return an empty catalog because the IC50 builder uses dedicated controls."""
    return {}


def make_default_chembl_ic50_builder_row() -> dict[str, object]:
    """Return a fresh default ChEMBL IC50 builder row state."""
    return {
        "condition": "range",
        "minimum": 0,
        "maximum": 10,
        "value": None,
        "unit": "nM",
    }


def get_chembl_ic50_row_value(row: object, key: str, default: object = None) -> object:
    """Return one IC50 row value from a mapping or row object."""
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def normalize_chembl_resource(resource: str) -> str:
    """Normalize a ChEMBL resource key."""
    return str(resource).strip().lower()


def normalize_chembl_field(field: str) -> str:
    """Normalize a ChEMBL field key."""
    return str(field).strip()


def normalize_chembl_filter_type(filter_type: str) -> str:
    """Normalize a ChEMBL filter type or operator."""
    return str(filter_type).strip().lower()


def normalize_chembl_ic50_condition(value: object) -> str:
    """Normalize and validate a ChEMBL IC50 condition."""
    normalized = str(value or "").strip().lower()
    if normalized not in IC50_CONDITIONS:
        allowed = ", ".join(IC50_CONDITIONS)
        msg = f"Unsupported IC50 condition '{value}'. Choose one of: {allowed}."
        raise ValueError(msg)
    return normalized


def normalize_chembl_ic50_unit(value: object) -> str:
    """Normalize and validate a ChEMBL IC50 standard unit."""
    normalized = normalize_standard_units(str(value or ""))
    if normalized not in IC50_STANDARD_UNITS:
        allowed = ", ".join(IC50_STANDARD_UNITS)
        msg = f"Unsupported IC50 standard unit '{value}'. Choose one of: {allowed}."
        raise ValueError(msg)
    return normalized


def normalize_chembl_ic50_number(value: object, field_name: str) -> int | float:
    """Normalize one required finite IC50 numeric value."""
    if isinstance(value, bool) or value is None:
        msg = f"IC50 {field_name} is required and must be a finite number."
        raise ValueError(msg)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            msg = f"IC50 {field_name} must be a finite number."
            raise ValueError(msg)
        return int(value) if value.is_integer() else value
    text = str(value).strip()
    if not text:
        msg = f"IC50 {field_name} is required and must be a finite number."
        raise ValueError(msg)
    try:
        parsed = float(text)
    except ValueError as exc:
        msg = f"IC50 {field_name} must be a finite number."
        raise ValueError(msg) from exc
    if not math.isfinite(parsed):
        msg = f"IC50 {field_name} must be a finite number."
        raise ValueError(msg)
    return int(parsed) if parsed.is_integer() else parsed


def format_chembl_ic50_number(value: float) -> str:
    """Format an IC50 number without changing its numeric meaning."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def normalize_chembl_ic50_builder_row(row: object) -> ChEMBLIC50QueryBuilderRow:
    """Normalize a mapping or row object into a ChEMBL IC50 builder row."""
    condition = normalize_chembl_ic50_condition(get_chembl_ic50_row_value(row, "condition", "range"))
    unit = normalize_chembl_ic50_unit(get_chembl_ic50_row_value(row, "unit", "nM"))
    minimum = get_chembl_ic50_row_value(row, "minimum", None)
    maximum = get_chembl_ic50_row_value(row, "maximum", None)
    value = get_chembl_ic50_row_value(row, "value", None)
    if condition == "range":
        minimum = normalize_chembl_ic50_number(minimum, "minimum")
        maximum = normalize_chembl_ic50_number(maximum, "maximum")
    else:
        value = normalize_chembl_ic50_number(value, "value")
    return ChEMBLIC50QueryBuilderRow(
        condition=condition,
        minimum=minimum,
        maximum=maximum,
        value=value,
        unit=unit,
    )


def validate_chembl_ic50_builder_row(row: ChEMBLIC50QueryBuilderRow) -> None:
    """Validate one dedicated ChEMBL IC50 builder row."""
    condition = normalize_chembl_ic50_condition(row.condition)
    normalize_chembl_ic50_unit(row.unit)
    if condition == "range":
        minimum = normalize_chembl_ic50_number(row.minimum, "minimum")
        maximum = normalize_chembl_ic50_number(row.maximum, "maximum")
        if minimum >= maximum:
            msg = "IC50 minimum must be less than IC50 maximum."
            raise ValueError(msg)
        return
    normalize_chembl_ic50_number(row.value, "value")


def build_chembl_ic50_interpreted_query(row: ChEMBLIC50QueryBuilderRow) -> str:
    """Build the executable ChEMBL IC50 macro query."""
    normalized = normalize_chembl_ic50_builder_row(row)
    validate_chembl_ic50_builder_row(normalized)
    unit = normalize_chembl_ic50_unit(normalized.unit)
    if normalized.condition == "range":
        minimum = normalize_chembl_ic50_number(normalized.minimum, "minimum")
        maximum = normalize_chembl_ic50_number(normalized.maximum, "maximum")
        return (
            f"ic50:{format_chembl_ic50_number(minimum)}-{format_chembl_ic50_number(maximum)} "
            f"AND standard_units:{unit}"
        )
    value = normalize_chembl_ic50_number(normalized.value, "value")
    operator = IC50_CONDITION_OPERATOR[normalized.condition]
    return f"ic50:{operator}{format_chembl_ic50_number(value)} AND standard_units:{unit}"


def build_chembl_ic50_friendly_query(row: ChEMBLIC50QueryBuilderRow) -> str:
    """Build the human-readable ChEMBL IC50 preview."""
    normalized = normalize_chembl_ic50_builder_row(row)
    validate_chembl_ic50_builder_row(normalized)
    unit = normalize_chembl_ic50_unit(normalized.unit)
    if normalized.condition == "range":
        minimum = normalize_chembl_ic50_number(normalized.minimum, "minimum")
        maximum = normalize_chembl_ic50_number(normalized.maximum, "maximum")
        return (
            f"IC50 between {format_chembl_ic50_number(minimum)} "
            f"and {format_chembl_ic50_number(maximum)} {unit}"
        )
    value = normalize_chembl_ic50_number(normalized.value, "value")
    phrase = IC50_FRIENDLY_CONDITION[normalized.condition]
    return f"IC50 {phrase} {format_chembl_ic50_number(value)} {unit}"


def serialize_chembl_ic50_metadata_row(row: ChEMBLIC50QueryBuilderRow) -> dict[str, object]:
    """Serialize one validated IC50 builder row into query-builder-v1 metadata."""
    normalized = normalize_chembl_ic50_builder_row(row)
    validate_chembl_ic50_builder_row(normalized)
    metadata: dict[str, object] = {
        "condition": normalized.condition,
        "unit": normalize_chembl_ic50_unit(normalized.unit),
    }
    if normalized.condition == "range":
        metadata["minimum"] = normalize_chembl_ic50_number(normalized.minimum, "minimum")
        metadata["maximum"] = normalize_chembl_ic50_number(normalized.maximum, "maximum")
    else:
        metadata["value"] = normalize_chembl_ic50_number(normalized.value, "value")
    return metadata


def restore_chembl_ic50_metadata_row(row: object) -> ChEMBLIC50QueryBuilderRow:
    """Restore one IC50 builder row from query-builder-v1 metadata."""
    if not isinstance(row, dict):
        msg = "query.builder.rows[0] must be a mapping."
        raise TypeError(msg)
    condition = normalize_chembl_ic50_condition(row.get("condition"))
    expected_fields = (
        {"condition", "minimum", "maximum", "unit"}
        if condition == "range"
        else {
            "condition",
            "value",
            "unit",
        }
    )
    if set(row) != expected_fields:
        msg = "query.builder.rows[0] has an invalid ChEMBL IC50 row shape."
        raise ValueError(msg)
    restored = normalize_chembl_ic50_builder_row(row)
    validate_chembl_ic50_builder_row(restored)
    return restored


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
        if any(" AND " in value for value in values):
            msg = format_chembl_builder_row_error(
                index, "value cannot contain ' AND ', which separates ChEMBL query conditions."
            )
            raise ValueError(msg)
        if filter_type == "range" and len(values) != RANGE_VALUE_COUNT:
            msg = format_chembl_builder_row_error(index, "range requires exactly two comma-separated values.")
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
