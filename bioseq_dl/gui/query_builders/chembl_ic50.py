"""Pure builder utilities for ChEMBL IC50 activity macro queries."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from bioseq_dl.core.utils.chembl_activity import normalize_standard_units

CHEMBL_IC50_BUILDER_KEY = "chembl_ic50_activity"
IC50_COMPARISON_MODES = ("range", "lt", "lte", "gt", "gte", "exact")
IC50_NUMERIC_PATTERN = re.compile(r"\d+(?:\.\d+)?")


@dataclass(frozen=True)
class ChEMBLIC50QueryBuilderRow:
    """One row in the dedicated ChEMBL IC50 activity builder."""

    comparison_mode: str = "range"
    lower_value: str = ""
    upper_value: str = ""
    value: str = ""
    standard_units: str = "nM"


def get_chembl_ic50_query_builder_field_catalog() -> dict[str, object]:
    """Return an empty catalog because this builder uses dedicated controls."""
    return {}


def normalize_ic50_comparison_mode(value: object) -> str:
    """Normalize and validate an IC50 comparison mode."""
    normalized = str(value or "").strip().lower()
    if normalized not in IC50_COMPARISON_MODES:
        allowed = ", ".join(IC50_COMPARISON_MODES)
        msg = f"Unsupported IC50 comparison mode '{value}'. Choose one of: {allowed}."
        raise ValueError(msg)
    return normalized


def normalize_ic50_numeric_value(value: object, field_name: str) -> str:
    """Normalize one required non-negative decimal IC50 value."""
    if isinstance(value, bool) or value is None:
        msg = f"{field_name} must be a numeric value."
        raise ValueError(msg)
    if isinstance(value, float) and not math.isfinite(value):
        msg = f"{field_name} must be a finite numeric value."
        raise ValueError(msg)
    normalized = str(value).strip()
    if not normalized:
        msg = f"{field_name} is required."
        raise ValueError(msg)
    if not IC50_NUMERIC_PATTERN.fullmatch(normalized):
        msg = f"{field_name} must be a non-negative decimal value."
        raise ValueError(msg)
    return normalized


def normalize_ic50_standard_units(value: object) -> str:
    """Normalize optional IC50 units while allowing no unit constraint."""
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    return normalize_standard_units(normalized)


def validate_chembl_ic50_builder_row(row: ChEMBLIC50QueryBuilderRow) -> None:
    """Validate a dedicated ChEMBL IC50 builder row."""
    mode = normalize_ic50_comparison_mode(row.comparison_mode)
    if mode == "range":
        normalize_ic50_numeric_value(row.lower_value, "IC50 lower value")
        normalize_ic50_numeric_value(row.upper_value, "IC50 upper value")
    else:
        normalize_ic50_numeric_value(row.value, "IC50 value")
    normalize_ic50_standard_units(row.standard_units)


def build_chembl_ic50_interpreted_query(row: ChEMBLIC50QueryBuilderRow) -> str:
    """Build the executable IC50 macro query from one validated row."""
    mode = normalize_ic50_comparison_mode(row.comparison_mode)
    if mode == "range":
        lower = normalize_ic50_numeric_value(row.lower_value, "IC50 lower value")
        upper = normalize_ic50_numeric_value(row.upper_value, "IC50 upper value")
        query = f"ic50:{lower}-{upper}"
    else:
        value = normalize_ic50_numeric_value(row.value, "IC50 value")
        operator = {"lt": "<", "lte": "<=", "gt": ">", "gte": ">=", "exact": ""}[mode]
        query = f"ic50:{operator}{value}"

    standard_units = normalize_ic50_standard_units(row.standard_units)
    if standard_units:
        query += f" AND standard_units:{standard_units}"
    return query


def build_chembl_ic50_friendly_query(row: ChEMBLIC50QueryBuilderRow) -> str:
    """Build the friendly preview using the executable IC50 macro syntax."""
    return build_chembl_ic50_interpreted_query(row)
