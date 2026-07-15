"""High-level multi-step download workflow orchestrator."""

from __future__ import annotations

import contextlib
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal, cast

import polars as pl

from bioseq_dl import ChEMBLInterface, UniprotInterface
from bioseq_dl.core.crossref_enricher import CrossRefEnricher, EndpointSpec
from bioseq_dl.core.export import normalize_parse_format
from bioseq_dl.core.utils.crossref_enrichment import normalize_crossref_fields, run_crossref_enrichment
from bioseq_dl.core.utils.frames import records_to_frame
from bioseq_dl.logging import get_logger

from .chebi_execution import execute_chebi_request_plan
from .chebi_query_parser import is_chebi_prefixed_query, parse_chebi_query_builder_string
from .chembl_query_parser import (
    get_chembl_prefixed_query_resource,
    is_chembl_prefixed_query,
    parse_chembl_query_builder_string,
)
from .pubchem_execution import execute_pubchem_request_plan
from .pubchem_query_parser import is_pubchem_prefixed_query, parse_pubchem_query_builder_string
from .query_interpreter import (
    UniProtQueryInterpreter,
    build_default_chembl_interpreter,
    build_default_uniprot_interpreter,
    normalize_standard_units,
)

if TYPE_CHECKING:
    import logging
    from collections.abc import Iterable

log = get_logger("bioseq_dl.core.workflow.main")

# Split large ChEMBL ID lists into chunks of this size to keep UniProt queries short.
CHEMBL_ID_CHUNK_SIZE = 100
PROTEIN_CHEMBL_QUERY_ERROR = (
    "ChEMBL-prefixed queries are not valid for protein workflows. "
    "Use a compound workflow or a protein-ligand interaction workflow."
)
PPI_CHEMBL_QUERY_ERROR = (
    "ChEMBL-prefixed queries are not valid for protein-protein interaction workflows. "
    "Use a protein-ligand interaction workflow for ChEMBL target or activity queries."
)
PROTEIN_COMPOUND_SOURCE_QUERY_ERROR = (
    "PubChem- and ChEBI-prefixed queries are not valid for protein workflows. "
    "Use a compound workflow for PubChem or ChEBI queries."
)
INTERACTION_COMPOUND_SOURCE_QUERY_ERROR = (
    "PubChem- and ChEBI-prefixed queries are not valid for interaction workflows. "
    "Use a compound workflow, or use ChEMBL for protein-ligand interaction workflows."
)
COMPOUND_UNSUPPORTED_CHEMBL_RESOURCE_ERROR = (
    "ChEMBL resource '{resource}' is not valid for compound workflows. "
    "Use chembl.molecule or chembl.activity for compound workflows, or use a "
    "protein-ligand interaction workflow for target, assay, or cell-line queries."
)


def calculate_enrichment_execution_time(enrichment_metadata: object) -> float:
    """Return the total execution time reported by enrichment metadata.

    Each endpoint's metadata records ``started_at`` / ``finished_at`` ISO-8601
    timestamps rather than a precomputed duration, so the per-endpoint elapsed
    time is derived here and summed.

    Args:
        enrichment_metadata (object): Mapping of endpoint label to metadata dict;
            non-dict values yield ``0.0``.

    Returns:
        float: Sum of per-endpoint elapsed seconds.

    """
    if not isinstance(enrichment_metadata, dict):
        return 0.0

    total = 0.0
    for metadata in enrichment_metadata.values():
        if not isinstance(metadata, dict):
            continue
        total += _elapsed_seconds(metadata.get("started_at"), metadata.get("finished_at"))
    return total


def _elapsed_seconds(started_at: object, finished_at: object) -> float:
    """Seconds between two ISO-8601 timestamps; ``0.0`` if either is missing/invalid."""
    if not isinstance(started_at, str) or not isinstance(finished_at, str):
        return 0.0
    try:
        delta = datetime.fromisoformat(finished_at) - datetime.fromisoformat(started_at)
    except ValueError:
        return 0.0
    return max(delta.total_seconds(), 0.0)


# Maps each modality to the result key its primary payload lives under.
_MODALITY_RESULT_KEY = {"protein": "uniprot", "compound": "chembl", "interaction": "data"}
_COMPOUND_RESULT_KEYS = ("chembl", "pubchem", "chebi")


def _apply_label(value: Any, label: str) -> Any:
    """Tag a result value with a ``_label`` and return the labeled value.

    DataFrames get a new ``_label`` column (preserving any existing one as
    ``_label_original``); list rows / dicts get ``_label`` via ``setdefault``;
    scalars are replaced wholesale by ``{"_label": label}``.

    Args:
        value (Any): Result value to label (DataFrame, list, dict, or scalar).
        label (str): Label to attach.

    Returns:
        Any: The labeled value.

    """
    if isinstance(value, pl.DataFrame):
        if "_label" in value.columns:
            value = value.rename({"_label": "_label_original"})
        return value.with_columns(pl.lit(label).alias("_label"))
    if isinstance(value, list):
        for row in value:
            if isinstance(row, dict):
                row.setdefault("_label", label)
        return value
    if isinstance(value, dict):
        value.setdefault("_label", label)
        return value
    return {"_label": label}


def attach_label_to_part(part_data: dict, label: str, modality: str) -> dict:
    """Attach a query-composition label to a workflow result part.

    Locates the part's primary payload by modality, labels it, and (for the
    compound modality) also labels any accompanying ``uniprot`` payload.

    Args:
        part_data (dict): A single workflow result part keyed by database.
        label (str): Label to attach to each result row.
        modality (str): Modality selecting the primary payload key
            ('protein', 'compound', 'interaction').

    Returns:
        dict: Labeled payload(s), or an empty dict if nothing applicable was found.

    """
    if not isinstance(part_data, dict):
        return {}
    if modality == "compound":
        labeled = {
            key: _apply_label(part_data[key], label)
            for key in _COMPOUND_RESULT_KEYS
            if part_data.get(key) is not None
        }
        if part_data.get("uniprot") is not None:
            labeled["uniprot"] = _apply_label(part_data["uniprot"], label)
        return labeled

    key = _MODALITY_RESULT_KEY.get(modality)
    if key is None or part_data.get(key) is None:
        return {}

    return {key: _apply_label(part_data[key], label)}


def activity_filter_metadata(activity_filter: dict) -> dict:
    """Return a compact activity filter description for workflow metadata.

    Args:
        activity_filter (dict): ChEMBL activity filter spec.

    Returns:
        dict: Selected filter fields; ``standard_value`` is included only when set.

    """
    metadata = {
        "standard_type": activity_filter.get("standard_type"),
        "standard_value_min": activity_filter.get("standard_value_min"),
        "standard_value_max": activity_filter.get("standard_value_max"),
        "standard_units": activity_filter.get("standard_units"),
    }
    if activity_filter.get("standard_value") is not None:
        metadata["standard_value"] = activity_filter.get("standard_value")
    return metadata


