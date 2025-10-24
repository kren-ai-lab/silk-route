import logging
import pandas as pd

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

log = get_logger("bioseq_dl.gui.components.utils")
# -------------------------------------------------

def load_dataframe(file):
    """Carga un archivo CSV o Excel en un DataFrame."""
    if file is None:
        return None, []
    try:
        if file.name.endswith(".csv"):
            df = pd.read_csv(file.name)
        elif file.name.endswith(".xlsx"):
            df = pd.read_excel(file.name)
        else:
            return None, []
        return df, list(df.columns)
    except Exception as e:
        return None, [f"Error: {e}"]


def run_crossref_enrichment(df, crossref_fields):
    if df.empty:
        return df
    log.info(f"Running crossref enrichment for fields: {crossref_fields}")
    config = ConfigLoader(config_dir=str(BASE_CONFIG_DIR) + "/uniprot_crossref")
    config.load_config("config_endpoints")

    endpoint_specs = []
    # Generate the endpoint specs based on selected crossref fields
    for key, (uniprot_field, db_name) in XREF_MAPPING.items():
        if db_name and key in crossref_fields:
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
    crossref_df = enricher.enrich(df, concat_results=True)
    if isinstance(crossref_df, pd.DataFrame) and not crossref_df.empty:
        log.info(f"Crossref enrichment resulted in {len(crossref_df)} rows")
        return crossref_df
    log.warning("Crossref enrichment returned empty DataFrame or result is not a DataFrame")
    return df