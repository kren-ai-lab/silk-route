"""Cross-reference enrichment orchestrator."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, cast
from xml.etree.ElementTree import Element, ElementTree, fromstring

import polars as pl

from bioseq_dl.core.metadata import FetchMetadata
from bioseq_dl.core.utils.frames import records_to_frame
from bioseq_dl.core.utils.query_builders import INTERFACE_CLASSES, get_query_builder

if TYPE_CHECKING:
    from collections.abc import Mapping

    from bioseq_dl.core.interfaces.base import BaseAPIInterface
from bioseq_dl.core.utils.xmlhandler import elementtree_to_dataframe
from bioseq_dl.logging import get_logger

log = get_logger("bioseq_dl.interfaces.crossref_enricher")


@dataclass
class EndpointSpec:
    """Declarative specification for a single endpoint.

    Attributes:
        database (str): Database key as used in INTERFACE_CLASSES (e.g., "uniprot", "brenda", "biogrid").
        endpoint (str): Method name to call within the interface (e.g., "search", "getKmValue", "xrefs").
        option (str | None): Optional modifier some interfaces support (e.g., GeneOntology categories).
        params (dict[str, Any] | None): Static/default parameters to merge with query-builder results.
        required_columns (list[str] | None): Column names this endpoint expects in the input row,
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

    One spec per declared option (``[None]`` when an endpoint has none). Shared by
    the CLI and the workflow "all methods" expansion paths.

    Args:
        endpoint_config (Any): Database config dict with an ``endpoints`` mapping.
        database (str): Database key recorded on each produced spec.

    Returns:
        list[EndpointSpec]: One spec per enabled endpoint/option; empty when the
            config is missing or not a dict.

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
        interface_options: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        """Initialize the enricher with the endpoints and fetch settings to use.

        Args:
            endpoint_specs (list[EndpointSpec] | None): Endpoints to query; defaults to empty.
            config_path (str | None): Path to a config file for the interfaces.
            max_workers (int): Number of worker threads used by each interface.
            total_retries (int): Number of retries each interface attempts on failure.
            interface_options (Mapping[str, Mapping[str, Any]] | None): Optional source-specific
                interface constructor kwargs.

        """
        self.endpoint_specs = endpoint_specs or []
        self.config_path = config_path
        self.max_workers = max_workers
        self.total_retries = total_retries
        self.interface_options = {
            str(source): dict(options) for source, options in (interface_options or {}).items()
        }

    def _check_required_columns(self, df: pl.DataFrame, spec: EndpointSpec) -> None:
        """Validate that a spec's required columns are present in the DataFrame.

        Args:
            df (pl.DataFrame): Input data to validate.
            spec (EndpointSpec): Endpoint whose ``required_columns`` are checked.

        Raises:
            ValueError: If any declared required column is missing.

        """
        if not spec.required_columns:
            return
        missing = [c for c in spec.required_columns if c not in df.columns]
        if missing:
            msg = f"Missing required columns for {spec.label}: {missing}"
            raise ValueError(msg)

    def _prepare_params(self, spec: EndpointSpec) -> dict[str, Any]:
        """Prepare base params for an endpoint, including ``option`` if provided.

        Args:
            spec (EndpointSpec): Endpoint whose params are prepared.

        Returns:
            dict[str, Any]: A copy of the spec params, with ``option`` added when set.

        """
        params = dict(spec.params or {})
        if spec.option is not None:
            params["option"] = spec.option

        return params

    def _build_interface(self, database_name: str) -> BaseAPIInterface:
        """Create the interface instance for a database with configured workers and retries.

        Args:
            database_name (str): Database key, must be present in ``INTERFACE_CLASSES``.

        Returns:
            BaseAPIInterface: A new interface instance for the database.

        Raises:
            ValueError: If the database is not supported.

        """
        if database_name not in INTERFACE_CLASSES:
            msg = f"Unsupported database: {database_name}"
            raise ValueError(msg)

        interface_kwargs = dict(self.interface_options.get(database_name, {}))
        return INTERFACE_CLASSES[database_name](
            max_workers=self.max_workers,
            total_retries=self.total_retries,
            **interface_kwargs,
        )

    def _search_and_merge(
        self,
        row: dict[str, Any],
        instance: Any,
        spec: EndpointSpec,
        params: dict[str, Any],
        fmt: Literal["dataframe", "json", "xml"] = "dataframe",
    ) -> tuple[pl.DataFrame | list[dict[str, Any]], dict]:
        """Build a query from a row and fetch its cross-reference result.

        Uses the registered query-builder for the spec, then calls ``fetch_single``
        for a single query or ``fetch_batch`` for multiple.

        Args:
            row (dict[str, Any]): Input row supplying query values.
            instance (Any): Interface instance used to fetch.
            spec (EndpointSpec): Endpoint being queried.
            params (dict[str, Any]): Base params passed to the query-builder.
            fmt (Literal["dataframe", "json", "xml"]): Output format requested.

        Returns:
            tuple[pl.DataFrame | list[dict[str, Any]], dict]: Fetched result and fetch metadata.

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
            result = pl.DataFrame()
        else:
            result = []

        return result, metadata

    @staticmethod
    def _merge_metadata(meta1: dict, meta2: dict) -> dict:
        """Accumulate two same-endpoint fetch metadata dicts via ``FetchMetadata.merge``."""
        return FetchMetadata.from_dict(meta1).merge(FetchMetadata.from_dict(meta2)).to_dict()

    @staticmethod
    def _clean_frame(result: Any) -> pl.DataFrame | None:
        """Coerce a raw row-result to a cleaned DataFrame, or ``None`` to skip it.

        Accepts a DataFrame, list-of-dicts, or single dict; drops accidental
        numeric-only column names.

        Args:
            result (Any): Raw per-row fetch result to coerce.

        Returns:
            pl.DataFrame | None: Cleaned DataFrame, or None for empty or uncoercible results.

        """
        if isinstance(result, pl.DataFrame):
            df_result = result
        elif isinstance(result, list):
            if not result:
                return None
            try:
                df_result = records_to_frame(result)
            except Exception:  # skip records that will not coerce to a DataFrame
                log.exception("Dropping cross-ref result that will not coerce to a DataFrame: %r", result)
                return None
        elif isinstance(result, dict):
            try:
                df_result = records_to_frame(result)
            except Exception:  # skip records that will not coerce to a DataFrame
                log.exception("Dropping cross-ref result that will not coerce to a DataFrame: %r", result)
                return None
        else:
            log.debug("Skipping unsupported cross-ref result type: %s", type(result).__name__)
            return None

        if df_result.is_empty():
            return None
        # Drop accidental numeric-only column names like '1','2','3',...
        cols_to_keep = [c for c in df_result.columns if not str(c).isdigit()]
        if not cols_to_keep:
            return None
        return df_result.select(cols_to_keep)

    def _process_dataframe(
        self,
        df: pl.DataFrame,
        instance: Any,
        spec: EndpointSpec,
        params: dict[str, Any],
        fmt: Literal["dataframe", "json", "xml"] = "dataframe",
    ) -> tuple[pl.DataFrame | list | ElementTree[Element[str] | None], dict]:
        """Apply search-then-merge for every row and combine all row-expansions.

        Aggregates per-row results into the requested format and records per-row
        outcomes under the metadata ``extra`` block.

        Args:
            df (pl.DataFrame): Input rows to enrich.
            instance (Any): Interface instance used to fetch.
            spec (EndpointSpec): Endpoint being queried.
            params (dict[str, Any]): Base params passed to the query-builder.
            fmt (Literal["dataframe", "json", "xml"]): Output format requested.

        Returns:
            tuple[pl.DataFrame | list | ElementTree[Element[str] | None], dict]: Combined
                result in the requested format and merged fetch metadata.

        Raises:
            ValueError: If ``fmt`` is not a supported format.

        """
        # Apply row-wise; collect per-row DataFrames
        all_metadata = {}
        all_results = []
        # Per-input-row enrichment outcome: lets callers see exactly which rows
        # came back empty or failed (invisible in the merged aggregate alone).
        per_row: list[dict[str, Any]] = []

        for idx, row in enumerate(df.iter_rows(named=True)):
            result, metadata = self._search_and_merge(row, instance, spec, params, fmt)
            all_results.append(result)
            all_metadata = self._merge_metadata(all_metadata, metadata)
            failed = metadata.get("failed", {}) if isinstance(metadata, dict) else {}
            data_info = metadata.get("data_info", {}) if isinstance(metadata, dict) else {}
            per_row.append(
                {
                    "row": idx,
                    "found": data_info.get("total_entries", 0),
                    "failed_ids": failed.get("ids", []),
                    "failed_reasons": failed.get("reasons", []),
                }
            )

        # Attach per-row outcomes under the source-specific extra block.
        all_metadata.setdefault("extra", {})["per_row"] = per_row

        if fmt == "dataframe":
            # Unpack (df, metadata) tuples; metadata currently unused
            dfs = [res[0] if isinstance(res, tuple) else res for res in all_results]
            cleaned_results = [
                cleaned for result in dfs if (cleaned := self._clean_frame(result)) is not None
            ]
            if not cleaned_results:
                return pl.DataFrame(), all_metadata
            return pl.concat(cleaned_results, how="diagonal_relaxed"), all_metadata
        if fmt == "json":
            cleaned_results = []
            for raw in all_results:
                item = raw[0] if isinstance(raw, tuple) else raw
                if isinstance(item, list):
                    cleaned_results.extend(item)
            return cleaned_results, all_metadata
        if fmt == "xml":
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
        """Enrich the input data with cross-references from the configured endpoints.

        Accepts the input as a DataFrame, list of dicts, dict, JSON string, or
        ElementTree and processes each endpoint spec in turn.

        Args:
            data (Any): Input data to enrich (DataFrame, list, dict, JSON str, or ElementTree).
            format (Literal["dataframe", "json", "xml"]): Output format for each endpoint result.

        Returns:
            tuple[dict, dict]: Results keyed by ``spec.key`` and metadata keyed by ``spec.key``.

        Raises:
            TypeError: If ``data`` is not a supported input type.
            ValueError: If ``format`` is not supported.

        """
        # For an easier handling, convert input data to DataFrame if needed
        if isinstance(data, list):
            df = records_to_frame(data)
        elif isinstance(data, dict):
            df = pl.DataFrame(data, strict=False, infer_schema_length=None)
        elif isinstance(data, pl.DataFrame):
            df = data
        elif isinstance(data, ElementTree):
            df = elementtree_to_dataframe(tree=data)
        elif isinstance(data, str):
            df = records_to_frame(json.loads(data))
        else:
            msg = "Input data must be a Polars DataFrame, list of dicts, or dict."
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
