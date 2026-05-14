from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple, Literal
from xml.etree.ElementTree import ElementTree, Element
import pandas as pd

from bioseq_dl.core.utils.query_builders import QUERY_BUILDERS, INTERFACE_CLASSES
from bioseq_dl.constants.databases import BASE_CONFIG_DIR

from bioseq_dl.core.utils.xmlhandler import elementtree_to_dataframe

from bioseq_dl.logging import get_logger

log = get_logger("bioseq_dl.interfaces.crossref_enricher")

@dataclass
class EndpointSpec:
    """
    Declarative specification for a single endpoint.
    - database: database key as used in INTERFACE_CLASSES (e.g., "uniprot", "brenda", "biogrid").
    - endpoint: method name to call within the interface (e.g., "search", "getKmValue", "xrefs").
    - option: optional modifier some interfaces support (e.g., GeneOntology categories).
    - params: static/default parameters to merge with query-builder results.
    - required_columns: optional list of column names this endpoint expects to find in the input row,
      used only for early validation / diagnostics. Query builders still receive the full row.
    """
    database: str
    endpoint: str
    option: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    required_columns: Optional[List[str]] = None

class CrossRefEnricher():
    """
    A reusable, high-level orchestrator to enrich a dataframe of sequences/IDs with
    cross-references fetched from multiple biological APIs.

    Key features:
    - Auto-detect available columns and validate per-endpoint requirements (optional).
    - Transparent handling of BRENDA (email/password) and BioGRID (API key) via config.
    - Returns a single enriched DataFrame or individual per-endpoint DataFrames.
    - Utility helpers for CSV I/O.
    """

    def __init__(
            self, 
            endpoint_specs: List[EndpointSpec] = [],
            config_path: Optional[str] = None,
            max_workers: int = 4,
            total_retries: int = 3
        ) -> None:
        """
        Initialize with a single endpoint specification.
        """
        self.endpoint_specs = endpoint_specs
        self.config_path = config_path
        self.max_workers = max_workers
        self.total_retries = total_retries

    def _check_interface_availability(self, database: str) -> bool:
        """
        Check if the interface class for the given database is available.
        """
        return database in INTERFACE_CLASSES
    
    def _check_required_columns(self, df: pd.DataFrame, spec: EndpointSpec) -> None:
        """
        Optional check to warn/raise if declared required columns are missing.
        """
        if not spec.required_columns:
            return
        missing = [c for c in spec.required_columns if c not in df.columns]
        if missing:
            raise ValueError(
                f"Missing required columns for {spec.database}:{spec.endpoint}"
                f"{'[' + spec.option + ']' if spec.option else ''}: {missing}"
            )
    
    def _prepare_params(self, spec: EndpointSpec) -> Dict[str, Any]:
        """
        Prepare base params for an endpoint, including auth and 'option' if provided.
        """
        params = dict(spec.params or {})
        if spec.option is not None:
            params["option"] = spec.option

        return params
    
    def _build_interface(self, database_name: str):
        """
        Create the correct interface instance with configured max_workers and total_retries.
        """
        if database_name not in INTERFACE_CLASSES:
            raise ValueError(f"Unsupported database: {database_name}")

        return INTERFACE_CLASSES[database_name](
            max_workers=self.max_workers,
            total_retries=self.total_retries
        )
    
    def _query_builder_key(self, spec: EndpointSpec) -> str:
        """
        English docs:
        Compute the registry key for QUERY_BUILDERS like 'db_endpoint_option' or 'db_endpoint'.
        """
        if spec.option:
            return f"{spec.database}_{spec.endpoint}_{spec.option}"
        return f"{spec.database}_{spec.endpoint}"

    def _resolve_query_builder(self, spec: EndpointSpec):
        """
        English docs:
        Find the query builder callable from QUERY_BUILDERS registry.
        """
        key = self._query_builder_key(spec)
        qb = QUERY_BUILDERS.get(key)
        if not qb:
            raise ValueError(f"No query builder registered for key '{key}'")
        return qb

    def _search_and_merge(
        self,
        row: pd.Series,
        instance: Any,
        spec: EndpointSpec,
        params: Dict[str, Any],
        #concat_results: bool = True,
        format: Literal["dataframe", "json", "xml"] = "dataframe"
    ) -> Tuple[pd.DataFrame|List[Dict[str, Any]], Dict]:
        """
        Build query from row using the registered query-builder, perform fetch_single or fetch_batch,
        and merge the API result with the original row (row-expanded).
        """
        metadata = {}
        # Search for an available builder via a search key: {database}_{endpoint}[_option]
        qb = self._resolve_query_builder(spec)

        query_params = qb(row, params)

        method_params = {
            "method": spec.endpoint,
            "parse": True,
            "format": format
        }

        if spec.option:
            method_params["option"] = spec.option

        if isinstance(query_params, dict) \
            or ( isinstance(query_params, list) and len(query_params) == 1 ):
            # If is a single elemnt dict, use the dict itself
            query_params = query_params[0] if isinstance(query_params, list) else query_params
            result, metadata = instance.fetch_single(
                query=query_params,
                **method_params
            )
        elif isinstance(query_params, list) and len(query_params) > 1:
            # If is a list of dicts, use batch
            log.debug(f"Batch querying {spec.database}:{spec.endpoint}{'[' + spec.option + ']' if spec.option else ''} with {len(query_params)} queries and method_params: {method_params}")
            result, metadata = instance.fetch_batch(
                queries=query_params,
                **method_params
            )
        else:
            # Handle unexpected query_params format
            if format == "dataframe":
                result = pd.DataFrame()
            else:
                result = []

        if format == "dataframe":
            # Merge result with original row
            if not isinstance(result, pd.DataFrame) or result.empty:
                # if concat_results:
                #     return row.to_frame().T, metadata  # Return original row as single-row DataFrame
                # else:
                return result, metadata
            # Expand original row to match the number of result rows, then column-wise concat
            # if concat_results:
            #     row_expanded = pd.concat(
            #         [pd.DataFrame([row] * len(result)).reset_index(drop=True),
            #             result.reset_index(drop=True)],
            #         axis=1
            #     )
            #     return row_expanded, metadata
            # else:
            return result, metadata
        else:
            # if concat_results:
            #     # Merge each dict in result with original row dict
            #     if not isinstance(result, list) or not result:
            #         return [row.to_dict()], metadata  # Return original row as single dict in list
            #     merged_results = [
            #         {**row.to_dict(), **res} for res in result
            #     ]
            #     return merged_results, metadata
            # else:
            return result, metadata
    
    def _merge_metadata(self, meta1: Dict, meta2: Dict) -> Dict:
        """
        Merge two metadata dicts, concatenating lists and summing counts where appropriate.
        """
        merged = dict(meta1)  # Start with a copy of the first metadata

        if not isinstance(meta2, dict):
            return merged  # If meta2 is not a dict, just return meta1
        if not isinstance(meta1, dict):
            return meta2  # If meta1 is not a dict, just return meta2

        for key, value in meta2.items():
            if key in merged:
                if isinstance(merged[key], list) and isinstance(value, list):
                    merged[key] = merged[key] + value  # Concatenate lists
                elif isinstance(merged[key], (int, float)) and isinstance(value, (int, float)):
                    merged[key] = merged[key] + value  # Sum counts
                # Special case: data_info, in this case we just need to sum n_missing, because all metadata values have the same
                # structure across endpoints, so they will be overridden by the same value.
                elif key == "data_info":
                    if "total_entries" in merged[key] and "total_entries" in value:
                        merged[key]["total_entries"] = merged[key]["total_entries"] + value["total_entries"]
                    for column1, column2 in zip(merged[key].get("columns", []), value.get("columns", [])):
                        if column1["name"] == column2["name"]:
                            column1["n_missing"] = column1.get("n_missing", 0) + column2.get("n_missing", 0)
                else:
                    # In this case, Override strings will not cause major issues, because all metadata values
                    # Have the same structure across endpoints, so they will be overridden by the same value.
                    merged[key] = value
            else:
                merged[key] = value  # Add new key-value pair

        return merged

    def _process_dataframe(
            self,
            df: pd.DataFrame,
            instance: Any,
            spec: EndpointSpec,
            params: Dict[str, Any],
            #concat_results: bool = True,
            format: Literal["dataframe", "json", "xml"] = "dataframe"
    ) -> Tuple[pd.DataFrame|List[Dict[str, Any]]|ElementTree[Element[str] | None], Dict]:
        """
        Apply search-then-merge for every row and vertically concatenate all row-expansions.
        """
        # Apply row-wise; collect per-row DataFrames
        all_metadata = {}
        all_results = []

        for _, row in df.iterrows():
            result, metadata = self._search_and_merge(row, instance, spec, params, format)
            all_results.append(result)
            all_metadata = self._merge_metadata(all_metadata, metadata)

        # TODO comprobar si este cambio no es problematico
        if format == "dataframe":
            # Unpack (df, metadata) tuples; metadata currently unused
            dfs = [res[0] if isinstance(res, tuple) else res for res in all_results]

            # Normalize and filter results: keep only non-empty DataFrames.
            cleaned_results = []
            for result in dfs:
                # If already a DataFrame, ensure it's non-empty and drop duplicate columns.
                if isinstance(result, pd.DataFrame):
                    if result.empty:
                        continue
                    result = result.loc[:, ~pd.Index(result.columns).duplicated()]

                    # Drop accidental numeric-only column names like '1','2','3',...
                    cols_to_keep = [c for c in result.columns if not str(c).isdigit()]
                    if not cols_to_keep:
                        continue
                    cleaned_results.append(result.loc[:, cols_to_keep].reset_index(drop=True))
                    continue

                # If result is a list (likely list of dicts), try to coerce to DataFrame.
                if isinstance(result, list):
                    if not result:
                        continue
                    try:
                        df_result = pd.DataFrame(result)
                    except Exception:
                        continue
                    if df_result.empty:
                        continue
                    df_result = df_result.loc[:, ~pd.Index(df_result.columns).duplicated()]

                    # Drop accidental numeric-only column names like '1','2','3',...
                    cols_to_keep = [c for c in df_result.columns if not str(c).isdigit()]
                    if not cols_to_keep:
                        continue
                    cleaned_results.append(df_result.loc[:, cols_to_keep].reset_index(drop=True))
                    continue

                # If result is a single dict, wrap into a DataFrame.
                if isinstance(result, dict):
                    try:
                        df_result = pd.DataFrame([result])
                    except Exception:
                        continue
                    if df_result.empty:
                        continue
                    df_result = df_result.loc[:, ~pd.Index(df_result.columns).duplicated()]

                    # Drop accidental numeric-only column names like '1','2','3',...
                    cols_to_keep = [c for c in df_result.columns if not str(c).isdigit()]
                    if not cols_to_keep:
                        continue
                    cleaned_results.append(df_result.loc[:, cols_to_keep].reset_index(drop=True))
                    continue

                # Unknown/unsupported type: skip
                continue

            if not cleaned_results:
                return pd.DataFrame(), all_metadata

            return pd.concat(cleaned_results, ignore_index=True, sort=False), all_metadata
        elif format == "json":
            cleaned_results = []
            for result in all_results:
                if isinstance(result, tuple):
                    result = result[0]
                if isinstance(result, list):
                    cleaned_results.extend(result)
            return cleaned_results, all_metadata
        elif format == "xml":
            # TODO check if this code is correct, i did a lot of changes recently regarding XML exporting
            import xml.etree.ElementTree as ET
            # Make final root
            merged_root = ET.Element("results")

            for xml_bytes in all_results:
                # Parse each XML
                root = ET.fromstring(xml_bytes)

                # Copy all <item> to final root
                for item in root.findall("item"):
                    merged_root.append(item)

            return ET.ElementTree(merged_root), all_metadata
        else:
            raise ValueError(f"Unsupported format: {format}")

    def enrich(
            self,
            data: pd.DataFrame|List[Dict[str, Any]]|Dict[str, Any] | ElementTree | str  ,
            format: Literal["dataframe", "json", "xml"] = "dataframe"
    ):
        """
        Enrich the input DataFrame with cross-references from specified endpoints.
        """
        # For an easier handling, convert input data to DataFrame if needed
        if isinstance(data, list) or isinstance(data, dict):
            df = pd.DataFrame(data)
        elif isinstance(data, pd.DataFrame):
            df = data
        elif isinstance(data, ElementTree):
            df = elementtree_to_dataframe(tree=data)
        elif isinstance(data, str):
            df = pd.read_json(data)
        else:
            raise ValueError("Input data must be a pandas DataFrame, list of dicts, or dict.")
        

        results = {}
        metadata = {}
        for spec in self.endpoint_specs:
            log.debug(f"Processing {spec.database}:{spec.endpoint}{'[' + spec.option + ']' if spec.option else ''}...")
            log.info(f"Checking availability for interface: {spec.database}")
            self._check_interface_availability(spec.database)
            log.info(f"Checking required columns for {spec.database}:{spec.endpoint}{'[' + spec.option + ']' if spec.option else ''}...")
            self._check_required_columns(df, spec)

            log.info(f"Building interface for {spec.database}...")
            instance = self._build_interface(spec.database)
            params = self._prepare_params(spec)
            log.info(f"Prepared params for {spec.database}:{spec.endpoint}{'[' + spec.option + ']' if spec.option else ''}: {params}")

            processed_data, processed_metadata = self._process_dataframe(df, instance, spec, params, format)
            results.update(
                {
                    f"{spec.database}_{spec.endpoint}{'_' + spec.option if spec.option else ''}": processed_data
                }
            )
            metadata.update(
                {
                    f"{spec.database}_{spec.endpoint}{'_' + spec.option if spec.option else ''}": processed_metadata
                }
            )

        if format == "dataframe":
            frames = []
            for df in results.values():
                # 1) Flatten MultiIndex columns (if any)
                if isinstance(df.columns, pd.MultiIndex):
                    df = df.copy(); df.columns = ['__'.join(map(str, c)) for c in df.columns]
                # 2) Drop duplicate column names and reset index to avoid reindex issues on concat
                frames.append(df.loc[:, ~pd.Index(df.columns).duplicated()].reset_index(drop=True))

            # if concat_results:
            #     if frames and any([not f.empty for f in frames]):
            #         out = pd.concat(frames, axis=0, ignore_index=True, sort=False)
            #         return out, metadata
            #     else:
            #         return pd.DataFrame(), metadata
            # else:
            return results, metadata
        elif format in ["json", "xml"]:
            # if concat_results:
            #     # Flatten all dict lists into a single list
            #     combined_results = []
            #     for lst in results.values():
            #         combined_results.extend(lst)
            #     return combined_results, metadata
            return results, metadata
        else:
            raise ValueError(f"Unsupported format: {format}")
