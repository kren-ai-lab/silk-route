import logging
import pandas as pd
from typing import Tuple, Dict, Any, Literal, List

from bioseq_dl.core.crossref_enricher import CrossRefEnricher, EndpointSpec
from bioseq_dl.core.interfacesconfig import ConfigLoader
from bioseq_dl.constants.databases import BASE_CONFIG_DIR
from bioseq_dl.constants.uniprot import XREF_MAPPING

# ----- Optional logging (fallback to stdlib) -----
try:
    from bioseq_dl.logging import get_logger
except Exception:
    def get_logger(name: str) -> logging.Logger:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        return logging.getLogger(name)

log = get_logger("bioseq_dl.core.utils.crossref_enrichment")
# -------------------------------------------------

def run_crossref_enrichment(data: pd.DataFrame | List[Dict] | bytes | str | Dict , crossref_fields: list, format: Literal["dataframe", "json", "xml"] = "json") -> Tuple[Any, Dict]:
    if isinstance(data, pd.DataFrame) and data.empty:
        log.warning("Input DataFrame is empty. Skipping crossref enrichment.")
        return pd.DataFrame(), {}
    elif isinstance(data, list) and len(data) == 0:
        log.warning("Input list is empty. Skipping crossref enrichment.")
        return pd.DataFrame(), {}
    elif isinstance(data, dict) and len(data) == 0:
        log.warning("Input dict is empty. Skipping crossref enrichment.")
        return pd.DataFrame(), {}
    elif isinstance(data, bytes) and data == b"":
        log.warning("Input bytes is empty. Skipping crossref enrichment.")
        return pd.DataFrame(), {}
    elif isinstance(data, str) and data.strip() == "":
        log.warning("Input string is empty. Skipping crossref enrichment.")
        return pd.DataFrame(), {}

    log.info(f"Running crossref enrichment for fields: {crossref_fields}")
    config = ConfigLoader(config_dir=str(BASE_CONFIG_DIR) + "/uniprot_crossref")
    config.load_config("config_endpoints")

    endpoint_specs = []
    # Generate the endpoint specs based on selected crossref fields
    for key, (uniprot_field, db_name) in XREF_MAPPING.items():
        if db_name and db_name in crossref_fields:
            log.debug(f"Processing crossref field: {key} -> db: {db_name}, uniprot_field: {uniprot_field}")
            endpoint_config = config.get_parameter(db_name)
            if not isinstance(endpoint_config, dict):
                continue
            #if not endpoint_config.get("enabled", False):
            #    continue

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

    log.debug(f"Final endpoint specs: {endpoint_specs}")
    enricher = CrossRefEnricher(endpoint_specs)
    enriched_data, enriched_metadata = enricher.enrich(data, format=format)
    
    # Normalize metadata to a dict to satisfy the annotated return type
    if enriched_metadata is None:
        enriched_metadata = {}
    elif not isinstance(enriched_metadata, dict):
        enriched_metadata = {"metadata": enriched_metadata}
    
    # TODO: Patch solution probably I should only return the enriched data
    if isinstance(enriched_data, pd.DataFrame) and not enriched_data.empty:
        return enriched_data, enriched_metadata
    elif isinstance(enriched_data, list) and len(enriched_data) > 0:
        return enriched_data, enriched_metadata
    elif isinstance(enriched_data, dict) and len(enriched_data) > 0:
        return enriched_data, enriched_metadata
    log.warning("Crossref enrichment returned empty DataFrame or result is not a DataFrame")
    return pd.DataFrame(), {}