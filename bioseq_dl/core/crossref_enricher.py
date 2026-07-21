"""Cross-reference enrichment orchestrator."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, cast
from xml.etree.ElementTree import Element, ElementTree, fromstring, tostring

import polars as pl

from bioseq_dl.core.metadata import FetchMetadata
from bioseq_dl.core.utils.frames import records_to_frame
from bioseq_dl.core.utils.query_builders import INTERFACE_CLASSES, get_query_builder

if TYPE_CHECKING:
    from collections.abc import Mapping

    from bioseq_dl.core.interfaces.base import BaseAPIInterface
from bioseq_dl.core.utils.xmlhandler import dict_to_elementtree, elementtree_to_dataframe
from bioseq_dl.logging import get_logger

log = get_logger("bioseq_dl.interfaces.crossref_enricher")

PROVENANCE_COLUMNS = (
    "source_accession",
    "source_protein_name",
    "source_organism_id",
    "source_query",
    "source_database",
    "source_endpoint",
)
PROVENANCE_SCHEMA = dict.fromkeys(PROVENANCE_COLUMNS, pl.String)
GRAPH_JSON_COLUMN = "graph_json"
GRAPH_LIKE_ENRICHMENT_OUTPUTS = {
    "pathwaycommons_fetch",
    "pathwaycommons_neighborhood",
}
GRAPH_OUTPUT_NOTE = (
    "graph_json is intentionally preserved as raw graph data until workflow export "
    "writes the external JSON artifact."
)
EMPTY_GRAPH_COLLECTION_KEYS = ("@graph", "graph", "searchHit")


def empty_provenance_frame() -> pl.DataFrame:
    """Return an empty frame with the stable enrichment provenance schema."""
    return pl.DataFrame(schema=PROVENANCE_SCHEMA)


def _is_missing_value(value: Any) -> bool:
    """Return whether a source-row value should be treated as absent."""
    return value is None or (isinstance(value, float) and math.isnan(value))


def _stable_object_text(value: Any) -> str:
    """Return a stable string fallback for non-JSON-native objects."""
    try:
        return str(value)
    except Exception:  # noqa: BLE001  # defensive fallback for user objects with broken __str__
        return repr(value)


def _canonical_json_sort_key(value: Any) -> str:
    """Return a string key for sorting canonical JSON values."""
    return canonical_json_text(value) or "null"


def _canonical_mapping_key(key: Any) -> str:
    """Return the string key used for deterministic JSON mapping output."""
    if isinstance(key, str):
        return key
    return _stable_object_text(key)


def _dedupe_mapping_key(key: str, seen: dict[str, int]) -> str:
    """Return ``key`` or a deterministic suffixed form when stringified keys collide."""
    seen_count = seen.get(key, 0) + 1
    seen[key] = seen_count
    if seen_count == 1:
        return key
    return f"{key}#{seen_count}"


def _canonical_json_value(value: Any) -> Any:
    """Return a JSON-native value with deterministic mapping keys.

    Mapping keys are normalized with ``str(key)`` for non-string keys, sorted by
    that normalized key plus the original key type/name, and duplicate normalized
    keys are preserved with ``#2``, ``#3`` suffixes.
    """
    if value is None:
        return None
    if isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else _stable_object_text(value)
    if isinstance(value, MappingABC):
        sorted_items = sorted(
            value.items(),
            key=lambda item: (
                _canonical_mapping_key(item[0]),
                type(item[0]).__name__,
                _stable_object_text(item[0]),
            ),
        )
        seen: dict[str, int] = {}
        return {
            _dedupe_mapping_key(_canonical_mapping_key(key), seen): _canonical_json_value(item_value)
            for key, item_value in sorted_items
        }
    if isinstance(value, list | tuple):
        return [_canonical_json_value(item) for item in value]
    if isinstance(value, set | frozenset):
        normalized_items = [_canonical_json_value(item) for item in value]
        return sorted(normalized_items, key=_canonical_json_sort_key)
    return _stable_object_text(value)


def canonical_json_text(value: Any) -> str | None:
    """Serialize ordinary Python values to compact deterministic JSON text.

    Returns ``None`` only for an actual ``None`` input. Mappings are recursively
    normalized to string keys before sorting, so mixed key types cannot make
    ``json.dumps(sort_keys=True)`` fail.
    """
    if value is None:
        return None
    return json.dumps(
        _canonical_json_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_stable_object_text,
    )


def _stable_text(value: Any) -> str | None:
    """Normalize a provenance scalar to stable string/null form."""
    if _is_missing_value(value):
        return None
    if isinstance(value, MappingABC | list | tuple | set | frozenset):
        return canonical_json_text(value)
    return str(value)


def serialize_source_query(value: Any) -> str | None:
    """Serialize the resolved enrichment query deterministically for tabular output."""
    if _is_missing_value(value):
        return None
    return canonical_json_text(value)


def get_enrichment_output_key(database_name: str, endpoint_name: str) -> str:
    """Return the stable output key used to classify enrichment results."""
    return f"{database_name}_{endpoint_name}"


def is_graph_like_enrichment(database_name: str, endpoint_name: str) -> bool:
    """Return whether an enrichment endpoint must preserve a raw graph payload."""
    return get_enrichment_output_key(database_name, endpoint_name) in GRAPH_LIKE_ENRICHMENT_OUTPUTS


@dataclass(frozen=True)
class NormalizedGraphPayload:
    """JSON-native graph payload plus an optional normalization error."""

    payload: Any = None
    error: str | None = None


def _decode_graph_payload_text(value: str | bytes) -> NormalizedGraphPayload:
    """Decode and parse a text/bytes graph payload as JSON."""
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError as exc:
            return NormalizedGraphPayload(error=f"invalid_utf8_graph_payload: {exc}")
    try:
        return NormalizedGraphPayload(payload=json.loads(value))
    except json.JSONDecodeError as exc:
        return NormalizedGraphPayload(error=f"malformed_graph_json: {exc}")


def normalize_graph_payload(raw_result: Any) -> NormalizedGraphPayload:
    """Return a JSON-native graph payload or a concise normalization error."""
    if isinstance(raw_result, pl.DataFrame):
        return NormalizedGraphPayload(payload=raw_result.to_dicts())
    if isinstance(raw_result, str | bytes):
        return _decode_graph_payload_text(raw_result)
    if raw_result is None or (isinstance(raw_result, dict | list) and not raw_result):
        return NormalizedGraphPayload(payload=[])
    return NormalizedGraphPayload(payload=_canonical_json_value(raw_result))


def is_empty_graph_payload(graph_payload: Any) -> bool:
    """Return whether a graph payload is an empty graph response."""
    if graph_payload is None:
        return True
    if isinstance(graph_payload, list):
        return not graph_payload
    if not isinstance(graph_payload, dict):
        return False
    if not graph_payload:
        return True
    for key in EMPTY_GRAPH_COLLECTION_KEYS:
        value = graph_payload.get(key)
        if isinstance(value, list):
            return not value
    nodes = graph_payload.get("nodes")
    edges = graph_payload.get("edges")
    if isinstance(nodes, list) and isinstance(edges, list):
        return not nodes and not edges
    return False


def count_graph_records(graph_payload: Any) -> int:
    """Count graph records using recognized graph collections when present."""
    if isinstance(graph_payload, dict):
        graph_records = graph_payload.get("@graph")
        if isinstance(graph_records, list):
            return len(graph_records)
        nodes = graph_payload.get("nodes")
        edges = graph_payload.get("edges")
        if isinstance(nodes, list) and isinstance(edges, list):
            return len(nodes) + len(edges)
        return 1 if graph_payload else 0
    if isinstance(graph_payload, list):
        return len(graph_payload)
    return 0 if graph_payload is None else 1


def build_graph_output_row(
    graph_payload: Any,
    row: dict[str, Any],
    source_query: Any,
    *,
    source_database: str,
    source_endpoint: str,
) -> dict[str, Any]:
    """Build one provenance row containing a deterministic raw graph payload."""
    graph_json = canonical_json_text(graph_payload) or "null"
    return {
        **build_source_context(
            row,
            source_query,
            source_database=source_database,
            source_endpoint=source_endpoint,
        ),
        "graph_format": "json",
        "graph_record_count": count_graph_records(graph_payload),
        GRAPH_JSON_COLUMN: graph_json,
    }


def add_graph_endpoint_metadata(metadata: dict, spec: EndpointSpec | None) -> dict:
    """Annotate graph-like endpoint metadata with its tabular graph contract."""
    if spec is None:
        return metadata
    if not is_graph_like_enrichment(spec.database, spec.endpoint):
        return metadata
    metadata.update(
        {
            "output_kind": "raw_graph",
            "graph_serialization": "json",
            "graph_tabularization": "one_row_per_source",
            "note": GRAPH_OUTPUT_NOTE,
        }
    )
    return metadata


def build_graph_failure_metadata(query: Any, reason: str, error: str | None = None) -> dict:
    """Return fetch metadata for a graph request that could not produce a graph row."""
    metadata = FetchMetadata()
    metadata.failed.add(serialize_source_query(query) or "graph_query", query, reason)
    metadata.data_info = {"total_entries": 0, "data_type": "graph", "columns": []}
    if error:
        metadata.extra["graph_payload_error"] = error
    return metadata.to_dict()


def _first_present(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """Return the first non-missing value found under ``keys``."""
    for key in keys:
        value = row.get(key)
        if not _is_missing_value(value):
            return value
    return None


def _organism_taxon_id(row: dict[str, Any]) -> Any:
    """Return a nested or normalized taxon id without using organism names."""
    organism = row.get("organism")
    if isinstance(organism, dict):
        for key in ("taxonId", "taxon_id", "organism_id"):
            value = organism.get(key)
            if not _is_missing_value(value):
                return value
    return _first_present(row, ("organism.taxonId",))


def build_source_context(
    row: dict[str, Any],
    source_query: Any,
    *,
    source_database: str,
    source_endpoint: str,
) -> dict[str, str | None]:
    """Return normalized original-record and request provenance."""
    return {
        "source_accession": _stable_text(
            _first_present(row, ("source_accession", "accession", "Entry", "primaryAccession"))
        ),
        "source_protein_name": _stable_text(
            _first_present(row, ("source_protein_name", "protein_name", "Protein names"))
        ),
        "source_organism_id": _stable_text(_source_organism_id(row)),
        "source_query": serialize_source_query(source_query),
        "source_database": str(source_database),
        "source_endpoint": str(source_endpoint),
    }


def _payload_key_for(record: dict[str, Any], key: str) -> str:
    """Return a deterministic non-conflicting payload key for a reserved column."""
    candidate = f"payload_{key}"
    if candidate not in record:
        return candidate
    index = 2
    while f"payload_{index}_{key}" in record:
        index += 1
    return f"payload_{index}_{key}"


def preserve_payload_collisions(
    record: dict[str, Any],
    context: dict[str, str | None],
) -> dict[str, Any]:
    """Move API payload values from reserved provenance names to ``payload_*`` names."""
    clean_record = dict(record)
    for column in PROVENANCE_COLUMNS:
        if column not in clean_record:
            continue
        payload_value = _stable_text(clean_record[column])
        if payload_value == context.get(column):
            clean_record.pop(column)
            continue
        payload_key = _payload_key_for(clean_record, column)
        clean_record[payload_key] = payload_value
        clean_record.pop(column)
    return clean_record


def _source_organism_id(row: dict[str, Any]) -> Any:
    """Return source organism id using the reviewed precedence."""
    value = _first_present(row, ("source_organism_id", "organism_id"))
    if not _is_missing_value(value):
        return value
    return _organism_taxon_id(row)


def _with_provenance_record(record: dict[str, Any], context: dict[str, str | None]) -> dict[str, Any]:
    """Return one API payload record with authoritative provenance columns first."""
    payload = preserve_payload_collisions(record, context)
    return {**context, **payload}


def order_provenance_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Place provenance columns first while preserving payload column order."""
    provenance = [column for column in PROVENANCE_COLUMNS if column in df.columns]
    payload = [column for column in df.columns if column not in PROVENANCE_COLUMNS]
    ordered = df.select(provenance + payload)
    return ordered.with_columns(pl.col(column).cast(pl.String) for column in provenance)


