"""Cross-reference enrichment workflow utilities."""

from pathlib import Path
from typing import Any, Literal, cast

import polars as pl

from silkroute.constants.uniprot import XREF_MAPPING
from silkroute.core.crossref_enricher import CrossRefEnricher, EndpointSpec, specs_for_database
from silkroute.core.interfacesconfig import load_packaged_config
from silkroute.logging import get_logger

log = get_logger("silkroute.core.utils.crossref_enrichment")

STRUCTURE_DOWNLOAD_SOURCES = ("alphafold", "pdb")
NO_INTERACTION_VALUES = {"", "none", "no interaction", "no_interaction", "no-interaction"}


def normalize_crossref_fields(crossref_fields: object) -> list[str]:
    """Return cleaned cross-reference field names.

    Accepts a comma-separated string or a list/tuple/set; non-string entries are
    skipped with a warning, and blank entries are dropped.

    Args:
        crossref_fields (object): Raw cross-reference field specification.

    Returns:
        list[str]: Stripped, non-empty field names.

    """
    if crossref_fields is None:
        return []
    if isinstance(crossref_fields, str):
        raw_fields = crossref_fields.split(",")
    elif isinstance(crossref_fields, (list, tuple, set)):
        raw_fields = crossref_fields
    else:
        return []

    fields = []
    for field in raw_fields:
        if not isinstance(field, str):
            log.warning("Ignoring non-string crossref field: %s", field)
            continue
        cleaned_field = field.strip()
        if cleaned_field:
            fields.append(canonicalize_structure_source_field(cleaned_field))
    return fields


def canonicalize_structure_source_field(field: str) -> str:
    """Return canonical structure-source casing without touching unrelated fields."""
    normalized = field.strip()
    lowered = normalized.lower()
    for source in STRUCTURE_DOWNLOAD_SOURCES:
        if lowered in {source, f"{source}_all"} or lowered.startswith(f"{source}_"):
            return lowered
    return normalized


def is_structure_download_workflow_compatible(
    modality: object,
    interaction_type: object,
) -> bool:
    """Return whether a workflow context may activate structure downloads."""
    normalized_modality = str(modality or "").strip().lower()
    normalized_interaction = str(interaction_type or "").strip().lower()
    return normalized_modality == "protein" and normalized_interaction in NO_INTERACTION_VALUES


def is_empty_enrichment_input(data: object) -> bool:
    """Return whether enrichment input has no records to process.

    Handles DataFrames, lists/dicts, bytes, and strings; other types are treated
    as non-empty.

    Args:
        data (object): Input data to check.

    Returns:
        bool: True if the input has no records to process.

    """
    if data is None:
        return True
    if isinstance(data, pl.DataFrame):
        return data.is_empty()
    if isinstance(data, (list, dict)):
        return len(data) == 0
    if isinstance(data, bytes):
        return data == b""
    if isinstance(data, str):
        return data.strip() == ""
    return False


def has_enrichment_result_value(value: object) -> bool:
    """Return whether an enrichment result value contains exportable data.

    Handles DataFrames, strings, bytes, and collections; other types are treated
    as containing data.

    Args:
        value (object): Enrichment result value to check.

    Returns:
        bool: True if the value contains exportable data.

    """
    if value is None:
        return False
    if isinstance(value, pl.DataFrame):
        return not value.is_empty()
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, bytes):
        return value != b""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def count_enrichment_output_rows(value: object) -> int:
    """Return a deterministic row/record count for one enrichment artifact."""
    if value is None:
        return 0
    if isinstance(value, pl.DataFrame):
        return value.height
    if isinstance(value, (list, tuple, set)):
        return len(value)
    if isinstance(value, dict):
        return 1 if value else 0
    if isinstance(value, (str, bytes)):
        return 1 if value else 0
    return 1


def add_enrichment_output_row_counts(enriched_data: dict, enriched_metadata: dict) -> None:
    """Record artifact-level output row counts in each endpoint metadata block."""
    for label, value in enriched_data.items():
        metadata = enriched_metadata.setdefault(label, {})
        if not isinstance(metadata, dict):
            metadata = {"details": metadata}
            enriched_metadata[label] = metadata
        metadata.setdefault("extra", {})["output_row_count"] = count_enrichment_output_rows(value)


def filter_non_empty_enrichment_data(enriched_data: dict) -> dict:
    """Return only enrichment artifacts that contain public exportable data."""
    return {label: value for label, value in enriched_data.items() if has_enrichment_result_value(value)}


def _crossref_source_selected(crossref_fields: list[str], source: str) -> bool:
    """Return whether a normalized crossref field selects a source."""
    return any(
        field in {source, f"{source}_all"} or field.startswith(f"{source}_") for field in crossref_fields
    )


def _structure_output_directory(output_dir: str | Path | None, source: str) -> str | None:
    """Return the workflow-controlled structure directory for an active source."""
    if output_dir is None:
        return None
    return str(Path(output_dir) / "structures" / source)


