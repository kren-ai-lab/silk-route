"""Cross-reference enrichment orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, cast
from xml.etree.ElementTree import Element, ElementTree, fromstring

import pandas as pd

from bioseq_dl.core.utils.query_builders import INTERFACE_CLASSES, get_query_builder

if TYPE_CHECKING:
    from bioseq_dl.core.interfaces.base import BaseAPIInterface
from bioseq_dl.core.utils.xmlhandler import elementtree_to_dataframe
from bioseq_dl.logging import get_logger

log = get_logger("bioseq_dl.interfaces.crossref_enricher")


@dataclass
class EndpointSpec:
    """Declarative specification for a single endpoint.

    - database: database key as used in INTERFACE_CLASSES (e.g., "uniprot", "brenda", "biogrid").
    - endpoint: method name to call within the interface (e.g., "search", "getKmValue", "xrefs").
    - option: optional modifier some interfaces support (e.g., GeneOntology categories).
    - params: static/default parameters to merge with query-builder results.
    - required_columns: optional list of column names this endpoint expects to find in the input row,
      used only for early validation / diagnostics. Query builders still receive the full row.
    """

    database: str
    endpoint: str
    option: str | None = None
    params: dict[str, Any] | None = None
    required_columns: list[str] | None = None

    @property
    def label(self) -> str:
        """Human-readable ``database:endpoint[option]`` label for logging."""
        return f"{self.database}:{self.endpoint}{f'[{self.option}]' if self.option else ''}"

    @property
    def key(self) -> str:
        """Registry / result key ``database_endpoint[_option]``."""
        return f"{self.database}_{self.endpoint}{f'_{self.option}' if self.option else ''}"


def specs_for_database(endpoint_config: Any, database: str) -> list[EndpointSpec]:
    """Expand a database's ENABLED endpoints into ``EndpointSpec`` objects.

    One spec per declared option (``[None]`` when an endpoint has none). Returns
    ``[]`` when the config is missing / not a dict. Shared by the CLI and the
    workflow "all methods" expansion paths.
    """
    if not isinstance(endpoint_config, dict):
        return []
    specs: list[EndpointSpec] = []
    for ep_name, ep_info in endpoint_config.get("endpoints", {}).items():
        if not ep_info.get("enabled", False):
            continue
        options = ep_info.get("options", [None]) if "options" in ep_info else [None]
        specs.extend(
            EndpointSpec(
                database=database,
                endpoint=ep_name,
                option=ep_option,
                params=ep_info.get("params", {}),
            )
            for ep_option in options
        )
    return specs


class CrossRefEnricher:
    """Reusable orchestrator that enriches a dataframe of sequences/IDs with cross-references from APIs.

    Key features:
    - Auto-detect available columns and validate per-endpoint requirements (optional).
    - Transparent handling of BRENDA (email/password) and BioGRID (API key) via config.
    - Returns a single enriched DataFrame or individual per-endpoint DataFrames.
    - Utility helpers for CSV I/O.
    """

    def __init__(
        self,
        endpoint_specs: list[EndpointSpec] | None = None,
        config_path: str | None = None,
        max_workers: int = 4,
        total_retries: int = 3,
    ) -> None:
        """Initialize with a single endpoint specification."""
        self.endpoint_specs = endpoint_specs or []
        self.config_path = config_path
        self.max_workers = max_workers
        self.total_retries = total_retries

    def _check_required_columns(self, df: pd.DataFrame, spec: EndpointSpec) -> None:
        """Raise if declared required columns are missing from the DataFrame."""
        if not spec.required_columns:
            return
        missing = [c for c in spec.required_columns if c not in df.columns]
        if missing:
            msg = f"Missing required columns for {spec.label}: {missing}"
            raise ValueError(msg)

    def _prepare_params(self, spec: EndpointSpec) -> dict[str, Any]:
        """Prepare base params for an endpoint, including auth and 'option' if provided."""
        params = dict(spec.params or {})
        if spec.option is not None:
            params["option"] = spec.option

        return params

    def _build_interface(self, database_name: str) -> BaseAPIInterface:
        """Create the correct interface instance with configured max_workers and total_retries."""
        if database_name not in INTERFACE_CLASSES:
            msg = f"Unsupported database: {database_name}"
            raise ValueError(msg)

        return INTERFACE_CLASSES[database_name](
            max_workers=self.max_workers, total_retries=self.total_retries
        )

    def _search_and_merge(
        self,
        row: pd.Series,
        instance: Any,
        spec: EndpointSpec,
        params: dict[str, Any],
        fmt: Literal["dataframe", "json", "xml"] = "dataframe",
    ) -> tuple[pd.DataFrame | list[dict[str, Any]], dict]:
        """Build query from row using the registered query-builder.

        Performs ``fetch_single`` or ``fetch_batch`` and merges the API result with the original row
        (row-expanded).
        """
        metadata = {}
        # Search for an available builder via a search key: {database}_{endpoint}[_option]
        qb = get_query_builder(spec.database, spec.endpoint, spec.option)

        query_params = qb(row, params)

        method_params = {"method": spec.endpoint, "parse": True, "format": fmt}

        if spec.option:
            method_params["option"] = spec.option

        if isinstance(query_params, dict) or (isinstance(query_params, list) and len(query_params) == 1):
            # If is a single elemnt dict, use the dict itself
            query_params = query_params[0] if isinstance(query_params, list) else query_params
            result, metadata = instance.fetch_single(query=query_params, **method_params)
        elif isinstance(query_params, list) and len(query_params) > 1:
            # If is a list of dicts, use batch
            log.debug(
                "Batch querying %s with %s queries and method_params: %s",
                spec.label,
                len(query_params),
                method_params,
            )
            result, metadata = instance.fetch_batch(queries=query_params, **method_params)
        # Handle unexpected query_params format
        elif fmt == "dataframe":
            result = pd.DataFrame()
        else:
            result = []

        return result, metadata

    def _merge_metadata(self, meta1: dict, meta2: dict) -> dict:
        """Merge two metadata dicts, concatenating lists and summing counts where appropriate."""
        merged = dict(meta1)  # Start with a copy of the first metadata

        if not isinstance(meta2, dict):
            return merged  # If meta2 is not a dict, just return meta1
        if not isinstance(meta1, dict):
            return meta2  # If meta1 is not a dict, just return meta2

        for key, value in meta2.items():
            if key in merged:
                if isinstance(merged[key], list) and isinstance(value, list):
                    merged[key] = merged[key] + value  # Concatenate lists
                # started_at / finished_at: keep the widest window across endpoints.
                # ISO-8601 UTC strings compare chronologically, so min/max are safe.
                elif key in ("started_at", "finished_at") and merged[key] and value:
                    merged[key] = min(merged[key], value) if key == "started_at" else max(merged[key], value)
                elif isinstance(merged[key], (int, float)) and isinstance(value, (int, float)):
                    merged[key] = merged[key] + value  # Sum counts
                # Special case: data_info, in this case we just need to sum n_missing, because all metadata
                # values have the same
                # structure across endpoints, so they will be overridden by the same value.
                elif key == "data_info":
                    if "total_entries" in merged[key] and "total_entries" in value:
                        merged[key]["total_entries"] = merged[key]["total_entries"] + value["total_entries"]
                    for column1, column2 in zip(
                        merged[key].get("columns", []), value.get("columns", []), strict=False
                    ):
                        if column1["name"] == column2["name"]:
                            column1["n_missing"] = column1.get("n_missing", 0) + column2.get("n_missing", 0)
                else:
                    # In this case, Override strings will not cause major issues, because all metadata values
                    # Have the same structure across endpoints, so they will be overridden by the same value.
                    merged[key] = value
            else:
                merged[key] = value  # Add new key-value pair

        return merged

    @staticmethod
    def _clean_frame(result: Any) -> pd.DataFrame | None:
        """Coerce a raw row-result to a cleaned DataFrame, or ``None`` to skip it.

        Accepts a DataFrame, list-of-dicts, or single dict; drops duplicate
        columns and accidental numeric-only column names. Returns ``None`` for
        empty or uncoercible results.
        """
        if isinstance(result, pd.DataFrame):
            df_result = result
        elif isinstance(result, list):
            if not result:
                return None
            try:
                df_result = pd.DataFrame(result)
            except Exception:  # skip records that will not coerce to a DataFrame
                log.exception("Dropping cross-ref result that will not coerce to a DataFrame: %r", result)
                return None
        elif isinstance(result, dict):
            try:
                df_result = pd.DataFrame([result])
            except Exception:  # skip records that will not coerce to a DataFrame
                log.exception("Dropping cross-ref result that will not coerce to a DataFrame: %r", result)
                return None
        else:
            log.debug("Skipping unsupported cross-ref result type: %s", type(result).__name__)
            return None

        if df_result.empty:
            return None
        df_result = df_result.loc[:, ~pd.Index(df_result.columns).duplicated()]
        # Drop accidental numeric-only column names like '1','2','3',...
        cols_to_keep = [c for c in df_result.columns if not str(c).isdigit()]
        if not cols_to_keep:
            return None
        return df_result.loc[:, cols_to_keep].reset_index(drop=True)

    def _process_dataframe(
        self,
        df: pd.DataFrame,
        instance: Any,
        spec: EndpointSpec,
        params: dict[str, Any],
        fmt: Literal["dataframe", "json", "xml"] = "dataframe",
    ) -> tuple[pd.DataFrame | list | ElementTree[Element[str] | None], dict]:
        """Apply search-then-merge for every row and vertically concatenate all row-expansions."""
        # Apply row-wise; collect per-row DataFrames
        all_metadata = {}
        all_results = []

        for _, row in df.iterrows():
            result, metadata = self._search_and_merge(row, instance, spec, params, fmt)
            all_results.append(result)
            all_metadata = self._merge_metadata(all_metadata, metadata)

        # TODO(diego): comprobar si este cambio no es problematico
        if fmt == "dataframe":
            # Unpack (df, metadata) tuples; metadata currently unused
            dfs = [res[0] if isinstance(res, tuple) else res for res in all_results]
            cleaned_results = [
                cleaned for result in dfs if (cleaned := self._clean_frame(result)) is not None
            ]
            if not cleaned_results:
                return pd.DataFrame(), all_metadata
            return pd.concat(cleaned_results, ignore_index=True, sort=False), all_metadata
        if fmt == "json":
            cleaned_results = []
            for raw in all_results:
                item = raw[0] if isinstance(raw, tuple) else raw
                if isinstance(item, list):
                    cleaned_results.extend(item)
            return cleaned_results, all_metadata
        if fmt == "xml":
            # TODO(diego): check if this code is correct, i did a lot of changes recently regarding XML
            # exporting
            # Make final root
            merged_root = Element("results")

            for xml_bytes in all_results:
                # Parse each XML
                root = fromstring(cast("str | bytes", xml_bytes))  # noqa: S314  # trusted cross-ref API response

                # Copy all <item> to final root
                for item in root.findall("item"):
                    merged_root.append(item)

            return ElementTree(merged_root), all_metadata
        msg = f"Unsupported format: {fmt}"
        raise ValueError(msg)

    def enrich(
        self,
        data: Any,
        format: Literal["dataframe", "json", "xml"] = "dataframe",  # noqa: A002
    ) -> tuple[dict, dict]:
        """Enrich the input DataFrame with cross-references from specified endpoints."""
        # For an easier handling, convert input data to DataFrame if needed
        if isinstance(data, (list, dict)):
            df = pd.DataFrame(data)
        elif isinstance(data, pd.DataFrame):
            df = data
        elif isinstance(data, ElementTree):
            df = elementtree_to_dataframe(tree=data)
        elif isinstance(data, str):
            df = pd.read_json(data)
        else:
            msg = "Input data must be a pandas DataFrame, list of dicts, or dict."
            raise TypeError(msg)

        results = {}
        metadata = {}
        for spec in self.endpoint_specs:
            log.debug("Processing %s...", spec.label)
            log.info("Checking required columns for %s...", spec.label)
            self._check_required_columns(df, spec)

            log.info("Building interface for %s...", spec.database)
            instance = self._build_interface(spec.database)
            params = self._prepare_params(spec)
            log.info("Prepared params for %s: %s", spec.label, params)

            processed_data, processed_metadata = self._process_dataframe(df, instance, spec, params, format)
            results[spec.key] = processed_data
            metadata[spec.key] = processed_metadata

        if format not in ("dataframe", "json", "xml"):
            msg = f"Unsupported format: {format}"
            raise ValueError(msg)
        return results, metadata
