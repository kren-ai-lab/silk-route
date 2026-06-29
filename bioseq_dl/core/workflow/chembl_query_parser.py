"""Parse ChEMBL query-builder strings into internal query structures."""

from __future__ import annotations

import re

from bioseq_dl.core.workflow.chembl_query_catalog import (
    FILTER_LIST_MODEL,
    FLAT_PARAMETERS_MODEL,
    OPERATOR_SUFFIXES,
    get_chembl_query_builder_resource_catalog,
)
from bioseq_dl.core.workflow.query_prefixes import is_source_prefixed_query

CHEMBL_QUERY_PATTERN = re.compile(r"^chembl\.(?P<resource>[a-z_]+):(?P<body>.+)$")
CHEMBL_BUILDER_QUERY_PREFIXES = (
    "chembl.target:",
    "chembl.assay:",
    "chembl.cell_line:",
    "chembl.molecule:",
    "chembl.activity:",
)


def is_chembl_prefixed_query(query: str) -> bool:
    """Return whether the query uses a ChEMBL builder prefix."""
    return is_source_prefixed_query(query, "chembl") and str(query or "").strip().lower().startswith(
        CHEMBL_BUILDER_QUERY_PREFIXES
    )


def get_chembl_prefixed_query_resource(query: str) -> str | None:
    """Return the ChEMBL resource name from a prefixed query, if present."""
    match = CHEMBL_QUERY_PATTERN.match(str(query or "").strip())
    if not match:
        return None
    return match.group("resource")


def split_chembl_condition_fragment(fragment: str) -> tuple[str, str, str]:
    """Split one ChEMBL builder condition into field, filter type, and value."""
    if "=" not in fragment:
        msg = f"Invalid ChEMBL query condition '{fragment}'."
        raise ValueError(msg)

    field_with_operator, value = fragment.split("=", 1)
    for operator, suffix in sorted(OPERATOR_SUFFIXES.items(), key=lambda item: len(item[1]), reverse=True):
        if suffix and field_with_operator.endswith(suffix):
            field = field_with_operator[: -len(suffix)]
            return field, operator, value
    return field_with_operator, "exact", value


def parse_chembl_query_builder_string(query: str) -> dict[str, object]:
    """Parse a ChEMBL query-builder string into a resource-specific query structure."""
    match = CHEMBL_QUERY_PATTERN.match(str(query).strip())
    if not match:
        msg = "ChEMBL query builder strings must start with 'chembl.<resource>:'."
        raise ValueError(msg)

    resources = get_chembl_query_builder_resource_catalog()
    resource_key = match.group("resource")
    if resource_key not in resources:
        msg = f"Unsupported ChEMBL query resource '{resource_key}'."
        raise ValueError(msg)

    resource = resources[resource_key]
    fragments = [fragment.strip() for fragment in match.group("body").split(" AND ") if fragment.strip()]
    if not fragments:
        msg = "ChEMBL query builder string must contain at least one condition."
        raise ValueError(msg)

    parsed_fragments = [split_chembl_condition_fragment(fragment) for fragment in fragments]
    if resource.query_model == FILTER_LIST_MODEL:
        return {
            "resource": resource.key,
            "query_model": resource.query_model,
            "filters": [
                {
                    "field": field,
                    "filter_type": filter_type,
                    "value": value,
                }
                for field, filter_type, value in parsed_fragments
            ],
        }
    if resource.query_model == FLAT_PARAMETERS_MODEL:
        parameters = {
            field if filter_type == "exact" else f"{field}__{filter_type}": value
            for field, filter_type, value in parsed_fragments
        }
        return {
            "resource": resource.key,
            "query_model": resource.query_model,
            "parameters": parameters,
        }

    msg = f"ChEMBL query model '{resource.query_model}' is not implemented for parsing."
    raise ValueError(msg)