def attach_source_context(
    result: Any,
    row: dict[str, Any],
    source_query: Any,
    *,
    source_database: str,
    source_endpoint: str,
) -> Any:
    """Attach source-row and request provenance to non-empty enrichment results."""
    context = build_source_context(
        row,
        source_query,
        source_database=source_database,
        source_endpoint=source_endpoint,
    )

    if isinstance(result, pl.DataFrame):
        if result.is_empty():
            return empty_provenance_frame()
        records = [_with_provenance_record(record, context) for record in result.to_dicts()]
        return order_provenance_columns(records_to_frame(records))
    if isinstance(result, list):
        if not result:
            return []
        return [_with_provenance_record(item, context) if isinstance(item, dict) else item for item in result]
    if isinstance(result, dict):
        if not result:
            return {}
        return _with_provenance_record(result, context)
    return result


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
    ) -> tuple[pl.DataFrame | list[dict[str, Any]] | str, dict]:
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
        if not query_params:
            if fmt == "dataframe":
                return empty_provenance_frame(), metadata
            return [], metadata

        graph_like = is_graph_like_enrichment(spec.database, spec.endpoint)
        method_params = {
            "method": spec.endpoint,
            "parse": not graph_like,
            "format": "json" if graph_like else fmt,
        }

        if spec.option:
            method_params["option"] = spec.option

        try:
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
                result = empty_provenance_frame()
            else:
                result = []
        except Exception as exc:  # graph fetches must preserve workflow execution
            if not graph_like:
                raise
            log.warning("Graph payload fetch failed for %s: %s", spec.label, exc)
            metadata = build_graph_failure_metadata(query_params, "request_error", str(exc))
            if fmt == "dataframe":
                return empty_provenance_frame(), metadata
            return [], metadata

        if graph_like:
            normalized_graph = normalize_graph_payload(result)
            if normalized_graph.error:
                metadata = self._merge_metadata(
                    metadata,
                    build_graph_failure_metadata(query_params, "malformed_result", normalized_graph.error),
                )
                return self._empty_graph_result(fmt), metadata
            if is_empty_graph_payload(normalized_graph.payload):
                return self._empty_graph_result(fmt), metadata
            graph_row = build_graph_output_row(
                normalized_graph.payload,
                row,
                query_params,
                source_database=spec.database,
                source_endpoint=spec.endpoint,
            )
            result = self._graph_row_result(graph_row, fmt)
        else:
            result = attach_source_context(
                result,
                row,
                query_params,
                source_database=spec.database,
                source_endpoint=spec.endpoint,
            )
        return result, metadata

    @staticmethod
    def _empty_graph_result(fmt: str) -> pl.DataFrame | str | list:
        """Return the empty per-row graph result matching the requested output format."""
        if fmt == "dataframe":
            return empty_provenance_frame()
        if fmt == "xml":
            return "<results></results>"
        return []

    @staticmethod
    def _graph_row_result(graph_row: dict, fmt: str) -> pl.DataFrame | str | list:
        """Serialize a graph row into the requested format.

        XML must be a string, not a list: `_process_dataframe` feeds each result to
        `fromstring`.
        """
        if fmt == "dataframe":
            return records_to_frame([graph_row])
        if fmt == "xml":
            return tostring(dict_to_elementtree([graph_row]).getroot(), encoding="unicode")
        return [graph_row]

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
        all_metadata = add_graph_endpoint_metadata(all_metadata, spec)

        if fmt == "dataframe":
            # Unpack (df, metadata) tuples; metadata currently unused
            dfs = [res[0] if isinstance(res, tuple) else res for res in all_results]
            cleaned_results = [
                cleaned for result in dfs if (cleaned := self._clean_frame(result)) is not None
            ]
            if not cleaned_results:
                all_metadata.setdefault("extra", {})["output_row_count"] = 0
                return empty_provenance_frame(), all_metadata
            combined = order_provenance_columns(pl.concat(cleaned_results, how="diagonal_relaxed"))
            all_metadata.setdefault("extra", {})["output_row_count"] = combined.height
            return combined, all_metadata
        if fmt == "json":
            cleaned_results = []
            for raw in all_results:
                item = raw[0] if isinstance(raw, tuple) else raw
                if isinstance(item, list):
                    cleaned_results.extend(item)
                elif isinstance(item, dict) and item:
                    cleaned_results.append(item)
            all_metadata.setdefault("extra", {})["output_row_count"] = len(cleaned_results)
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
