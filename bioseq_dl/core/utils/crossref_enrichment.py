import pandas as pd
from typing import Tuple, Dict, Any, Literal, List, Union

from bioseq_dl.core.crossref_enricher import CrossRefEnricher, EndpointSpec
from bioseq_dl.core.interfacesconfig import ConfigLoader
from bioseq_dl.constants.databases import BASE_CONFIG_DIR
from bioseq_dl.constants.uniprot import XREF_MAPPING

from bioseq_dl.logging import get_logger

log = get_logger("bioseq_dl.core.utils.crossref_enrichment")

def run_crossref_enrichment(
        data: pd.DataFrame | List[Dict] | bytes | str | Dict , 
        crossref_fields: list, 
        format: Literal["dataframe", "json", "xml"] = "json",
        max_workers: int = 4,
        total_retries: int = 3
    ) -> Tuple[Any, Union[Dict, List[Dict]]]:
    if isinstance(data, pd.DataFrame) and data.empty:
        log.warning("Input DataFrame is empty. Skipping crossref enrichment.")
        return {"none": pd.DataFrame()}, {}
    elif isinstance(data, list) and len(data) == 0:
        log.warning("Input list is empty. Skipping crossref enrichment.")
        return {"none": pd.DataFrame()}, {}
    elif isinstance(data, dict) and len(data) == 0:
        log.warning("Input dict is empty. Skipping crossref enrichment.")
        return {"none": pd.DataFrame()}, {}
    elif isinstance(data, bytes) and data == b"":
        log.warning("Input bytes is empty. Skipping crossref enrichment.")
        return {"none": pd.DataFrame()}, {}
    elif isinstance(data, str) and data.strip() == "":
        log.warning("Input string is empty. Skipping crossref enrichment.")
        return {"none": pd.DataFrame()}, {}

    # Process crossref fields
    # Some definitions in crossref_fields may contain the database name and the method separated by underscore
    # For example, "brenda_getOptimumTemperature" should be processed as "brenda" and use the method "getOptimumTemperature"
    # Another example is giving only the database name "kegg" which means we should use all available methods for that database
    # For this reason we will make a new dictionary containing the databases and their methods
    # As last thing, some fields definitions will have another underscore after the method name, this will indicate the option to use
    # Example: "brenda_getOptimumTemperature_option1" should be processed as:
    # {"brenda": [{"method": "getOptimumTemperature", "option": "option1"}]}
    # Special case: "kegg_all" should be processed as:
    # {"kegg": [{"method": None, "option": None}]}

    processed_crossref_fields = {}
    for field in crossref_fields:
        # Ensure we only try to parse string entries
        if not isinstance(field, str):
            log.warning(f"Ignoring non-string crossref field: {field}")
            continue

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
                processed_crossref_fields.setdefault(db_name, []).append({"method": method_name, "option": option})
            else:
                processed_crossref_fields.setdefault(db_name, []).append({"method": method_part, "option": None})
        else:
            # Plain database name -> use all methods
            processed_crossref_fields.setdefault(field, []).append({"method": None, "option": None})

    log.info(f"Running crossref enrichment for fields: {crossref_fields}")
    config = ConfigLoader(config_dir=str(BASE_CONFIG_DIR) + "/uniprot_crossref")
    config.load_config("config_endpoints")

    print("Processed crossref fields:", processed_crossref_fields)
    print("Crossref fields:", crossref_fields)

    endpoint_specs = []
    # Generate the endpoint specs based on selected crossref fields
    for key, (uniprot_field, db_name) in XREF_MAPPING.items():
        if db_name and db_name in processed_crossref_fields.keys():
            log.debug(f"Processing crossref field: {key} -> db: {db_name}, uniprot_field: {uniprot_field}")
            if processed_crossref_fields[db_name] == [ {"method": None, "option": None} ]:
                # Use all available methods for this database
                log.debug(f"Using all available methods for database: {db_name}")
                endpoint_config = config.get_parameter(db_name)
                if not isinstance(endpoint_config, dict):
                    continue
                #if not endpoint_config.get("enabled", False):
                #   continue

                for ep_name, ep_info in endpoint_config.get("endpoints", {}).items():
                    if ep_info.get("enabled", False):
                        if "options" in ep_info:
                            for ep_option in ep_info.get("options", [None]):
                                endpoint_specs.append(
                                    EndpointSpec(
                                        database=db_name,
                                        endpoint=ep_name,
                                        option=ep_option,
                                        params=ep_info.get("params", {}),
                                    )
                                )
                        else:
                            endpoint_specs.append(
                                EndpointSpec(
                                    database=db_name,
                                    endpoint=ep_name,
                                    option=None,
                                    params=ep_info.get("params", {}),
                                )
                            )
            else:
                log.debug(f"Using specified methods for database: {db_name}")
                for method in processed_crossref_fields[db_name]:
                    method_name = method["method"]
                    option = method["option"]
                    endpoint_config = config.get_parameter(db_name)
                    if not isinstance(endpoint_config, dict):
                        continue
                    #if not endpoint_config.get("enabled", False):
                    #    continue

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
                        log.warning(f"Method {method_name} for database {db_name} is not enabled or does not exist in config.")
    
    log.debug(f"Final endpoint specs: {endpoint_specs}")
    enricher = CrossRefEnricher(endpoint_specs=endpoint_specs, max_workers=max_workers, total_retries=total_retries)
    enriched_data, enriched_metadata = enricher.enrich(data, format=format)
    
    # Normalize metadata to a dict to satisfy the annotated return type
    if enriched_metadata is None:
        enriched_metadata = {}
    
    # TODO: Patch solution probably I should only return the enriched data
    if isinstance(enriched_data, pd.DataFrame) and not enriched_data.empty:
        return enriched_data, enriched_metadata
    elif isinstance(enriched_data, list) and len(enriched_data) > 0:
        return enriched_data, enriched_metadata
    elif isinstance(enriched_data, dict) and len(enriched_data) > 0:
        return enriched_data, enriched_metadata
    log.warning("Crossref enrichment returned empty DataFrame or result is not a DataFrame")
    return {"none": pd.DataFrame()}, {}