def filter_chembl_activity_dataframe(df: pl.DataFrame, activity_filter: dict) -> tuple[pl.DataFrame, dict]:
    """Apply a defensive ChEMBL activity filter to a DataFrame without changing column types.

    Filters rows by ``standard_type`` and numeric ``standard_value`` (exact value
    or inclusive/exclusive min/max bounds). Missing required columns yield an empty
    frame with an explanatory ``reason`` in the metadata.

    Args:
        df (pl.DataFrame): Rows to filter.
        activity_filter (dict): ChEMBL activity filter spec.

    Returns:
        tuple[pl.DataFrame, dict]: Filtered frame and filter metadata (row counts).

    """
    initial_rows = df.height
    if df.is_empty():
        return df, {
            "applied": True,
            "initial_rows": initial_rows,
            "filtered_rows": 0,
            "removed_rows": 0,
        }

    if "standard_type" not in df.columns or "standard_value" not in df.columns:
        return df.clear(), {
            "applied": True,
            "initial_rows": initial_rows,
            "filtered_rows": 0,
            "removed_rows": initial_rows,
            "reason": "missing_standard_type_or_standard_value",
        }

    standard_type = str(activity_filter.get("standard_type", "")).upper()
    type_cond = pl.col("standard_type").cast(pl.String).str.to_uppercase() == standard_type
    standard_units = activity_filter.get("standard_units")
    if standard_units is not None and "standard_units" not in df.columns:
        return df.clear(), {
            "applied": True,
            "initial_rows": initial_rows,
            "filtered_rows": 0,
            "removed_rows": initial_rows,
            "reason": "missing_standard_units",
            "requested_standard_units": standard_units,
        }

    units_cond = pl.lit(value=True)
    if standard_units is not None:
        normalized_units = normalize_standard_units(str(standard_units)).lower()
        units_cond = (
            pl.col("standard_units")
            .cast(pl.String)
            .str.strip_chars()
            .str.replace_all("Âµ", "u")
            .str.replace_all("Î¼", "u")
            .str.replace_all("µ", "u")
            .str.replace_all("μ", "u")
            .str.to_lowercase()
            .eq(normalized_units)
            .fill_null(value=False)
        )

    values = pl.col("standard_value").cast(pl.Float64, strict=False)
    value_cond = values.is_not_null()

    exact_value = activity_filter.get("standard_value")
    if exact_value is not None:
        value_cond &= values == exact_value
    else:
        min_value = activity_filter.get("standard_value_min")
        max_value = activity_filter.get("standard_value_max")
        if min_value is not None:
            if activity_filter.get("standard_value_min_inclusive"):
                value_cond &= values >= min_value
            else:
                value_cond &= values > min_value
        if max_value is not None:
            if activity_filter.get("standard_value_max_inclusive"):
                value_cond &= values <= max_value
            else:
                value_cond &= values < max_value

    filtered = df.filter(type_cond & value_cond & units_cond)
    filtered_rows = filtered.height
    return filtered, {
        "applied": True,
        "initial_rows": initial_rows,
        "filtered_rows": filtered_rows,
        "removed_rows": initial_rows - filtered_rows,
    }


def filter_chembl_activity_result(result: Any, activity_filter: dict | None) -> tuple[Any, dict]:
    """Apply a defensive ChEMBL activity filter to supported workflow result shapes.

    DataFrame, list-of-records, and single-dict results are filtered via
    ``filter_chembl_activity_dataframe`` and returned in their original shape;
    other types pass through unfiltered.

    Args:
        result (Any): Workflow result (DataFrame, list, dict, or other).
        activity_filter (dict | None): Filter spec; falsy disables filtering.

    Returns:
        tuple[Any, dict]: Filtered result (same shape as input) and filter metadata.

    """
    if not activity_filter:
        return result, {"applied": False}

    if isinstance(result, pl.DataFrame):
        return filter_chembl_activity_dataframe(result, activity_filter)

    if isinstance(result, list):
        df = records_to_frame(result)
        filtered, metadata = filter_chembl_activity_dataframe(df, activity_filter)
        return filtered.to_dicts(), metadata

    if isinstance(result, dict):
        df = records_to_frame(result)
        filtered, metadata = filter_chembl_activity_dataframe(df, activity_filter)
        if filtered.is_empty():
            return {}, metadata
        return filtered.row(0, named=True), metadata

    return result, {
        "applied": False,
        "reason": f"unsupported_result_type:{type(result).__name__}",
    }


def normalize_chembl_pages_to_fetch(value: int | None) -> int:
    """Normalize a ChEMBL workflow page cap.

    Args:
        value (int | None): Requested page cap; ``None`` means "all pages".

    Returns:
        int: ``-1`` for all pages, otherwise a positive page count.

    Raises:
        TypeError: If ``value`` is a bool.
        ValueError: If ``value`` is not coercible to a valid page count
            (must be ``-1`` or a positive integer).

    """
    if value is None:
        return -1
    if isinstance(value, bool):
        msg = "chembl_pages_to_fetch must be -1 or a positive integer."
        raise TypeError(msg)
    try:
        pages_to_fetch = int(value)
    except (TypeError, ValueError) as exc:
        msg = "chembl_pages_to_fetch must be -1 or a positive integer."
        raise ValueError(msg) from exc
    if pages_to_fetch == 0 or pages_to_fetch < -1:
        msg = "chembl_pages_to_fetch must be -1 or a positive integer."
        raise ValueError(msg)
    return pages_to_fetch


def resolve_chembl_search_type_from_query(query: str, default_search_type: str | None) -> str:
    """Return the ChEMBL resource/search type for a workflow query."""
    resource = get_chembl_prefixed_query_resource(query)
    if resource:
        return resource
    return default_search_type or "activity"


def validate_compound_chembl_query_resource(query: str) -> None:
    """Validate ChEMBL-prefixed query resources for compound workflows."""
    resource = get_chembl_prefixed_query_resource(query)
    if resource is None:
        return
    if resource in {"molecule", "activity"}:
        return
    msg = COMPOUND_UNSUPPORTED_CHEMBL_RESOURCE_ERROR.format(resource=resource)
    raise ValueError(msg)


def build_chembl_query_structure(query: str) -> dict[str, object] | None:
    """Parse a ChEMBL-prefixed query string, if one is present."""
    if not is_chembl_prefixed_query(query):
        return None
    return parse_chembl_query_builder_string(query)


def is_pubchem_or_chebi_prefixed_query(query: str | None) -> bool:
    """Return whether a query uses a PubChem or ChEBI workflow prefix."""
    if query is None:
        return False
    return is_pubchem_prefixed_query(query) or is_chebi_prefixed_query(query)


def build_pubchem_request_plan(query: str) -> dict[str, object] | None:
    """Parse a PubChem-prefixed query string, if one is present."""
    if not is_pubchem_prefixed_query(query):
        return None
    return parse_pubchem_query_builder_string(query)


def build_chebi_request_plan(query: str) -> dict[str, object] | None:
    """Parse a ChEBI-prefixed query string, if one is present."""
    if not is_chebi_prefixed_query(query):
        return None
    return parse_chebi_query_builder_string(query)


def merge_pair(existing: Any, new: Any) -> Any:
    """Merge two workflow result values: concat DataFrames, extend lists, else pair them.

    Dicts and ElementTree elements have no in-place merge, so they (and any other
    mismatched types) collapse into a ``[existing, new]`` list.

    Args:
        existing (Any): Current value.
        new (Any): Value to merge in.

    Returns:
        Any: Merged value (concatenated frame, extended list, or a two-element list).

    """
    if isinstance(existing, pl.DataFrame) and isinstance(new, pl.DataFrame):
        return pl.concat([existing, new], how="diagonal_relaxed")
    if isinstance(existing, list) and isinstance(new, list):
        existing.extend(new)
        return existing
    return [existing, new]


