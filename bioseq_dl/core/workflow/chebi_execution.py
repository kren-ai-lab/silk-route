"""ChEBI request-plan execution helpers and result normalization."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bioseq_dl.core.interfaces.chebi import ChEBIInterface
from bioseq_dl.core.utils.frames import records_to_frame

if TYPE_CHECKING:
    import polars as pl

SUPPORTED_CHEBI_QUERY_MODELS = ("entity_query",)
EXECUTABLE_CHEBI_ENTITY_FIELDS = ("chebi_id", "name", "name_contains")
CHEBI_SEARCH_SIZE = 100


def build_chebi_fetch_spec(request_plan: dict[str, Any]) -> dict[str, Any]:
    """Translate an executable ChEBI request plan into interface call arguments."""
    resource = str(request_plan.get("resource") or "")
    query_model = str(request_plan.get("query_model") or "")
    parameters = request_plan.get("parameters")

    if resource != "entity":
        msg = "Only chebi.entity queries are executable in this workflow phase."
        raise ValueError(msg)
    if query_model not in SUPPORTED_CHEBI_QUERY_MODELS:
        supported = ", ".join(SUPPORTED_CHEBI_QUERY_MODELS)
        msg = f"Unsupported ChEBI query model '{query_model}'. Supported models are: {supported}."
        raise ValueError(msg)
    if not isinstance(parameters, dict):
        msg = "ChEBI request plans require a parameters mapping."
        raise TypeError(msg)

    fields = [field for field in parameters if field in EXECUTABLE_CHEBI_ENTITY_FIELDS]
    unsupported_fields = [field for field in parameters if field not in EXECUTABLE_CHEBI_ENTITY_FIELDS]
    if unsupported_fields or len(fields) != 1 or len(parameters) != 1:
        unsupported = ", ".join(unsupported_fields or parameters)
        supported = ", ".join(EXECUTABLE_CHEBI_ENTITY_FIELDS)
        msg = (
            f"ChEBI entity parameters '{unsupported}' are not executable yet. "
            f"Executable fields are: {supported}."
        )
        raise ValueError(msg)

    field = fields[0]
    value = str(parameters[field])
    if field == "chebi_id":
        return {"method": "compound", "query": value}
    return {
        "method": "es_search",
        "query": {"term": value, "page": 1, "size": CHEBI_SEARCH_SIZE},
    }


def extract_chebi_records(payload: object) -> list[dict[str, Any]]:
    """Return ChEBI records from compound and search response shapes."""
    if isinstance(payload, list):
        return [record for record in payload if isinstance(record, dict)]
    if not isinstance(payload, dict):
        return []
    if not payload:
        return []
    results = payload.get("results")
    if isinstance(results, list):
        return [record for record in results if isinstance(record, dict)]
    return [payload]


def unwrap_chebi_search_record(record: dict[str, Any]) -> dict[str, Any]:
    """Return the ChEBI entity payload from an Elasticsearch-style hit."""
    source = record.get("_source")
    return source if isinstance(source, dict) else record


def normalize_chebi_id(record: dict[str, Any]) -> str | None:
    """Return a source-qualified ChEBI identifier when available."""
    chebi_id = record.get("chebi_accession") or record.get("chebi_id")
    if chebi_id:
        text = str(chebi_id)
        return text if text.upper().startswith("CHEBI:") else f"CHEBI:{text}"
    numeric_id = record.get("id")
    return f"CHEBI:{numeric_id}" if numeric_id is not None else None


def normalize_chebi_record(record: dict[str, Any], request_plan: dict[str, Any]) -> dict[str, Any]:
    """Normalize one ChEBI entity record for compound workflow output."""
    entity = unwrap_chebi_search_record(record)
    chemical_data = entity.get("chemical_data")
    if not isinstance(chemical_data, dict):
        chemical_data = {}
    structure = entity.get("default_structure")
    if not isinstance(structure, dict):
        structure = {}
    chebi_id = normalize_chebi_id(entity)
    return {
        "source": "chebi",
        "compound_id": chebi_id,
        "chebi_id": chebi_id,
        "name": entity.get("name") or entity.get("ascii_name"),
        "definition": entity.get("definition"),
        "formula": chemical_data.get("formula") or entity.get("formula"),
        "charge": chemical_data.get("charge") if "charge" in chemical_data else entity.get("charge"),
        "mass": chemical_data.get("mass") or entity.get("mass"),
        "monoisotopic_mass": chemical_data.get("monoisotopic_mass")
        or entity.get("monoisotopic_mass")
        or entity.get("monoisotopicmass"),
        "inchi": structure.get("standard_inchi") or entity.get("inchi"),
        "inchikey": structure.get("standard_inchi_key") or entity.get("inchikey"),
        "smiles": structure.get("smiles") or entity.get("smiles"),
        "database_accessions": entity.get("database_accessions"),
        "query_resource": request_plan.get("resource"),
        "query_model": request_plan.get("query_model"),
    }


def normalized_chebi_name(record: dict[str, Any]) -> str:
    """Return the best available ChEBI entity name for exact matching."""
    entity = unwrap_chebi_search_record(record)
    return str(entity.get("name") or entity.get("ascii_name") or "")


def filter_chebi_name_records(
    records: list[dict[str, Any]],
    request_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    """Apply exact-name filtering for ``chebi.entity:name=...`` request plans."""
    parameters = request_plan.get("parameters")
    if not isinstance(parameters, dict) or "name" not in parameters:
        return records
    expected = str(parameters["name"]).casefold()
    return [record for record in records if normalized_chebi_name(record).casefold() == expected]


def normalize_chebi_records(payload: object, request_plan: dict[str, Any]) -> pl.DataFrame:
    """Normalize ChEBI workflow results into a Polars DataFrame."""
    records = filter_chebi_name_records(extract_chebi_records(payload), request_plan)
    normalized = [normalize_chebi_record(record, request_plan) for record in records]
    return records_to_frame(normalized)


def execute_chebi_request_plan(
    request_plan: dict[str, Any],
    *,
    interface: ChEBIInterface | None = None,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    """Execute one ChEBI request plan and return normalized data plus metadata."""
    instance = interface or ChEBIInterface()
    fetch_spec = build_chebi_fetch_spec(request_plan)
    payload, fetch_meta = instance.fetch_single(
        query=fetch_spec["query"],
        method=fetch_spec["method"],
        parse=False,
        format="json",
    )
    frame = normalize_chebi_records(payload, request_plan)
    metadata = {
        "query_source": "chebi",
        "query_resource": request_plan.get("resource"),
        "query_model": request_plan.get("query_model"),
        "request_plan": request_plan,
        "number_of_records": frame.height,
        "fetch": fetch_meta if isinstance(fetch_meta, dict) else {},
    }
    return frame, metadata
