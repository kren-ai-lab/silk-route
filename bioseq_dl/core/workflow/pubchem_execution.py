"""PubChem request-plan execution helpers and result normalization."""

from __future__ import annotations

from typing import Any

import pandas as pd

PUBCHEM_WORKFLOW_METHOD = "workflow/compound-properties"
PUBCHEM_MAX_RECORDS = 100
SUPPORTED_PUBCHEM_QUERY_MODELS = ("compound_lookup", "structure_search")
PUBCHEM_LOOKUP_NAMESPACE_BY_FIELD = {
    "cid": "cid",
    "name": "name",
    "inchi": "inchi",
    "inchikey": "inchikey",
}
PUBCHEM_STRUCTURE_SEARCH_BY_FIELD = {
    "smiles_identity": "identity",
    "smiles_substructure": "substructure",
    "similarity_2d_cid": "similarity_2d",
}


def build_pubchem_fetch_query(request_plan: dict[str, Any]) -> dict[str, Any]:
    """Translate a PubChem request plan into interface parameters."""
    query_model = str(request_plan.get("query_model") or "")
    parameters = request_plan.get("parameters")
    if query_model not in SUPPORTED_PUBCHEM_QUERY_MODELS:
        supported = ", ".join(SUPPORTED_PUBCHEM_QUERY_MODELS)
        msg = f"Unsupported PubChem query model '{query_model}'. Supported models are: {supported}."
        raise ValueError(msg)
    if not isinstance(parameters, dict):
        msg = "PubChem request plans require a parameters mapping."
        raise TypeError(msg)

    if query_model == "compound_lookup":
        lookup_fields = [field for field in PUBCHEM_LOOKUP_NAMESPACE_BY_FIELD if field in parameters]
        if len(lookup_fields) != 1:
            supported = ", ".join(PUBCHEM_LOOKUP_NAMESPACE_BY_FIELD)
            msg = f"PubChem compound lookup requires one supported field: {supported}."
            raise ValueError(msg)
        field = lookup_fields[0]
        return {
            "namespace": PUBCHEM_LOOKUP_NAMESPACE_BY_FIELD[field],
            "identifier": str(parameters[field]),
            "search_mode": "lookup",
            "max_records": PUBCHEM_MAX_RECORDS,
        }

    structure_fields = [field for field in PUBCHEM_STRUCTURE_SEARCH_BY_FIELD if field in parameters]
    if len(structure_fields) != 1:
        supported = ", ".join(PUBCHEM_STRUCTURE_SEARCH_BY_FIELD)
        msg = f"PubChem structure search requires one supported field: {supported}."
        raise ValueError(msg)
    field = structure_fields[0]
    query = {
        "namespace": "cid" if field == "similarity_2d_cid" else "smiles",
        "identifier": str(parameters[field]),
        "search_mode": PUBCHEM_STRUCTURE_SEARCH_BY_FIELD[field],
        "max_records": PUBCHEM_MAX_RECORDS,
    }
    if field == "similarity_2d_cid":
        query["threshold"] = int(parameters["threshold"])
    return query


def extract_pubchem_records(payload: object) -> list[dict[str, Any]]:
    """Return PubChem property records from common response envelopes."""
    if isinstance(payload, list):
        return [record for record in payload if isinstance(record, dict)]
    if not isinstance(payload, dict):
        return []
    property_table = payload.get("PropertyTable")
    if isinstance(property_table, dict):
        properties = property_table.get("Properties")
        if isinstance(properties, list):
            return [record for record in properties if isinstance(record, dict)]
    identifier_list = payload.get("IdentifierList")
    if isinstance(identifier_list, dict) and isinstance(identifier_list.get("CID"), list):
        return [{"CID": cid} for cid in identifier_list["CID"]]
    return [payload]


def first_pubchem_value(record: dict[str, Any], *keys: str) -> object:
    """Return the first present PubChem field value."""
    for key in keys:
        value = record.get(key)
        if value is not None:
            return value
    return None


def normalize_pubchem_record(record: dict[str, Any], request_plan: dict[str, Any]) -> dict[str, Any]:
    """Normalize one PubChem property record for compound workflow output."""
    cid = first_pubchem_value(record, "CID", "cid")
    cid_text = str(cid) if cid is not None else None
    return {
        "source": "pubchem",
        "compound_id": f"PUBCHEM:{cid_text}" if cid_text else None,
        "pubchem_cid": cid,
        "name": first_pubchem_value(record, "Title", "title", "IUPACName", "iupac_name"),
        "synonyms": first_pubchem_value(record, "Synonym", "synonyms"),
        "molecular_formula": first_pubchem_value(record, "MolecularFormula", "molecular_formula"),
        "molecular_weight": first_pubchem_value(record, "MolecularWeight", "molecular_weight"),
        "canonical_smiles": first_pubchem_value(
            record,
            "ConnectivitySMILES",
            "CanonicalSMILES",
            "canonical_smiles",
        ),
        "isomeric_smiles": first_pubchem_value(record, "SMILES", "IsomericSMILES", "isomeric_smiles"),
        "inchi": first_pubchem_value(record, "InChI", "inchi"),
        "inchikey": first_pubchem_value(record, "InChIKey", "inchikey"),
        "iupac_name": first_pubchem_value(record, "IUPACName", "iupac_name"),
        "query_resource": request_plan.get("resource"),
        "query_model": request_plan.get("query_model"),
    }


def normalize_pubchem_records(payload: object, request_plan: dict[str, Any]) -> pd.DataFrame:
    """Normalize PubChem workflow results into a stable DataFrame."""
    records = extract_pubchem_records(payload)
    return pd.DataFrame(normalize_pubchem_record(record, request_plan) for record in records)
