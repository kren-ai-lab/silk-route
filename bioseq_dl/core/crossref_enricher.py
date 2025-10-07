from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import pandas as pd

from bioseq_dl.core.utils.query_builders import QUERY_BUILDERS, INTERFACE_CLASSES
from bioseq_dl.constants.databases import BASE_CONFIG_DIR

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
            config_path: Optional[str] = None
        ) -> None:
        """
        Initialize with a single endpoint specification.
        """
        self.endpoint_specs = endpoint_specs
        self.config_path = config_path


            
    def _check_interface_availability(self, database: str) -> bool:
        """
        Check if the interface class for the given database is available.
        """
        return database in INTERFACE_CLASSES
    
    def _validate_dataframe(self, df: pd.DataFrame) -> None:
        """
        Validate that the DataFrame contains required columns for each endpoint.
        """
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("Input DataFrame must be a non-empty pandas DataFrame.")

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
        Create the correct interface instance.
        """
        if database_name not in INTERFACE_CLASSES:
            raise ValueError(f"Unsupported database: {database_name}")

        # Most interfaces have parameterless constructors
        return INTERFACE_CLASSES[database_name]()
    
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
        params: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        English docs:
        Build query from row using the registered query-builder, perform fetch_single or fetch_batch,
        and merge the API result with the original row (row-expanded).
        """
        # Search for an available builder via a search key: {database}_{endpoint}[_option]
        qb = self._resolve_query_builder(spec)

        query_params = qb(row, params)

        method_params = {
            "method": spec.endpoint,
            "parse": True,
            "to_dataframe": True
        }

        if spec.option:
            method_params["option"] = spec.option

        if isinstance(query_params, dict) \
            or ( isinstance(query_params, list) and len(query_params) == 1 ):
            # If is a single elemnt dict, use the dict itself
            query_params = query_params[0] if isinstance(query_params, list) else query_params
            result = instance.fetch_single(
                query=query_params,
                **method_params
            )
        elif isinstance(query_params, list) and len(query_params) > 1:
            # If is a list of dicts, use batch
            print(f"Batch querying {spec.database}:{spec.endpoint}{'[' + spec.option + ']' if spec.option else ''} with {len(query_params)} queries and method_params: {method_params}")
            result = instance.fetch_batch(
                queries=query_params,
                **method_params
            )
        else:
            # Handle unexpected query_params format
            result = pd.DataFrame()
    
        # Merge result with original row
        if not isinstance(result, pd.DataFrame) or result.empty:
            return row.to_frame().T  # Return original row as single-row DataFrame
        # Expand original row to match the number of result rows, then column-wise concat
        row_expanded = pd.concat(
            [pd.DataFrame([row] * len(result)).reset_index(drop=True),
                result.reset_index(drop=True)],
            axis=1
        )

        return row_expanded

    def _process_dataframe(
            self,
            df: pd.DataFrame,
            instance: Any,
            spec: EndpointSpec,
            params: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Apply search-then-merge for every row and vertically concatenate all row-expansions.
        """
        # Apply row-wise; collect per-row DataFrames
        all_results = [
            self._search_and_merge(row, instance, spec, params)
            for _, row in df.iterrows()
        ]

        if not all_results or all([r.empty for r in all_results]):
            return pd.DataFrame()
        
        return pd.concat(all_results, ignore_index=True)
    
    def enrich(
            self,
            df: pd.DataFrame,
            concat_results: bool = True,
    ):
        """
        Enrich the input DataFrame with cross-references from specified endpoints.
        """
        self._validate_dataframe(df)

        results = {}

        for spec in self.endpoint_specs:
            print(f"Processing {spec.database}:{spec.endpoint}{'[' + spec.option + ']' if spec.option else ''}...")
            self._check_interface_availability(spec.database)
            self._check_required_columns(df, spec)
            
            instance = self._build_interface(spec.database)
            params = self._prepare_params(spec)

            tmp_df = self._process_dataframe(df, instance, spec, params)

            results.update(
                {
                    f"{spec.database}_{spec.endpoint}{'_' + spec.option if spec.option else ''}": tmp_df
                    if isinstance(tmp_df, pd.DataFrame) and not tmp_df.empty
                    else pd.DataFrame()
                }
            )

        frames = []
        for df in results.values():
            # 1) Flatten MultiIndex columns (if any)
            if isinstance(df.columns, pd.MultiIndex):
                df = df.copy(); df.columns = ['__'.join(map(str, c)) for c in df.columns]
            # 2) Drop duplicate column names and reset index to avoid reindex issues on concat
            frames.append(df.loc[:, ~pd.Index(df.columns).duplicated()].reset_index(drop=True))

        out = pd.concat(frames, axis=0, ignore_index=True, sort=False)

        if concat_results:
            return out
        return results