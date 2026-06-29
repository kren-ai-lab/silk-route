"""Parse PubChem query-builder strings into request-plan dictionaries."""

from __future__ import annotations

import re

from bioseq_dl.core.workflow.pubchem_query_catalog import (
    COMPOUND_LOOKUP_MODEL,
    STRUCTURE_SEARCH_MODEL,
    get_pubchem_query_builder_resource_catalog,
)

PUBCHEM_QUERY_PATTERN = re.compile(r"^pubchem\.(?P<resource>[a-z_]+):(?P<body>.+)$")
PUBCHEM_BUILDER_QUERY_PREFIXES = ("pubchem.compound:", "pubchem.structure:")
MIN_QUOTED_VALUE_LENGTH = 2
MIN_THRESHOLD = 0
MAX_THRESHOLD = 100

COMPOUND_FIELDS = frozenset({"cid", "name", "inchikey", "inchi"})
STRUCTURE_FIELDS = frozenset({"smiles_identity", "smiles_substructure", "similarity_2d_cid"})


def is_pubchem_prefixed_query(query: str) -> bool:
    """Return whether the query uses a PubChem builder prefix."""
    normalized = str(query or "").strip().lower()
    return normalized.startswith(PUBCHEM_BUILDER_QUERY_PREFIXES)


def get_pubchem_prefixed_query_resource(query: str) -> str | None:
    """Return the PubChem resource name from a prefixed query, if present."""
    match = PUBCHEM_QUERY_PATTERN.match(str(query or "").strip())
    if not match:
        return None
    return match.group("resource")


def strip_pubchem_value_quotes(value: str) -> str:
    """Strip one matching pair of surrounding quotes from a PubChem value."""
    stripped = value.strip()
    if len(stripped) >= MIN_QUOTED_VALUE_LENGTH and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        return stripped[1:-1]
    return stripped


def split_pubchem_conditions(body: str) -> list[str]:
    """Split a PubChem query-builder body into AND-separated conditions."""
    return [fragment.strip() for fragment in body.split(" AND ") if fragment.strip()]


def split_pubchem_condition(fragment: str) -> tuple[str, str]:
    """Split one PubChem query condition into field and value."""
    if "=" not in fragment:
        msg = f"Invalid PubChem query condition '{fragment}'."
        raise ValueError(msg)
    field, value = fragment.split("=", 1)
    field = field.strip()
    value = strip_pubchem_value_quotes(value)
    if not field or not value:
        msg = f"Invalid PubChem query condition '{fragment}'."
        raise ValueError(msg)
    return field, value


def parse_pubchem_threshold(value: str) -> int:
    """Parse and validate a PubChem 2-D similarity threshold."""
    if not re.fullmatch(r"\d+", value.strip()):
        msg = "PubChem similarity_2d threshold must be an integer from 0 to 100."
        raise ValueError(msg)
    threshold = int(value)
    if threshold < MIN_THRESHOLD or threshold > MAX_THRESHOLD:
        msg = "PubChem similarity_2d threshold must be an integer from 0 to 100."
        raise ValueError(msg)
    return threshold


def parse_pubchem_compound_parameters(fragments: list[str]) -> dict[str, str]:
    """Parse PubChem compound lookup parameters."""
    if len(fragments) != 1:
        msg = "PubChem compound queries require exactly one lookup condition."
        raise ValueError(msg)
    field, value = split_pubchem_condition(fragments[0])
    if field not in COMPOUND_FIELDS:
        msg = f"Unsupported PubChem compound field '{field}'."
        raise ValueError(msg)
    if field == "cid" and not re.fullmatch(r"\d+", value):
        msg = "PubChem CID values must be positive integers."
        raise ValueError(msg)
    return {field: value}


def parse_pubchem_structure_parameters(fragments: list[str]) -> dict[str, object]:
    """Parse PubChem structure search parameters."""
    raw_parameters: dict[str, str] = {}
    for fragment in fragments:
        field, value = split_pubchem_condition(fragment)
        if field not in STRUCTURE_FIELDS and field != "threshold":
            msg = f"Unsupported PubChem structure field '{field}'."
            raise ValueError(msg)
        raw_parameters[field] = value

    if "similarity_2d_cid" in raw_parameters:
        allowed = {"similarity_2d_cid", "threshold"}
        if set(raw_parameters) - allowed:
            msg = "PubChem similarity_2d queries only support similarity_2d_cid and threshold."
            raise ValueError(msg)
        if "threshold" not in raw_parameters:
            msg = "PubChem similarity_2d queries require threshold."
            raise ValueError(msg)
        if not re.fullmatch(r"\d+", raw_parameters["similarity_2d_cid"]):
            msg = "PubChem similarity_2d_cid values must be positive integers."
            raise ValueError(msg)
        return {
            "similarity_2d_cid": raw_parameters["similarity_2d_cid"],
            "threshold": parse_pubchem_threshold(raw_parameters["threshold"]),
        }

    if "threshold" in raw_parameters:
        msg = "PubChem threshold is only supported with similarity_2d_cid."
        raise ValueError(msg)
    if len(raw_parameters) != 1:
        msg = "PubChem structure queries require exactly one structure condition."
        raise ValueError(msg)
    return dict(raw_parameters)


def parse_pubchem_query_builder_string(query: str) -> dict[str, object]:
    """Parse a PubChem query-builder string into a pure request plan."""
    match = PUBCHEM_QUERY_PATTERN.match(str(query).strip())
    if not match:
        msg = "PubChem query builder strings must start with 'pubchem.<resource>:'."
        raise ValueError(msg)

    resources = get_pubchem_query_builder_resource_catalog()
    resource_key = match.group("resource")
    if resource_key not in resources:
        msg = f"Unsupported PubChem query resource '{resource_key}'."
        raise ValueError(msg)

    fragments = split_pubchem_conditions(match.group("body"))
    if not fragments:
        msg = "PubChem query builder string must contain at least one condition."
        raise ValueError(msg)

    if resource_key == "compound":
        parameters = parse_pubchem_compound_parameters(fragments)
        query_model = COMPOUND_LOOKUP_MODEL
    elif resource_key == "structure":
        parameters = parse_pubchem_structure_parameters(fragments)
        query_model = STRUCTURE_SEARCH_MODEL
    else:
        msg = f"Unsupported PubChem query resource '{resource_key}'."
        raise ValueError(msg)

    return {
        "source": "pubchem",
        "resource": resource_key,
        "query_model": query_model,
        "parameters": parameters,
    }