def build_structure_download_metadata(
    crossref_fields: list[str],
    *,
    enrich: bool,
    structure_downloads_allowed: bool,
    download_alphafold_structures: bool,
    download_pdb_structures: bool,
    output_dir: str | Path | None,
) -> dict[str, dict[str, Any]]:
    """Build concise workflow metadata for optional structure downloads."""
    requested_by_source = {
        "alphafold": bool(download_alphafold_structures),
        "pdb": bool(download_pdb_structures),
    }
    metadata: dict[str, dict[str, Any]] = {}
    for source in STRUCTURE_DOWNLOAD_SOURCES:
        requested = requested_by_source[source]
        source_selected = _crossref_source_selected(crossref_fields, source)
        output_directory = _structure_output_directory(output_dir, source)
        active = bool(
            structure_downloads_allowed and enrich and requested and source_selected and output_directory
        )
        source_meta: dict[str, Any] = {
            "requested": requested,
            "active": active,
            "source_selected": source_selected,
        }
        if active:
            source_meta["output_directory"] = output_directory
        elif requested:
            if not structure_downloads_allowed:
                source_meta["inactive_reason"] = "incompatible_workflow"
            elif not enrich:
                source_meta["inactive_reason"] = "enrichment_disabled"
            elif not source_selected:
                source_meta["inactive_reason"] = "source_not_selected"
            elif not output_directory:
                source_meta["inactive_reason"] = "missing_output_dir"
        metadata[source] = source_meta
    return metadata


