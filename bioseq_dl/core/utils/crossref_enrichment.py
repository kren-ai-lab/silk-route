"""Cross-reference enrichment workflow utilities."""

from typing import Any, Literal

import pandas as pd

from bioseq_dl.constants.uniprot import XREF_MAPPING
from bioseq_dl.core.crossref_enricher import CrossRefEnricher, EndpointSpec
from bioseq_dl.core.interfacesconfig import load_packaged_config
from bioseq_dl.logging import get_logger

log = get_logger("bioseq_dl.core.utils.crossref_enrichment")


def normalize_crossref_fields(crossref_fields: object) -> list[str]:
    """Return cleaned cross-reference field names."""
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
            fields.append(cleaned_field)
    return fields


def is_empty_enrichment_input(data: object) -> bool:
    """Return whether enrichment input has no records to process."""
    if data is None:
        return True
    if isinstance(data, pd.DataFrame):
        return data.empty
    if isinstance(data, (list, dict)):
        return len(data) == 0
    if isinstance(data, bytes):
        return data == b""
    if isinstance(data, str):
        return data.strip() == ""
    return False


def has_enrichment_result_value(value: object) -> bool:
    """Return whether an enrichment result value contains exportable data."""
    if value is None:
        return False
    if isinstance(value, pd.DataFrame):
        return not value.empty
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, bytes):
        return value != b""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def run_crossref_enrichment(
    data: Any,
    crossref_fields: list,
    fmt: Literal["dataframe", "json", "xml"] = "json",
    max_workers: int = 4,
    total_retries: int = 3,
) -> tuple[Any, dict | list[dict]]:
    """Run cross-reference enrichment for all configured endpoint specs."""
    crossref_fields = normalize_crossref_fields(crossref_fields)
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
                endpoint_config = endpoints_config.get(db_name)
                if not isinstance(endpoint_config, dict):
                    continue

                for ep_name, ep_info in endpoint_config.get("endpoints", {}).items():
                    if ep_info.get("enabled", False):
                        options = ep_info.get("options", [None]) if "options" in ep_info else [None]
                        endpoint_specs.extend(
                            EndpointSpec(
                                database=db_name,
                                endpoint=ep_name,
                                option=ep_option,
                                params=ep_info.get("params", {}),
                            )
                            for ep_option in options
                        )
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
                                endpoint=method_name,
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
        endpoint_specs=endpoint_specs, max_workers=max_workers, total_retries=total_retries
    )
    enriched_data, enriched_metadata = enricher.enrich(data, fmt=fmt)

    # Normalize metadata to a dict to satisfy the annotated return type
    if enriched_metadata is None:
        enriched_metadata = {}
    elif not isinstance(enriched_metadata, dict):
        enriched_metadata = {"details": enriched_metadata}

    if (isinstance(enriched_data, pd.DataFrame) and not enriched_data.empty) or (
        isinstance(enriched_data, list) and len(enriched_data) > 0
    ):
        return enriched_data, enriched_metadata
    if isinstance(enriched_data, dict):
        enriched_data = {
            label: value for label, value in enriched_data.items() if has_enrichment_result_value(value)
        }
        if enriched_data:
            return enriched_data, enriched_metadata
    log.warning("Crossref enrichment returned no exportable results.")
    return {}, {**enriched_metadata, "skipped": True, "reason": "empty_enrichment_results"}