def merge_into_dict(target: dict, key: str, value: Any) -> None:
    """Insert ``value`` at ``key``, merging via ``merge_pair`` when the key already exists."""
    target[key] = merge_pair(target[key], value) if key in target else value


def merge_enrichment_data(existing: list[Any], new: Any) -> list[Any]:
    """Merge query-composition enrichment result parts by endpoint label.

    For each endpoint in ``new``, merges into the existing item carrying that
    endpoint (via ``merge_pair``) or appends a new single-key entry.

    Args:
        existing (list[Any]): Accumulated enrichment items, each a dict keyed by endpoint.
        new (Any): New enrichment part; only dicts are merged, others are ignored.

    Returns:
        list[Any]: The updated ``existing`` list.

    """
    if isinstance(new, dict):
        for db_ep, db_data in new.items():
            if db_data is None:
                continue
            existing_item = next((item for item in existing if db_ep in item), None)
            if existing_item is not None:
                existing_item[db_ep] = merge_pair(existing_item[db_ep], db_data)
            else:
                existing.append({db_ep: db_data})
    return existing


class MainWorkflow:
    """High-level workflow orchestrator for biological modalities and workflow modes.

    Modes:
      - query_first(query, ...): interpret user-friendly queries, fetch from UniProt, optional enrichment.
      - query_composition(queries_with_labels, ...): run multiple queries and tag results with labels.

    By default this class will instantiate reasonable components so the caller does not need
    to provide any dependencies. All I/O (saving to disk, printing) is left to the caller.
    Optional dependency injection is supported via constructor arguments.
    """

    def __init__(
        self,
        interpreter: UniProtQueryInterpreter | None = None,
        uniprot_interface: UniprotInterface | None = None,
        enricher: CrossRefEnricher | None = None,
        default_export_format: str = "csv",
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize MainWorkflow with optional dependency injection.

        Any dependency left as ``None`` is replaced by a sensible default.

        Args:
            interpreter (UniProtQueryInterpreter | None): UniProt query interpreter.
            uniprot_interface (UniprotInterface | None): UniProt API client.
            enricher (CrossRefEnricher | None): Cross-reference enricher.
            default_export_format (str): Export format used when none is supplied per call.
            logger (logging.Logger | None): Logger; falls back to the module logger.

        """
        # Instantiate sensible defaults if not provided
        self.interpreter = interpreter or build_default_uniprot_interpreter()
        self.uniprot = uniprot_interface or UniprotInterface()
        self.enricher = enricher or CrossRefEnricher(endpoint_specs=[])
        self.default_export_format = default_export_format
        self.log = logger or log

        with contextlib.suppress(Exception):
            self.log.debug(
                "MainWorkflow initialized (interpreter=%s, uniprot=%s, enricher=%s, "
                "default_export_format=%s)",
                type(self.interpreter).__name__,
                type(self.uniprot).__name__,
                type(self.enricher).__name__,
                self.default_export_format,
            )

    # Public run entry that routes by workflow mode.
    def run(
        self,
        modality: str,
        mode: str = "query_first",
        **kwargs: Any,
    ) -> tuple[Any, dict]:
        """Primary public entry that routes by workflow mode.

        ``modality`` selects the declarative pipeline (e.g. 'protein', 'compound', 'interaction');
        ``mode`` selects the workflow execution strategy.

        Examples:
          run(modality='protein', mode='query_first', query='...')
          run(modality='interaction', mode='query_composition', queries_with_labels=[...])

        Args:
            modality (str): The modality to run ('protein', 'compound', 'interaction').
            mode (str): The workflow mode to run ('query_first', 'query_composition').
            **kwargs: Additional arguments passed to the selected mode handler.

        Returns:
            tuple[Any, dict]: Result data and run metadata from the selected handler.

        Raises:
            ValueError: If ``modality`` or ``mode`` is empty, or ``mode`` is unknown.

        """
        if not modality:
            msg = "`modality` is required for MainWorkflow.run"
            raise ValueError(msg)
        if not mode:
            msg = "`mode` is required for MainWorkflow.run"
            raise ValueError(msg)

        modality = modality.lower()
        workflow_mode = mode.lower()
        with contextlib.suppress(Exception):
            self.log.debug("Run invoked with mode=%s modality=%s kwargs=%s", workflow_mode, modality, kwargs)

        if workflow_mode == "query_first":
            return self.query_first(modality=modality, **kwargs)
        if workflow_mode == "query_composition":
            return self.query_composition(modality=modality, **kwargs)
        msg = f"Unknown workflow mode: {workflow_mode}"
        raise ValueError(msg)

    # ---- Pipeline step implementations ----
    def _fetch_uniprot_query(
        self,
        query: Any,
        *,
        fields: str,
        sort: str,
        include_isoform: bool,
        timeout: float | None,
    ) -> tuple[Any, Any]:
        """Submit one UniProt stream query, logging start and completion.

        Args:
            query (Any): The UniProt query to submit.
            fields (str): Comma-separated UniProt return fields.
            sort (str): Sort expression for the stream query.
            include_isoform (bool): Whether to include isoforms.
            timeout (float | None): Request timeout in seconds.

        Returns:
            tuple[Any, Any]: The raw response and its fetch metadata.

        """
        self.log.info(
            "Pipeline: fetching UniProt for query=%s fields=%s sort=%s include_isoform=%s",
            query,
            fields,
            sort,
            include_isoform,
        )
        resp, fetch_meta = self.uniprot.submit_stream(
            query=query,
            fields=(fields or ""),
            sort=sort,
            include_isoform=include_isoform,
            timeout=timeout,
        )
        if isinstance(fetch_meta, dict):
            extra = fetch_meta.get("extra", {})
            self.log.info(
                "Pipeline: UniProt fetch completed (status=%s elapsed=%.2fs size_bytes=%s results=%s)",
                extra.get("status_code"),
                _elapsed_seconds(fetch_meta.get("started_at"), fetch_meta.get("finished_at")),
                extra.get("response_size_bytes"),
                extra.get("total_results"),
            )
        return resp, fetch_meta

    def _step_fetch_uniprot(self, context: dict[str, Any]) -> None:
        """Fetch the UniProt step query (or queries) and store the response in ``context``.

        Reads the interpreted query and fetch options from ``context['searches']['uniprot']``,
        skips empty queries defensively, fetches each query (combining results for a list),
        and writes the response and fetch metadata back into ``context``.

        Args:
            context (dict[str, Any]): Mutable workflow context, updated in place.

        """
        args = context.get("searches", {}).get("uniprot", {}) or context.get("args", {})
        interpreted = context.get("searches", {}).get("uniprot", {}).get("interpreted_query") or args.get(
            "query"
        )
        # Defensive: do not call Uniprot with None/empty query
        if not interpreted:
            self.log.debug(
                "Pipeline: empty/uninterpreted query provided to _step_fetch_uniprot; skipping fetch"
            )
            context["response"] = []
            context.setdefault("metadata", {}).setdefault("fetch", {}).update(
                {"uniprot": {"skipped_empty_query": True}}
            )
            return
        fields = args.get("fields", "") or ""
        sort = args.get("sort", "accession asc")
        include_isoform = args.get("include_isoform", False)
        uniprot_timeout = args.get("uniprot_timeout")

        if isinstance(interpreted, list):
            # Multiple queries: fetch each and combine results
            combined_response: dict[str, Any] = {}
            combined_fetch_meta = {}
            for q in interpreted:
                resp, fetch_meta = self._fetch_uniprot_query(
                    q, fields=fields, sort=sort, include_isoform=include_isoform, timeout=uniprot_timeout
                )
                combined_response["results"] = combined_response.get("results", []) + (
                    resp.get("results", []) if isinstance(resp, dict) else []
                )
                combined_fetch_meta[q] = fetch_meta if isinstance(fetch_meta, dict) else {}
            response = combined_response
            fetch_meta = combined_fetch_meta
        else:
            response, fetch_meta = self._fetch_uniprot_query(
                interpreted,
                fields=fields,
                sort=sort,
                include_isoform=include_isoform,
                timeout=uniprot_timeout,
            )
        # Always store the latest response under context['data']['uniprot'] (setdefault would not overwrite
        # existing value)
        context.setdefault("data", {})["uniprot"] = response
        context.setdefault("metadata", {}).setdefault("uniprot", {}).update(
            {"fetch": fetch_meta if isinstance(fetch_meta, dict) else {}}
        )
        self.log.debug("Pipeline UniProt fetch metadata: %s", fetch_meta)

    def _step_parse_uniprot(self, context: dict[str, Any]) -> None:
        """Parse the stored UniProt response into the requested format, recording timing.

        Parse errors are caught defensively: the parsed data is replaced with an empty
        DataFrame and the error is recorded in the context metadata so the workflow can
        continue.

        Args:
            context (dict[str, Any]): Mutable workflow context, updated in place.

        """
        args = context.get("searches", {}).get("uniprot", {}) or context.get("args", {})
        export_format = args.get("export_format") or self.default_export_format
        parse_format = normalize_parse_format(export_format) or "dataframe"
        resp_val = context.get("data", {}).get("uniprot")
        response = resp_val if resp_val is not None else {}
        # cast fmt to Any to avoid strict Literal typing issues when passing runtime variables
        parse_started = time.time()
        try:
            self.log.info("Pipeline: parsing UniProt results format=%s", parse_format)
            data, parse_meta = self.uniprot.parse(
                results=response, extract_fields=None, format=cast("Any", parse_format)
            )
            parse_elapsed = time.time() - parse_started
            parsed_count = None
            if isinstance(data, (pl.DataFrame, list)):
                parsed_count = len(data)
            elif isinstance(data, dict):
                parsed_count = len(cast("list", data.get("results", [])))
            context["data"]["uniprot"] = data
            if isinstance(parse_meta, dict):
                parse_meta["elapsed_seconds"] = parse_elapsed
                parse_meta["parsed_count"] = parsed_count
            context.setdefault("metadata", {}).setdefault("uniprot", {}).setdefault(
                "parsing", parse_meta if isinstance(parse_meta, dict) else {}
            )
            self.log.debug("Pipeline UniProt parse metadata: %s", parse_meta)
            self.log.info(
                "Pipeline: UniProt parse completed (elapsed=%.2fs parsed=%s output_type=%s)",
                parse_elapsed,
                parsed_count if parsed_count is not None else "unknown",
                type(data).__name__,
            )
        except Exception as e:  # defensive catch-all; logged with traceback below
            parse_elapsed = time.time() - parse_started
            # Defensive: some upstream parsers may evaluate DataFrames in boolean context
            # (e.g., `if results:`) which raises ValueError("The truth value of a DataFrame is ambiguous").
            # Catch any parse error, record it and continue with an empty DataFrame so the
            # workflow can proceed without crashing. Use log.exception so a real parse bug
            # surfaces with a traceback instead of being degraded to a one-line "0 results".
            self.log.exception(
                "_step_parse: parser failed after %.2fs; setting empty DataFrame", parse_elapsed
            )
            context["data"]["uniprot"] = pl.DataFrame()
            context.setdefault("metadata", {}).setdefault("uniprot", {}).setdefault(
                "parsing", {"error": str(e)}
            )

    def _step_crossref_enrich(self, context: dict[str, Any], **kwargs: Any) -> None:
        """Run CrossRef enrichment on the parsed UniProt data when enabled.

        Skips when ``enrich`` is false or no cross-reference fields were requested,
        recording the skip reason in metadata. Otherwise, runs enrichment and stores
        the enriched data and metadata in ``context``.

        Args:
            context (dict[str, Any]): Mutable workflow context, updated in place.
            **kwargs: Enrichment options; notable keys: ``max_workers``, ``total_retries``.

        """
        args = context.get("searches", {}).get("uniprot", {})
        input_data = context.get("data", {}).get("uniprot")
        cross_ref_fields = normalize_crossref_fields(args.get("additional_crossref_fields"))
        enrich_flag = args.get("enrich", False)
        export_format = args.get("export_format") or self.default_export_format
        parse_format = normalize_parse_format(export_format) or "dataframe"
        max_workers = kwargs.get("max_workers", 4)
        total_retries = kwargs.get("total_retries", 3)

        if not enrich_flag:
            self.log.info("Pipeline: enrichment skipped (enrich=False)")
            return

        if not cross_ref_fields:
            self.log.info(
                "Pipeline: Skipping CrossRef enrichment because no cross-reference fields were requested."
            )
            context.setdefault("metadata", {})["uniprot_enrichment"] = {
                "skipped": True,
                "reason": "no_crossref_fields",
            }
            return

        self.log.info("Pipeline: starting CrossRef enrichment with fields=%s", cross_ref_fields)
        enrich_started = time.time()
        enriched, enriched_meta = run_crossref_enrichment(
            data=input_data if input_data is not None else pl.DataFrame(),
            crossref_fields=cross_ref_fields,
            format=cast("Literal['json', 'dataframe', 'xml']", parse_format),
            max_workers=max_workers,
            total_retries=total_retries,
        )
        enrich_elapsed = time.time() - enrich_started
        context["data"].setdefault("uniprot_enrichment", enriched)
        context["metadata"].setdefault("uniprot_enrichment", enriched_meta)
        self.log.debug("Pipeline enrichment metadata: %s", enriched_meta)
        self.log.info("Pipeline: CrossRef enrichment completed (elapsed=%.2fs)", enrich_elapsed)

    def _step_fetch_chembl(self, context: dict[str, Any], search_type: str | None = "activity") -> None:
        """Search ChEMBL for the query found in ``context['searches']['chembl']``.

        Skips empty queries defensively. For activity searches, derives an IC50
        activity filter, applies it post-fetch, and records filter metadata. Stores
        the result and metadata in ``context``.

        Args:
            context (dict[str, Any]): Mutable workflow context, updated in place.
            search_type (str | None): ChEMBL search kind (e.g. 'activity', 'target').

        """
        chembl_search = context.get("searches", {}).get("chembl", {})
        query = chembl_search.get("interpreted_query") or chembl_search.get("query")
        query_structure = chembl_search.get("query_structure")
        export_format = chembl_search.get("export_format") or self.default_export_format
        pages_to_fetch = normalize_chembl_pages_to_fetch(chembl_search.get("pages_to_fetch", -1))
        limit = int(chembl_search.get("limit", 100))
        parse_format = normalize_parse_format(export_format) or "dataframe"
        # Because there is two types of queries associated with 2 different methods,
        #   we need to check which one to use.
        if not query:
            self.log.debug("Pipeline: empty query for ChEMBL fetch; skipping")
            context["chembl_result"] = pl.DataFrame()
            context.setdefault("metadata", {}).setdefault("chembl", {"skipped_empty_query": True})
            return

        self.log.info("Pipeline: fetching ChEMBL for query=%s search_type=%s", query, search_type)
        instance = ChEMBLInterface()
        activity_filter = None
        fetch_query = query
        fetch_method = f"{search_type}-search" if search_type else "activity-search"
        if isinstance(query_structure, dict):
            resource = str(query_structure.get("resource") or "")
            fetch_method = resource
            if "filters" in query_structure:
                fetch_query = {"filters": query_structure["filters"]}
            elif "parameters" in query_structure:
                fetch_query = query_structure["parameters"]
            else:
                fetch_query = query
        elif search_type == "activity":
            activity_filter = instance.extract_ic50_activity_filter(query)
        result, meta = instance.fetch_single(
            query=fetch_query,
            method=fetch_method,
            parse=True,
            format=cast("Any", parse_format),
            pages_to_fetch=pages_to_fetch,
            limit=limit,
        )
        if isinstance(meta, dict):
            meta["pagination"] = {
                "limit": limit,
                "pages_to_fetch": pages_to_fetch,
                "fetch_all_pages": pages_to_fetch == -1,
            }
        if activity_filter:
            result, post_filter_meta = filter_chembl_activity_result(result, activity_filter)
            if isinstance(meta, dict):
                meta["activity_filter"] = activity_filter_metadata(activity_filter)
                meta["api_filter"] = {
                    "applied": True,
                    "endpoint": "activity",
                    "standard_units_constrained": activity_filter.get("standard_units") is not None,
                    "pagination_capped": pages_to_fetch != -1,
                }
                meta["post_fetch_filter"] = post_filter_meta
                meta["data_info"] = instance._build_data_info(result)  # noqa: SLF001  # library-internal helper
        context["data"]["chembl"] = result
        context["metadata"]["chembl"] = meta
        self.log.debug("Pipeline ChEMBL fetch metadata: %s", meta)

    def _step_fetch_pubchem(self, context: dict[str, Any]) -> None:
        """Execute a PubChem request plan and store normalized compound results."""
        pubchem_search = context.get("searches", {}).get("pubchem", {})
        request_plan = pubchem_search.get("request_plan")
        if not isinstance(request_plan, dict):
            self.log.debug("Pipeline: missing PubChem request plan; skipping")
            context.setdefault("data", {})["pubchem"] = pl.DataFrame()
            context.setdefault("metadata", {}).setdefault(
                "pubchem", {"skipped": True, "reason": "missing_request_plan"}
            )
            return

        self.log.info(
            "Pipeline: fetching PubChem for resource=%s model=%s",
            request_plan.get("resource"),
            request_plan.get("query_model"),
        )
        result, metadata = execute_pubchem_request_plan(request_plan)
        context.setdefault("data", {})["pubchem"] = result
        context.setdefault("metadata", {})["pubchem"] = metadata
        self.log.debug("Pipeline PubChem fetch metadata: %s", metadata)

    def _step_fetch_chebi(self, context: dict[str, Any]) -> None:
        """Execute a ChEBI request plan and store normalized compound results."""
        chebi_search = context.get("searches", {}).get("chebi", {})
        request_plan = chebi_search.get("request_plan")
        if not isinstance(request_plan, dict):
            self.log.debug("Pipeline: missing ChEBI request plan; skipping")
            context.setdefault("data", {})["chebi"] = pl.DataFrame()
            context.setdefault("metadata", {}).setdefault(
                "chebi", {"skipped": True, "reason": "missing_request_plan"}
            )
            return

        self.log.info(
            "Pipeline: fetching ChEBI for resource=%s model=%s",
            request_plan.get("resource"),
            request_plan.get("query_model"),
        )
        result, metadata = execute_chebi_request_plan(request_plan)
        context.setdefault("data", {})["chebi"] = result
        context.setdefault("metadata", {})["chebi"] = metadata
        self.log.debug("Pipeline ChEBI fetch metadata: %s", metadata)

    def _step_chembl_to_uniprot_query(
        self, context: dict[str, Any], keep_original_query: bool = True
    ) -> None:
        """Build a UniProt subquery from the ChEMBL IDs in the fetched results.

        Extracts ChEMBL IDs from the stored ChEMBL result, chunks large ID sets to
        keep queries short, and writes the resulting ``xref:chembl-*`` query (or list
        of chunked queries) into ``context['searches']['uniprot']['query']``. Does
        nothing when no IDs are found.

        Args:
            context (dict[str, Any]): Mutable workflow context, updated in place.
            keep_original_query (bool): Whether to ``AND`` the new query with the
                existing UniProt query.

        """
        # Build UniProt subquery from ChEMBL results (reuse logic similar to _resolve_chembl_search)
        result = context.get("data", {}).get("chembl")
        ids = []
        if isinstance(result, pl.DataFrame) and not result.is_empty():
            for col in ("target_chembl_id", "chembl_id", "molecule_chembl_id"):
                if col in result.columns:
                    ids = result[col].drop_nulls().unique(maintain_order=True).to_list()
                    break
        elif isinstance(result, list):
            for item in result:
                if isinstance(item, dict):
                    for v in item.values():
                        if isinstance(v, str) and v.startswith("CHEMBL"):
                            ids.append(v)
        elif isinstance(result, dict):
            for v in result.values():
                if isinstance(v, str) and v.startswith("CHEMBL"):
                    ids.append(v)

        ids = [str(i) for i in ids if i]
        if not ids:
            self.log.debug("Pipeline: no ChEMBL IDs found; leaving interpreted_query untouched")
            return
        if len(ids) > CHEMBL_ID_CHUNK_SIZE:
            self.log.warning(
                "Pipeline: large number of ChEMBL IDs (%s); UniProt query may be too long", len(ids)
            )
            self.log.info("Searches will be divided into chunks of %s IDs", CHEMBL_ID_CHUNK_SIZE)
            output_list = []
            for i in range(0, len(ids), CHEMBL_ID_CHUNK_SIZE):
                chunk_ids = ids[i : i + CHEMBL_ID_CHUNK_SIZE]
                chunk_query = "(" + " OR ".join([f"xref:chembl-{i}" for i in chunk_ids]) + ")"
                # attatch or extend existing interpreted_query for each chunk
                prev = (
                    context.get("searches", {}).get("uniprot", {}).get("query")
                    if keep_original_query
                    else None
                )
                new_query = f"{prev} AND {chunk_query}" if prev else chunk_query
                output_list.append(new_query)
            context["searches"]["uniprot"]["query"] = output_list
            self.log.debug("Pipeline built UniProt subqueries from ChEMBL IDs in %s chunks", len(output_list))
        else:
            out = "(" + " OR ".join([f"xref:chembl-{i}" for i in ids]) + ")"
            # attach or extend existing interpreted_query
            prev = context.get("searches", {}).get("uniprot", {}).get("query")
            new_query = f"{prev} AND {out}" if prev and keep_original_query else out
            context["searches"]["uniprot"]["query"] = new_query
            self.log.debug("Pipeline built UniProt subquery from ChEMBL IDs: %s", out)

    # ---- Core modality handlers ----
    def run_protein(
        self,
        query: str | None = None,
        fields: str | None = None,
        sort: str = "accession asc",
        include_isoform: bool = False,
        export_format: str | None = None,
        enrich: bool = False,
        uniprot_timeout: float | None = None,
        crossref_endpoint_specs: list[EndpointSpec] | None = None,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> tuple[dict, dict]:
        """Run the protein modality: fetch UniProt, parse, and optionally enrich.

        The most basic form of query is a UniProt query string, e.g. "organism:9606 AND reviewed:true".
        When a prepared ``context`` is supplied, non-``None`` arguments override its existing
        UniProt search args; otherwise a fresh context is created and the query interpreted.

        Args:
            query (str | None): UniProt query string.
            fields (str | None): Comma-separated UniProt return fields.
            sort (str): Sort expression for the stream query.
            include_isoform (bool): Whether to include isoforms.
            export_format (str | None): Output format; defaults to the workflow default.
            enrich (bool): Whether to run CrossRef enrichment.
            uniprot_timeout (float | None): UniProt request timeout in seconds.
            crossref_endpoint_specs (list[EndpointSpec] | None): Explicit enrichment endpoints.
            context (dict[str, Any] | None): Prepared workflow context to reuse, if any.
            **kwargs: Forwarded to pipeline steps; notable keys: ``crossref_fields``,
                ``max_workers``, ``total_retries``.

        Returns:
            tuple[dict, dict]: Result data and run metadata.

        """
        if context is None and query is not None and is_chembl_prefixed_query(query):
            raise ValueError(PROTEIN_CHEMBL_QUERY_ERROR)
        if context is None and is_pubchem_or_chebi_prefixed_query(query):
            raise ValueError(PROTEIN_COMPOUND_SOURCE_QUERY_ERROR)

        uniprot_interpreter = build_default_uniprot_interpreter()

        export_format = export_format or self.default_export_format

        args: dict[str, Any] = {
            "query": query,
            "interpreted_query": None,
            "additional_crossref_fields": None,
            "fields": fields or "",
            "sort": sort,
            "include_isoform": include_isoform,
            "export_format": export_format,
            "enrich": enrich,
            "uniprot_timeout": uniprot_timeout,
            "crossref_endpoint_specs": crossref_endpoint_specs,
        }
        if context is not None:
            existing_args = context.get("searches", {}).get("uniprot", {}) or {}
            # Only override keys that are not None from this call
            override = {k: v for k, v in args.items() if v is not None}
            context["searches"]["uniprot"] = {**existing_args, **override}
        else:
            context = {
                "searches": {"uniprot": args},
                "data": {"uniprot": {}},
                "metadata": {"mode": "query_first", "modality": "protein", "origin": "query"},
            }
            context["searches"]["uniprot"]["interpreted_query"] = uniprot_interpreter.interpret(
                query=args.get("query", "")
            )

        extracted_crossref_fields = uniprot_interpreter.extract_databases(
            query=context["searches"]["uniprot"].get("query", "")
        )
        explicit_crossref_fields = normalize_crossref_fields(kwargs.get("crossref_fields"))
        combined_crossref_fields = []
        for crossref_field in extracted_crossref_fields + explicit_crossref_fields:
            if crossref_field not in combined_crossref_fields:
                combined_crossref_fields.append(crossref_field)

        context["searches"]["uniprot"]["additional_crossref_fields"] = combined_crossref_fields

        self._step_fetch_uniprot(context)
        self._step_parse_uniprot(context)
        self._step_crossref_enrich(context, **kwargs)

        cast("dict", context["metadata"]).update(
            {
                "time_taken_seconds": sum(
                    [
                        _elapsed_seconds(
                            context.get("metadata", {}).get("uniprot", {}).get("fetch", {}).get("started_at"),
                            context.get("metadata", {})
                            .get("uniprot", {})
                            .get("fetch", {})
                            .get("finished_at"),
                        ),
                        calculate_enrichment_execution_time(
                            context.get("metadata", {}).get("uniprot_enrichment", {})
                        ),
                    ]
                )
            }
        )

        return context.get("data", {}), context.get("metadata", {})

    def run_compound(
        self,
        query: str,
        search_type: str | None = "activity",
        export_format: str | None = None,
        chembl_pages_to_fetch: int | None = None,
        context: dict[str, Any] | None = None,
        **_kwargs: Any,
    ) -> tuple[dict, dict]:
        """Run the compound modality through the matching compound data source.

        Source-prefixed ChEMBL, PubChem, and ChEBI compound queries are routed
        to their respective backends. Compound workflows keep compound-source
        outputs and do not automatically map ChEMBL targets back to UniProt;
        protein-ligand interaction workflows own that cross-entity mapping
        behavior.

        Args:
            query (str): The user-friendly compound query string.
            search_type (str | None): The type of ChEMBL search to perform. Defaults to "activity".
            export_format (str | None): The desired export format; defaults to the workflow default.
            chembl_pages_to_fetch (int | None): ChEMBL pages to fetch. Use -1 for all pages.
            context (dict[str, Any] | None): Optional context dictionary to carry state between steps.
            **kwargs: Forwarded to ``run_protein`` (only its recognized parameters).

        Returns:
            tuple[dict, dict]: Result data and run metadata.

        """
        pubchem_request_plan = build_pubchem_request_plan(query)
        if pubchem_request_plan is not None:
            context = {
                "searches": {
                    "pubchem": {
                        "query": query,
                        "interpreted_query": query,
                        "request_plan": pubchem_request_plan,
                        "modality": "compound",
                    },
                },
                "data": {},
                "metadata": {"mode": "query_first", "modality": "compound", "origin": "query"},
            }
            self._step_fetch_pubchem(context)
            return context.get("data", {}), context.get("metadata", {})

        chebi_request_plan = build_chebi_request_plan(query)
        if chebi_request_plan is not None:
            context = {
                "searches": {
                    "chebi": {
                        "query": query,
                        "interpreted_query": query,
                        "request_plan": chebi_request_plan,
                        "modality": "compound",
                    },
                },
                "data": {},
                "metadata": {"mode": "query_first", "modality": "compound", "origin": "query"},
            }
            self._step_fetch_chebi(context)
            return context.get("data", {}), context.get("metadata", {})

        validate_compound_chembl_query_resource(query)
        chembl_interpreter = build_default_chembl_interpreter()
        export_format = export_format or self.default_export_format
        pages_to_fetch = normalize_chembl_pages_to_fetch(chembl_pages_to_fetch)
        query_structure = build_chembl_query_structure(query)
        resolved_search_type = resolve_chembl_search_type_from_query(query, search_type)

        args: dict[str, Any] = {
            "query": query,
            "interpreted_query": None,
            "export_format": export_format,
            "search_type": resolved_search_type,
            "modality": "compound",
            "pages_to_fetch": pages_to_fetch,
        }
        if query_structure is not None:
            args["query_structure"] = query_structure
        if context is None:
            context = {
                "searches": {
                    "chembl": args,
                },
                "data": {},
                "metadata": {"mode": "query_first", "modality": "compound", "origin": "query"},
            }
        else:
            # Merge explicit function args into existing context args so callers that pass
            # a prepared context (e.g. run_interaction) have their desired parameters honored.
            existing_searches = context.get("searches") or {}
            # Only override keys that are not None from this call
            override = {k: v for k, v in args.items() if v is not None}
            merged = {**existing_searches, **override}
            context["searches"] = merged

        if query_structure is None:
            context["searches"]["chembl"]["interpreted_query"] = chembl_interpreter.interpret(
                query=args.get("query", "")
            )
        else:
            context["searches"]["chembl"]["interpreted_query"] = query

        # Fetch ChEMBL results
        self._step_fetch_chembl(context, search_type=resolved_search_type)
        return context.get("data", {}), context.get("metadata", {})

    def run_interaction(
        self,
        query: str,
        interaction_type: str | None = None,
        export_format: str | None = None,
        **kwargs: Any,
    ) -> tuple[dict, dict]:
        """Run the interaction modality, fetching interaction candidates from BioGRID/ChEMBL.

        May perform more than one search (e.g., ChEMBL + UniProt). Example queries:

        - ``"pli:'Proteases' AND {uniprot_filter_query}"`` — searches ChEMBL, extracts IDs, then fetches from
          UniProt.
        - ``"ppi:'disease:cancer' AND {uniprot_filter_query}"`` — searches UniProt; BioGRID is used for
          interaction data only.

        Args:
            query (str): The user-friendly interaction query string.
            interaction_type (str | None): Interaction kind ('protein-protein' or 'protein-ligand').
            export_format (str | None): Output format; defaults to the workflow default.
            **kwargs: Forwarded to pipeline steps; notable keys: ``uniprot_timeout``,
                ``chembl_pages_to_fetch``, ``max_workers``, ``total_retries``.

        Returns:
            tuple[dict, dict]: Result data and run metadata; empty dicts for an
            unrecognized ``interaction_type``.

        Raises:
            ValueError: If ``interaction_type`` is missing.

        """
        # ====== Short PPI search explanation ======
        # After searching UniProt with a desired query (e.g., "disease:cancer AND reviewed:true"),
        # We get a list of columns that we can use to retrieve data from different databases.
        # For example,
        # string_ids: '9606.ENSP00000269305' (from STRING database) can be used to get interactions giving us
        # gene_a vs gene_b and score
        # biogrid_ids: '108356' (from BioGRID database) can be used to get interactions giving us gene_a vs
        # gene_b and experimental details
        # ====== Short PLI search explanation ======
        # We do a similar approach for PLI, but we use ChEMBL to get the interactions with a target.
        # After that we search UniProt for the target details.
        if not interaction_type:
            msg = "interaction_type is required for run_interaction"
            raise ValueError(msg)
        if is_pubchem_or_chebi_prefixed_query(query):
            raise ValueError(INTERACTION_COMPOUND_SOURCE_QUERY_ERROR)

        export_format = export_format or self.default_export_format

        uniprot_interpreter = build_default_uniprot_interpreter()
        chembl_interpreter = build_default_chembl_interpreter()

        args: dict[str, Any] = {
            "query": query,
            "export_format": export_format,
            "interaction_type": interaction_type,
            "modality": "interaction",
        }
        if "uniprot_timeout" in kwargs:
            args["uniprot_timeout"] = kwargs.get("uniprot_timeout")
        chembl_pages_to_fetch = normalize_chembl_pages_to_fetch(kwargs.get("chembl_pages_to_fetch"))
        context: dict[str, Any] = {
            "searches": {
                "uniprot": args,
            },
            "data": {},
            "metadata": {"mode": "query_first", "modality": "interaction", "origin": "query"},
        }

        # Fetch interaction candidates
        if interaction_type == "protein-protein":
            if is_chembl_prefixed_query(query):
                raise ValueError(PPI_CHEMBL_QUERY_ERROR)
            # Interpret original interaction query
            context["searches"]["uniprot"]["interpreted_query"] = uniprot_interpreter.interpret(
                query=args.get("query", "")
            )
            # For PPI, we first search UniProt to get accessions matching the query,
            # then use those accessions to fetch interactions from BioGRID and StringDB.
            self._step_fetch_uniprot(context)
            self._step_parse_uniprot(context)
            # Instead of doing a enrichment we use another method to fetch specific endpoint from Biogrid and
            # StringDB.
            self._step_fetch_additional_ppi_interaction_sources(context, **kwargs)

            return context.get("data", {}), context.get("metadata", {})
        if interaction_type == "protein-ligand":
            query_structure = build_chembl_query_structure(query)
            resolved_search_type = resolve_chembl_search_type_from_query(query, "target")
            if query_structure is not None and resolved_search_type not in {
                "target",
                "activity",
                "assay",
            }:
                msg = (
                    f"ChEMBL resource '{resolved_search_type}' is not valid for protein-ligand "
                    "interaction workflows. Use chembl.target, chembl.activity, or chembl.assay."
                )
                raise ValueError(msg)
            context["searches"]["chembl"] = {
                "query": query,
                "export_format": export_format,
                "search_type": resolved_search_type,
                "pages_to_fetch": chembl_pages_to_fetch,
            }
            if query_structure is None:
                context["searches"]["chembl"]["interpreted_query"] = chembl_interpreter.interpret(
                    query=args.get("query", "")
                )
            else:
                context["searches"]["chembl"]["interpreted_query"] = query
                context["searches"]["chembl"]["query_structure"] = query_structure
            # For PLI, we first search ChEMBL to get compounds/targets matching the query,
            self._step_fetch_chembl(context, search_type=resolved_search_type)
            # then use those targets to fetch UniProt details.
            self._step_chembl_to_uniprot_query(context, keep_original_query=False)
            uniprot_query = context.get("searches", {}).get("uniprot", {}).get("query")
            if not uniprot_query:
                self.log.debug("Pipeline: no UniProt query generated from ChEMBL IDs for PLI")
                return context.get("data", {}), context.get("metadata", {})
            # Interpret UniProt query and append to ChEMBL IDs search
            chembl_ids_query = context["searches"]["uniprot"]["query"]
            # Combine both queries
            context["searches"]["uniprot"] = {
                "query": query,
                "interpreted_query": chembl_ids_query,
                "export_format": export_format,
            }
            return self.run_protein(context=context)

        return {}, {}

    def query_first(
        self,
        modality: str,
        query: str,
        fields: str | None = None,
        sort: str = "accession asc",
        include_isoform: bool = False,
        export_format: str | None = None,
        enrich: bool = False,
        crossref_endpoint_specs: list[EndpointSpec] | None = None,
        search_type: str | None = "activity",
        interaction_type: str | None = None,
        **kwargs: Any,
    ) -> tuple[dict, dict]:
        """Interpret ``query`` and route to the modality-specific handler.

        Args:
            modality (str): Modality to run ('protein', 'compound', 'interaction').
            query (str): The user-friendly query string.
            fields (str | None): Comma-separated UniProt return fields.
            sort (str): Sort expression for the UniProt stream query.
            include_isoform (bool): Whether to include isoforms.
            export_format (str | None): Output format; defaults to the workflow default.
            enrich (bool): Whether to run CrossRef enrichment.
            crossref_endpoint_specs (list[EndpointSpec] | None): Explicit enrichment endpoints.
            search_type (str | None): ChEMBL search kind for the compound modality.
            interaction_type (str | None): Interaction kind for the interaction modality.
            **kwargs: Forwarded to the selected modality handler.

        Returns:
            tuple[dict, dict]: Result data and run metadata.

        Raises:
            ValueError: If ``modality`` is unknown.

        """
        modality = (modality or "").lower()
        if modality == "protein":
            return self.run_protein(
                query=query,
                fields=fields,
                sort=sort,
                include_isoform=include_isoform,
                export_format=export_format,
                enrich=enrich,
                crossref_endpoint_specs=crossref_endpoint_specs,
                **kwargs,
            )
        if modality == "compound":
            return self.run_compound(
                query=query,
                fields=fields,
                export_format=export_format,
                enrich=enrich,
                crossref_endpoint_specs=crossref_endpoint_specs,
                search_type=search_type,
                **kwargs,
            )
        if modality == "interaction":
            return self.run_interaction(
                query=query,
                export_format=export_format,
                enrich=enrich,
                crossref_endpoint_specs=crossref_endpoint_specs,
                interaction_type=interaction_type,
                **kwargs,
            )
        msg = f"Unknown modality: {modality}"
        raise ValueError(msg)

    def query_composition(
        self,
        modality: str,
        queries_with_labels: Iterable[tuple[str, str]],
        fields: str | None = None,
        export_format: str | None = None,
        enrich: bool = False,
        crossref_endpoint_specs: list[EndpointSpec] | None = None,
        search_type: str | None = "activity",
        **kwargs: Any,
    ) -> tuple[dict, dict]:
        """Run several labeled queries and tag every result row with its label.

        Each ``(query, label)`` pair calls ``query_first`` and attaches the label to every row.
        Example::

            queries_with_labels = [
                ("Proteases AND reviewed:true", "protease_reviewed"),
                ("Kinases AND reviewed:false", "kinase_unreviewed"),
            ]

        Args:
            modality (str): Modality to run for every query ('protein', 'compound', 'interaction').
            queries_with_labels (Iterable[tuple[str, str]]): ``(query, label)`` pairs.
            fields (str | None): Comma-separated UniProt return fields.
            export_format (str | None): Output format; defaults to the workflow default.
            enrich (bool): Whether to run CrossRef enrichment.
            crossref_endpoint_specs (list[EndpointSpec] | None): Explicit enrichment endpoints.
            search_type (str | None): ChEMBL search kind for the compound modality.
            **kwargs: Forwarded to the selected modality handler.

        Returns:
            tuple[dict, dict]: Merged, labeled result data and aggregated run metadata
            (with a ``parts`` list of per-query metadata).

        Raises:
            ValueError: If ``modality`` is unknown.

        """
        combined_rows: list[Any] = []
        combined_enrichment: list[Any] = []
        metadata: dict = {"mode": "query_composition", "modality": modality, "origin": "query", "parts": []}

        for query, label in queries_with_labels:
            if modality == "protein":
                part_data, part_meta = self.run_protein(
                    query=query,
                    fields=fields,
                    export_format=export_format,
                    enrich=enrich,
                    crossref_endpoint_specs=crossref_endpoint_specs,
                    **kwargs,
                )
            elif modality == "compound":
                part_data, part_meta = self.run_compound(
                    query=query,
                    fields=fields,
                    export_format=export_format,
                    enrich=enrich,
                    crossref_endpoint_specs=crossref_endpoint_specs,
                    search_type=search_type,
                    **kwargs,
                )
            elif modality == "interaction":
                part_data, part_meta = self.run_interaction(
                    query=query,
                    export_format=export_format,
                    enrich=enrich,
                    crossref_endpoint_specs=crossref_endpoint_specs,
                    **kwargs,
                )
            else:
                msg = f"Unknown modality: {modality}"
                raise ValueError(msg)

            # Note: part_data is normally a dict of per-database results, e.g. uniprot (plus
            # uniprot_enrichment) for protein modality, with chembl added for compound modality.
            # part_meta holds the run metadata (mode, modality, origin, per-database entries and
            # their enrichment) for that specific run.

            labeled_part = attach_label_to_part(part_data, label, modality)
            if isinstance(labeled_part, dict):
                combined_rows.append(labeled_part)

            enrichment_data = part_data.get("uniprot_enrichment") if isinstance(part_data, dict) else None
            if enrichment_data:
                combined_enrichment = merge_enrichment_data(combined_enrichment, enrichment_data)

            metadata["parts"].append({"query": query, "label": label, "meta": part_meta})

        # Combined_rows now contains only the labeled data parts in a list.
        # For example
        # { "uniprot": [...], "chembl": [...] }  # noqa: ERA001
        # On the other hand, combined_enrichment contains only the enrichment data combined.
        # For example
        # {  # noqa: ERA001
        #   "alphafold_prediction": [pl.DataFrame(...)],  # noqa: ERA001
        #   "pdb_entry": [pl.DataFrame(...)],  # noqa: ERA001
        # }  # noqa: ERA001
        # We need to generate the final output merging every part.
        # RResulting in: { "uniprot": pl.DataFrame(...), "chembl": pl.DataFrame(...), "uniprot_enrichment": {
        # ... } }
        # Merge results depending on their type,
        # For dataframes we concat, for lists we extend, for dicts we create a list of dicts, for ET we create
        # a list of ET.
        if not combined_rows:
            return {}, metadata

        final_main: dict = {}
        for part in combined_rows:
            for key, value in part.items():
                merge_into_dict(final_main, key, value)

        if combined_enrichment:
            enrichment_final: dict = {}
            for enrich_part in combined_enrichment:
                for db_ep, db_data in enrich_part.items():
                    merge_into_dict(enrichment_final, db_ep, db_data)
            final_main["uniprot_enrichment"] = enrichment_final

        return final_main, metadata

    # ---- Helpers ----
    def _step_fetch_additional_ppi_interaction_sources(self, context: dict, **kwargs: Any) -> None:
        """Fetch protein-protein interaction data from BioGRID and StringDB.

        Inspects the parsed UniProt data for ``biogrid_ids`` / ``string_ids`` columns,
        enriches via the matching endpoints, and stores the result and metadata in
        ``context``.

        Args:
            context (dict): Mutable workflow context, updated in place.
            **kwargs: Enrichment options; notable keys: ``max_workers``, ``total_retries``.

        """
        args = context.get("searches", {}).get("uniprot", {})
        input_data = context.get("data", {}).get("uniprot")
        export_format = args.get("export_format") or self.default_export_format

        # Extract max_workers and total_retries from kwargs
        max_workers = kwargs.get("max_workers", 4)
        total_retries = kwargs.get("total_retries", 3)

        self.log.info("Pipeline: fetching additional interaction sources for protein-protein interactions")

        specs = []
        # Fetch BioGRID interactions
        # Check if Biogrid IDs are present in the input data
        if "biogrid_ids" in input_data.columns:
            specs.append(EndpointSpec(database="biogrid", endpoint="interactions"))
        else:
            self.log.debug("No biogrid_ids column found in input data; skipping BioGRID interaction fetch")
        # Fetch StringDB interactions
        if "string_ids" in input_data.columns:
            specs.append(EndpointSpec(database="string", endpoint="interaction_partners"))
        else:
            self.log.debug("No string_ids column found in input data; skipping StringDB interaction fetch")

        crossref_enricher = CrossRefEnricher(
            endpoint_specs=specs, max_workers=max_workers, total_retries=total_retries
        )
        enriched, enriched_meta = crossref_enricher.enrich(
            data=input_data if input_data is not None else pl.DataFrame(),
            format=cast("Literal['json', 'dataframe', 'xml']", export_format),
        )

        context["data"].setdefault("uniprot_enrichment", enriched)
        context["metadata"].setdefault("uniprot_enrichment", enriched_meta)
        self.log.debug("Pipeline additional interaction sources enrichment metadata: %s", enriched_meta)