def build_structure_download_interface_options(
    crossref_fields: list[str],
    *,
    enrich: bool,
    structure_downloads_allowed: bool,
    download_alphafold_structures: bool,
    download_pdb_structures: bool,
    output_dir: str | Path | None,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Return interface kwargs and metadata for explicit structure downloads."""
    structure_metadata = build_structure_download_metadata(
        crossref_fields,
        enrich=enrich,
        structure_downloads_allowed=structure_downloads_allowed,
        download_alphafold_structures=download_alphafold_structures,
        download_pdb_structures=download_pdb_structures,
        output_dir=output_dir,
    )
    interface_options: dict[str, dict[str, Any]] = {"pdb": {"download_structures": False}}

    alphafold_meta = structure_metadata["alphafold"]
    if alphafold_meta["active"]:
        interface_options["alphafold"] = {
            "structures": ["pdb"],
            "output_dir": alphafold_meta["output_directory"],
            "path_base": output_dir,
        }

    pdb_meta = structure_metadata["pdb"]
    if pdb_meta["active"]:
        interface_options["pdb"] = {
            "download_structures": True,
            "output_dir": pdb_meta["output_directory"],
            "path_base": output_dir,
        }

    return interface_options, structure_metadata


def run_crossref_enrichment(
    data: Any,
    crossref_fields: list,
    format: Literal["dataframe", "json", "xml"] = "json",  # noqa: A002
    max_workers: int = 4,
    total_retries: int = 3,
    enrich: bool = True,
    structure_downloads_allowed: bool = True,
    download_alphafold_structures: bool = False,
    download_pdb_structures: bool = False,
    output_dir: str | Path | None = None,
) -> tuple[Any, dict | list[dict]]:
    """Run cross-reference enrichment for the requested fields.

    Parses each field into a database/method/option spec (supporting ``db``,
    ``db_method``, ``db_method_option``, and ``db_all`` forms), resolves matching
    endpoint specs from the packaged config, runs the enricher, and filters the
    output to exportable values. Returns early with skip metadata when there are
    no fields, no input, or no resolved specs.

    Args:
        data (Any): Input records to enrich.
        crossref_fields (list): Requested cross-reference fields.
        format (Literal["dataframe", "json", "xml"]): Output format for results. Default is "json".
        max_workers (int): Maximum number of worker threads. Default is 4.
        total_retries (int): Number of retries per request. Default is 3.
        enrich (bool): Whether enrichment is active. False disables downloads defensively.
        structure_downloads_allowed (bool): Whether the workflow context can download structures.
        download_alphafold_structures (bool): Whether AlphaFold structure downloads were requested.
        download_pdb_structures (bool): Whether PDB structure downloads were requested.
        output_dir (str | Path | None): Workflow export directory used to root structure downloads.

    Returns:
        tuple[Any, dict | list[dict]]: Enriched data (empty dict if skipped) and
            accompanying metadata.

    """
    crossref_fields = normalize_crossref_fields(crossref_fields)
    interface_options, structure_metadata = build_structure_download_interface_options(
        crossref_fields,
        enrich=enrich,
        structure_downloads_allowed=structure_downloads_allowed,
        download_alphafold_structures=download_alphafold_structures,
        download_pdb_structures=download_pdb_structures,
        output_dir=output_dir,
    )
    if not enrich:
        log.info("Skipping CrossRef enrichment because enrich=False.")
        return {}, {"skipped": True, "reason": "enrichment_disabled"}
    if not crossref_fields:
        log.info("Skipping CrossRef enrichment because no cross-reference fields were requested.")
        return {}, {"skipped": True, "reason": "no_crossref_fields"}

    if is_empty_enrichment_input(data):
        log.warning("Input data is empty. Skipping crossref enrichment.")
        return {}, {"skipped": True, "reason": "empty_input"}

    # Process crossref fields
    # Some definitions in crossref_fields may contain the database name and the method separated by underscore
    # For example, "brenda_getOptimumTemperature" should be processed as "brenda" and use the method
    # "getOptimumTemperature"
    # Another example is giving only the database name "kegg" which means we should use all available methods
    # for that database
    # For this reason we will make a new dictionary containing the databases and their methods
    # As last thing, some fields definitions will have another underscore after the method name, this will
    # indicate the option to use
    # Example: "brenda_getOptimumTemperature_option1" should be processed as:
    # {"brenda": [{"method": "getOptimumTemperature", "option": "option1"}]}  # noqa: ERA001
    # Special case: "kegg_all" should be processed as:
    # {"kegg": [{"method": None, "option": None}]}  # noqa: ERA001

    processed_crossref_fields = {}
    for field in crossref_fields:
        # Special-cased form: "db_all" -> use all methods for that database
        if field.endswith("_all") and "_" in field:
            db_name = field.rsplit("_", 1)[0]
            processed_crossref_fields.setdefault(db_name, []).append({"method": None, "option": None})
            continue

        # Forms with a method: "db_method" or "db_method_option"
        if "_" in field:
            db_name, method_part = field.split("_", 1)
            if "_" in method_part:
                method_name, option = method_part.rsplit("_", 1)
                processed_crossref_fields.setdefault(db_name, []).append(
                    {"method": method_name, "option": option}
                )
            else:
                processed_crossref_fields.setdefault(db_name, []).append(
                    {"method": method_part, "option": None}
                )
        else:
            # Plain database name -> use all methods
            processed_crossref_fields.setdefault(field, []).append({"method": None, "option": None})

    log.info("Running crossref enrichment for fields: %s", crossref_fields)
    endpoints_config = load_packaged_config("uniprot_crossref", "config_endpoints.yml") or {}

    endpoint_specs = []
    # Generate the endpoint specs based on selected crossref fields
    for key, (uniprot_field, db_name) in XREF_MAPPING.items():
        if db_name and db_name in processed_crossref_fields:
            log.debug(
                "Processing crossref field: %s -> db: %s, uniprot_field: %s", key, db_name, uniprot_field
            )
            if processed_crossref_fields[db_name] == [{"method": None, "option": None}]:
                # Use all available methods for this database
                log.debug("Using all available methods for database: %s", db_name)
                endpoint_specs.extend(specs_for_database(endpoints_config.get(db_name), db_name))
            else:
                log.debug("Using specified methods for database: %s", db_name)
                for method in processed_crossref_fields[db_name]:
                    method_name = method["method"]
                    option = method["option"]
                    endpoint_config = endpoints_config.get(db_name)
                    if not isinstance(endpoint_config, dict):
                        continue

                    ep_info = endpoint_config.get("endpoints", {}).get(method_name, None)
                    if ep_info and ep_info.get("enabled", False):
                        endpoint_specs.append(
                            EndpointSpec(
                                database=db_name,
                                endpoint=cast("str", method_name),
                                option=option,
                                params=ep_info.get("params", {}),
                            )
                        )
                    else:
                        log.warning(
                            "Method %s for database %s is not enabled or does not exist in config.",
                            method_name,
                            db_name,
                        )

    log.debug("Final endpoint specs: %s", endpoint_specs)
    if not endpoint_specs:
        log.info("Skipping CrossRef enrichment because no endpoint specs were resolved.")
        return {}, {"skipped": True, "reason": "no_endpoint_specs"}

    enricher = CrossRefEnricher(
        endpoint_specs=endpoint_specs,
        max_workers=max_workers,
        total_retries=total_retries,
        interface_options=interface_options,
    )
    enriched_data, enriched_metadata = enricher.enrich(data, format=format)

    # Normalize metadata to a dict to satisfy the annotated return type
    if enriched_metadata is None:
        enriched_metadata = {}
    elif not isinstance(enriched_metadata, dict):
        enriched_metadata = {"details": enriched_metadata}
    enriched_metadata = cast("dict[str, object]", enriched_metadata)
    enriched_metadata["structure_downloads"] = structure_metadata

    if isinstance(enriched_data, dict):
        add_enrichment_output_row_counts(enriched_data, enriched_metadata)
        enriched_data = filter_non_empty_enrichment_data(enriched_data)
        if enriched_data:
            return enriched_data, enriched_metadata
    log.warning("Crossref enrichment returned no exportable results.")
    return {}, {**enriched_metadata, "skipped": True, "reason": "empty_enrichment_results"}
