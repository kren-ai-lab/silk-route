"""Cross-reference enrichment orchestrator."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, cast
from xml.etree.ElementTree import Element, ElementTree, fromstring

import pandas as pd

from bioseq_dl.core.utils.query_builders import INTERFACE_CLASSES, QUERY_BUILDERS, QueryBuilder

if TYPE_CHECKING:
    from bioseq_dl.core.interfaces.base import BaseAPIInterface
from bioseq_dl.core.utils.xmlhandler import elementtree_to_dataframe
from bioseq_dl.logging import get_logger

log = get_logger("bioseq_dl.interfaces.crossref_enricher")

GRAPH_LIKE_ENRICHMENT_OUTPUTS = {
    "pathwaycommons_fetch": "jsonld",
    "pathwaycommons_neighborhood": "jsonld",
}
GRAPH_OUTPUT_NOTE = (
    "graph_json is intentionally preserved as raw graph data and is not interpreted by "
    "BioSeqDownloader."
)

CrossRefInternalFormat = Literal["dataframe", "json", "xml"]
CrossRefFormat = Literal["csv", "dataframe", "json", "xml"]


def normalize_crossref_format(format_value: str) -> CrossRefInternalFormat:
    """Normalize user-facing enrichment formats to internal CrossRefEnricher formats."""
    normalized_format = str(format_value).strip().lower()
    if normalized_format == "csv":
        return "dataframe"
    if normalized_format in {"dataframe", "json", "xml"}:
        return cast("CrossRefInternalFormat", normalized_format)
    supported_formats = "csv, dataframe, json, xml"
    msg = (
        f"Unsupported cross-reference format '{format_value}'. "
        f"Supported formats: {supported_formats}."
    )
    raise ValueError(msg)


def get_crossref_interface_kwargs(database_name: str) -> dict[str, Any]:
    """Return interface initialization defaults for cross-reference enrichment."""
    if database_name == "alphafold":
        return {"structures": ["pdb"]}
    return {}


def merge_interface_options(
    database_name: str,
    interface_options: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    """Merge database-specific interface defaults with caller-provided options."""
    merged_options = get_crossref_interface_kwargs(database_name)
    if interface_options and database_name in interface_options:
        merged_options.update(interface_options[database_name])
    return merged_options


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


def get_source_context_value(row: pd.Series, column: str) -> Any | None:
    """Return a non-missing source value from an enrichment input row."""
    value = row.get(column)
    if value is None or value is pd.NA:
        return None
    missing = pd.isna(value)
    if not hasattr(missing, "__len__") and bool(missing):
        return None
    return value


def build_source_context(
    row: pd.Series,
    source_query: dict[str, Any] | list[Any],
    *,
    source_database: str,
    source_endpoint: str,
) -> dict[str, Any]:
    """Return source-row and endpoint provenance for an enrichment result."""
    return {
        "source_accession": get_source_context_value(row, "accession"),
        "source_protein_name": get_source_context_value(row, "protein_name"),
        "source_organism_id": get_source_context_value(row, "organism_id"),
        "source_query": source_query,
        "source_database": source_database,
        "source_endpoint": source_endpoint,
    }


def get_enrichment_output_key(database_name: str, endpoint_name: str) -> str:
    """Return the stable output key used to classify enrichment results."""
    return f"{database_name}_{endpoint_name}"


def is_graph_like_enrichment(database_name: str, endpoint_name: str) -> bool:
    """Return whether an enrichment endpoint must preserve a raw graph payload."""
    output_key = get_enrichment_output_key(database_name, endpoint_name)
    return output_key in GRAPH_LIKE_ENRICHMENT_OUTPUTS


def normalize_graph_payload(raw_result: Any) -> dict[str, Any] | list[Any] | Any:
    """Return a JSON-serializable graph payload without interpreting graph semantics."""
    if isinstance(raw_result, pd.DataFrame):
        return raw_result.to_dict(orient="records")
    if raw_result is None or (isinstance(raw_result, (dict, list)) and not raw_result):
        return []
    return raw_result


def count_graph_records(graph_payload: Any) -> int:
    """Count top-level records in a preserved graph payload."""
    if isinstance(graph_payload, dict):
        graph_records = graph_payload.get("@graph")
        if isinstance(graph_records, list):
            return len(graph_records)
        return 1 if graph_payload else 0
    if isinstance(graph_payload, list):
        return len(graph_payload)
    return 0 if graph_payload is None else 1


def build_graph_output_row(
    raw_result: Any,
    row: pd.Series,
    source_query: dict[str, Any] | list[Any],
    *,
    source_database: str,
    source_endpoint: str,
) -> dict[str, Any]:
    """Build one compact provenance row containing a serialized raw graph payload."""
    output_key = get_enrichment_output_key(source_database, source_endpoint)
    graph_payload = normalize_graph_payload(raw_result)
    return {
        **build_source_context(
            row,
            source_query,
            source_database=source_database,
            source_endpoint=source_endpoint,
        ),
        "graph_format": GRAPH_LIKE_ENRICHMENT_OUTPUTS[output_key],
        "graph_record_count": count_graph_records(graph_payload),
        "graph_json": json.dumps(graph_payload, ensure_ascii=False, default=str),
    }


def attach_source_context(
    result: Any,
    row: pd.Series,
    source_query: dict[str, Any] | list[Any],
    *,
    source_database: str,
    source_endpoint: str,
) -> Any:
    """Attach input-row and endpoint provenance to a cross-reference result."""
    if isinstance(result, pd.DataFrame) and result.empty:
        return result
    if isinstance(result, (list, dict)) and not result:
        return result

    context = build_source_context(
        row,
        source_query,
        source_database=source_database,
        source_endpoint=source_endpoint,
    )
    context = {key: value for key, value in context.items() if value is not None}

    if isinstance(result, pd.DataFrame):
        enriched_result = result.copy()
        for key, value in context.items():
            enriched_result[key] = [value] * len(enriched_result)
        return enriched_result
    if isinstance(result, list):
        return [dict(item, **context) if isinstance(item, dict) else item for item in result]
    if isinstance(result, dict):
        return dict(result, **context)
    return result


def add_endpoint_result_metadata(metadata: dict, spec: EndpointSpec) -> dict:
    """Add endpoint semantics needed to interpret exported enrichment results."""
    enriched_metadata = dict(metadata) if isinstance(metadata, dict) else {}
    if is_graph_like_enrichment(spec.database, spec.endpoint):
        enriched_metadata.update(
            {
                "output_kind": "raw_graph",
                "graph_serialization": "json",
                "graph_tabularization": "one_row_per_source",
                "note": GRAPH_OUTPUT_NOTE,
            }
        )
    return enriched_metadata


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
        interface_options: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Initialize with a single endpoint specification."""
        self.endpoint_specs = endpoint_specs or []
        self.config_path = config_path
        self.max_workers = max_workers
        self.total_retries = total_retries
        self.interface_options = interface_options or {}

    def _check_interface_availability(self, database: str) -> bool:
        """Check if the interface class for the given database is available."""
        return database in INTERFACE_CLASSES

    def _check_required_columns(self, df: pd.DataFrame, spec: EndpointSpec) -> None:
        """Raise if declared required columns are missing from the DataFrame."""
        if not spec.required_columns:
            return
        missing = [c for c in spec.required_columns if c not in df.columns]
        if missing:
            msg = (
                f"Missing required columns for {spec.database}:{spec.endpoint}"
                f"{'[' + spec.option + ']' if spec.option else ''}: {missing}"
            )
            raise ValueError(msg)

    def _prepare_params(self, spec: EndpointSpec) -> dict[str, Any]:
        """Prepare base params for an endpoint, including auth and 'option' if provided."""
        params = dict(spec.params or {})
        if spec.option is not None:
            params["option"] = spec.option

        return params

    def _build_interface(self, database_name: str) -> BaseAPIInterface:
        """Create an interface with configured cross-reference defaults."""
        if database_name not in INTERFACE_CLASSES:
            msg = f"Unsupported database: {database_name}"
            raise ValueError(msg)

        interface_kwargs = merge_interface_options(database_name, self.interface_options)
        return INTERFACE_CLASSES[database_name](
            max_workers=self.max_workers,
            total_retries=self.total_retries,
            **interface_kwargs,
        )

    def _query_builder_key(self, spec: EndpointSpec) -> str:
        """Compute the registry key for QUERY_BUILDERS like 'db_endpoint_option' or 'db_endpoint'."""
        if spec.option:
            return f"{spec.database}_{spec.endpoint}_{spec.option}"
        return f"{spec.database}_{spec.endpoint}"

    def _resolve_query_builder(self, spec: EndpointSpec) -> QueryBuilder:
        """Find the query builder callable from QUERY_BUILDERS registry."""
        key = self._query_builder_key(spec)
        qb = QUERY_BUILDERS.get(key)
        if not qb:
            msg = f"No query builder registered for key '{key}'"
            raise ValueError(msg)
        return qb

    def _search_and_merge(
        self,
        row: pd.Series,
        instance: Any,
        spec: EndpointSpec,
        params: dict[str, Any],
        fmt: CrossRefInternalFormat = "dataframe",
    ) -> tuple[pd.DataFrame | list[dict[str, Any]] | dict[str, Any], dict]:
        """Build query from row using the registered query-builder.

        Performs ``fetch_single`` or ``fetch_batch`` and merges the API result with the original row
        (row-expanded).
        """
        metadata = {}
        # Search for an available builder via a search key: {database}_{endpoint}[_option]
        qb = self._resolve_query_builder(spec)

        query_params = qb(row, params)

        graph_like = is_graph_like_enrichment(spec.database, spec.endpoint)
        method_params = {
            "method": spec.endpoint,
            "parse": not graph_like,
            "format": "json" if graph_like else fmt,
        }

        if spec.option:
            method_params["option"] = spec.option

        if isinstance(query_params, dict) or (isinstance(query_params, list) and len(query_params) == 1):
            # If is a single elemnt dict, use the dict itself
            query_params = query_params[0] if isinstance(query_params, list) else query_params
            result, metadata = instance.fetch_single(query=query_params, **method_params)
        elif isinstance(query_params, list) and len(query_params) > 1:
            # If is a list of dicts, use batch
            log.debug(
                "Batch querying %s:%s%s with %s queries and method_params: %s",
                spec.database,
                spec.endpoint,
                "[" + spec.option + "]" if spec.option else "",
                len(query_params),
                method_params,
            )
            result, metadata = instance.fetch_batch(queries=query_params, **method_params)
        # Handle unexpected query_params format
        elif fmt == "dataframe":
            result = pd.DataFrame()
        else:
            result = []

        if graph_like:
            graph_row = build_graph_output_row(
                result,
                row,
                query_params,
                source_database=spec.database,
                source_endpoint=spec.endpoint,
            )
            result = pd.DataFrame([graph_row]) if fmt == "dataframe" else [graph_row]
        else:
            result = attach_source_context(
                result,
                row,
                query_params,
                source_database=spec.database,
                source_endpoint=spec.endpoint,
            )
        return result, add_endpoint_result_metadata(metadata, spec)

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

    def _process_dataframe(
        self,
        df: pd.DataFrame,
        instance: Any,
        spec: EndpointSpec,
        params: dict[str, Any],
        fmt: CrossRefInternalFormat = "dataframe",
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

            # Normalize and filter results: keep only non-empty DataFrames.
            cleaned_results = []
            for result in dfs:
                # If already a DataFrame, ensure it's non-empty and drop duplicate columns.
                if isinstance(result, pd.DataFrame):
                    if result.empty:
                        continue
                    deduped = result.loc[:, ~pd.Index(result.columns).duplicated()]

                    # Drop accidental numeric-only column names like '1','2','3',...
                    cols_to_keep = [c for c in deduped.columns if not str(c).isdigit()]
                    if not cols_to_keep:
                        continue
                    cleaned_results.append(deduped.loc[:, cols_to_keep].reset_index(drop=True))
                    continue

                # If result is a list (likely list of dicts), try to coerce to DataFrame.
                if isinstance(result, list):
                    if not result:
                        continue
                    try:
                        df_result = pd.DataFrame(result)
                    except Exception:  # noqa: BLE001, S112  # skip records that won't coerce to a DataFrame
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
                    except Exception:  # noqa: BLE001, S112  # skip records that won't coerce to a DataFrame
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
        format: CrossRefFormat | str = "dataframe",  # noqa: A002
    ) -> tuple[dict, dict]:
        """Enrich the input DataFrame with cross-references from specified endpoints."""
        internal_format = normalize_crossref_format(format)
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
            log.debug(
                "Processing %s:%s%s...",
                spec.database,
                spec.endpoint,
                "[" + spec.option + "]" if spec.option else "",
            )
            log.info("Checking availability for interface: %s", spec.database)
            self._check_interface_availability(spec.database)
            log.info(
                "Checking required columns for %s:%s%s...",
                spec.database,
                spec.endpoint,
                "[" + spec.option + "]" if spec.option else "",
            )
            self._check_required_columns(df, spec)

            log.info("Building interface for %s...", spec.database)
            instance = self._build_interface(spec.database)
            params = self._prepare_params(spec)
            log.info(
                "Prepared params for %s:%s%s: %s",
                spec.database,
                spec.endpoint,
                "[" + spec.option + "]" if spec.option else "",
                params,
            )

            processed_data, processed_metadata = self._process_dataframe(
                df,
                instance,
                spec,
                params,
                internal_format,
            )
            results.update(
                {f"{spec.database}_{spec.endpoint}{'_' + spec.option if spec.option else ''}": processed_data}
            )
            metadata_key = f"{spec.database}_{spec.endpoint}{'_' + spec.option if spec.option else ''}"
            metadata.update({metadata_key: processed_metadata})

        if internal_format == "dataframe":
            return results, metadata
        if internal_format in ["json", "xml"]:
            return results, metadata
        msg = f"Unsupported format: {internal_format}"
        raise ValueError(msg)
