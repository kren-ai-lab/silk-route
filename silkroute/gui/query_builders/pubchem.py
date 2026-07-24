"""Pure PubChem query builder utilities."""

from __future__ import annotations

from dataclasses import dataclass

from silkroute.core.workflow.pubchem_query_catalog import get_pubchem_query_builder_field_catalog
from silkroute.core.workflow.query_interpreter import strip_surrounding_quotes
from silkroute.gui.query_builders.common import quote_builder_value

MIN_THRESHOLD = 0
MAX_THRESHOLD = 100
DEFAULT_SIMILARITY_THRESHOLD = 80
SIMILARITY_2D_CID_FIELD = "similarity_2d_cid"


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


def parse_pubchem_builder_threshold(value: int | str | None) -> int:
    """Parse and validate a PubChem builder threshold."""
    if value is None or str(value).strip() == "":
        msg = "PubChem 2-D similarity requires a threshold."
        raise ValueError(msg)
    normalized = str(value).strip()
    if not normalized.isdigit():
        msg = "PubChem similarity threshold must be an integer between 0 and 100."
        raise ValueError(msg)
    threshold = int(normalized)
    if threshold < MIN_THRESHOLD or threshold > MAX_THRESHOLD:
        msg = "PubChem similarity threshold must be an integer between 0 and 100."
        raise ValueError(msg)
    return threshold


def normalize_pubchem_builder_threshold_state(field: str, value: int | str | None) -> int | None:
    """Return GUI-safe threshold state for one PubChem builder field."""
    if normalize_pubchem_field(field) != SIMILARITY_2D_CID_FIELD:
        return None
    if value is None or str(value).strip() == "":
        return DEFAULT_SIMILARITY_THRESHOLD
    return parse_pubchem_builder_threshold(value)


def validate_pubchem_builder_row(row: PubChemQueryBuilderRow) -> None:
    """Validate one PubChem query builder row."""
    resource = normalize_pubchem_resource(row.resource)
    catalog = get_pubchem_query_builder_field_catalog(resource)
    field = normalize_pubchem_field(row.field)
    if field not in catalog:
        supported = ", ".join(catalog)
        msg = f"Unsupported PubChem {resource} field '{row.field}'. Supported fields are: {supported}."
        raise ValueError(msg)

    value = strip_surrounding_quotes(str(row.value)).strip()
    if not value:
        msg = "PubChem query builder value is required."
        raise ValueError(msg)
    if resource == "compound" and field == "cid" and (not value.isdigit() or int(value) <= 0):
        msg = "PubChem CID values must be positive integers."
        raise ValueError(msg)
    if resource == "structure" and field == SIMILARITY_2D_CID_FIELD:
        if not value.isdigit() or int(value) <= 0:
            msg = "PubChem 2-D similarity searches require a positive reference CID."
            raise ValueError(msg)
        parse_pubchem_builder_threshold(row.threshold)


def build_pubchem_parameter_fragment(row: PubChemQueryBuilderRow) -> str:
    """Build one PubChem interpreted-query parameter fragment."""
    field = normalize_pubchem_field(row.field)
    value = strip_surrounding_quotes(str(row.value)).strip()
    if field in {"cid", SIMILARITY_2D_CID_FIELD}:
        if field == SIMILARITY_2D_CID_FIELD:
            threshold = parse_pubchem_builder_threshold(row.threshold)
            return f"{field}={value} AND threshold={threshold}"
        return f"{field}={value}"
    return f"{field}={quote_builder_value(value)}"


def build_pubchem_friendly_query(row: PubChemQueryBuilderRow) -> str:
    """Build a human-readable PubChem query preview."""
    return build_pubchem_interpreted_query(row)


def build_pubchem_interpreted_query(row: PubChemQueryBuilderRow) -> str:
    """Build the final PubChem query.value string from a query builder row."""
    validate_pubchem_builder_row(row)
    resource = normalize_pubchem_resource(row.resource)
    return f"pubchem.{resource}:{build_pubchem_parameter_fragment(row)}"
