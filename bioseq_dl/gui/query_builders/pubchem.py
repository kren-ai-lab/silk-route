"""Pure PubChem query builder utilities."""

from __future__ import annotations

from dataclasses import dataclass

from bioseq_dl.core.workflow.pubchem_query_catalog import get_pubchem_query_builder_field_catalog
from bioseq_dl.core.workflow.query_interpreter import strip_surrounding_quotes

MIN_THRESHOLD = 0
MAX_THRESHOLD = 100


@dataclass(frozen=True)
class PubChemQueryBuilderRow:
    """One row in a PubChem resource-specific query builder."""

    resource: str
    field: str
    value: str
    threshold: int | str | None = None


def normalize_pubchem_resource(resource: str) -> str:
    """Normalize a PubChem resource key."""
    return str(resource).strip().lower()


def normalize_pubchem_field(field: str) -> str:
    """Normalize a PubChem field key."""
    return str(field).strip().lower()


def quote_pubchem_value(value: str) -> str:
    """Quote a PubChem query value."""
    cleaned = strip_surrounding_quotes(str(value))
    escaped = cleaned.replace('"', '\\"')
    return f'"{escaped}"'


def parse_pubchem_builder_threshold(value: int | str | None) -> int:
    """Parse and validate a PubChem builder threshold."""
    if value is None or str(value).strip() == "":
        msg = "PubChem 2-D similarity requires a threshold."
        raise ValueError(msg)
    normalized = str(value).strip()
    if not normalized.isdigit():
        msg = "PubChem 2-D similarity threshold must be an integer from 0 to 100."
        raise ValueError(msg)
    threshold = int(normalized)
    if threshold < MIN_THRESHOLD or threshold > MAX_THRESHOLD:
        msg = "PubChem 2-D similarity threshold must be an integer from 0 to 100."
        raise ValueError(msg)
    return threshold


def validate_pubchem_builder_row(row: PubChemQueryBuilderRow) -> None:
    """Validate one PubChem query builder row."""
    resource = normalize_pubchem_resource(row.resource)
    catalog = get_pubchem_query_builder_field_catalog(resource)
    field = normalize_pubchem_field(row.field)
    if field not in catalog:
        msg = f"PubChem field '{row.field}' is not supported for resource '{row.resource}'."
        raise ValueError(msg)
    if not strip_surrounding_quotes(str(row.value)).strip():
        msg = "PubChem query builder value is required."
        raise ValueError(msg)
    if resource == "compound" and field == "cid" and not str(row.value).strip().isdigit():
        msg = "PubChem CID values must be positive integers."
        raise ValueError(msg)
    if resource == "structure" and field == "similarity_2d":
        parse_pubchem_builder_threshold(row.threshold)


def build_pubchem_parameter_fragment(row: PubChemQueryBuilderRow) -> str:
    """Build one PubChem interpreted-query parameter fragment."""
    field = normalize_pubchem_field(row.field)
    value = strip_surrounding_quotes(str(row.value)).strip()
    if field == "cid":
        return f"cid={value}"
    if field == "similarity_2d":
        threshold = parse_pubchem_builder_threshold(row.threshold)
        return f"similarity_2d_cid={value} AND threshold={threshold}"
    return f"{field}={quote_pubchem_value(value)}"


def build_pubchem_friendly_query(row: PubChemQueryBuilderRow) -> str:
    """Build a human-readable PubChem query preview."""
    return build_pubchem_interpreted_query(row)


def build_pubchem_interpreted_query(row: PubChemQueryBuilderRow) -> str:
    """Build the final PubChem query.value string from a query builder row."""
    validate_pubchem_builder_row(row)
    resource = normalize_pubchem_resource(row.resource)
    return f"pubchem.{resource}:{build_pubchem_parameter_fragment(row)}"
