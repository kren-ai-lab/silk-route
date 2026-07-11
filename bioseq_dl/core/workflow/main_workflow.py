"""High-level multi-step download workflow orchestrator."""

from __future__ import annotations

import contextlib
import time
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING, Any, Literal, cast

import pandas as pd

from bioseq_dl import ChEBIInterface, ChEMBLInterface, PubChemInterface, UniprotInterface
from bioseq_dl.core.crossref_enricher import CrossRefEnricher, EndpointSpec
from bioseq_dl.core.export import normalize_parse_format
from bioseq_dl.core.utils.crossref_enrichment import (
    build_effective_uniprot_request_fields,
    normalize_crossref_fields,
    run_crossref_enrichment,
)
from bioseq_dl.logging import get_logger

from .chebi_execution import build_chebi_fetch_spec, normalize_chebi_records
from .chebi_query_parser import is_chebi_prefixed_query, parse_chebi_query_builder_string
from .chembl_query_parser import (
    get_chembl_prefixed_query_resource,
    is_chembl_prefixed_query,
    parse_chembl_query_builder_string,
)
from .pubchem_execution import (
    PUBCHEM_WORKFLOW_METHOD,
    build_pubchem_fetch_query,
    normalize_pubchem_records,
)
from .pubchem_query_parser import is_pubchem_prefixed_query, parse_pubchem_query_builder_string
from .query_interpreter import (
    UniProtQueryInterpreter,
    build_default_chembl_interpreter,
    build_default_uniprot_interpreter,
)
from .query_prefixes import get_query_source_prefix, is_any_source_prefixed_query

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
PROTEIN_SOURCE_QUERY_ERROR = (
    "{source}-prefixed queries are not valid for protein workflows. "
    "Use a compound workflow for chemical-source query builders."
)
PPI_SOURCE_QUERY_ERROR = (
    "{source}-prefixed queries are not valid for protein-protein interaction workflows. "
    "Use compound workflows for chemical-source query builders."
)
PLI_SOURCE_QUERY_ERROR = (
    "{source}-prefixed queries are not valid for protein-ligand interaction workflows. "
    "ChEMBL is the supported source for protein-ligand workflow execution."
)
PLANNED_COMPOUND_QUERY_SOURCES = ("pubchem", "chebi")
COMPOUND_UNSUPPORTED_CHEMBL_RESOURCE_ERROR = (
    "ChEMBL resource '{resource}' is not valid for compound workflows. "
    "Use chembl.molecule or chembl.activity for compound workflows, or use a "
    "protein-ligand interaction workflow for target, assay, or cell-line queries."
)


def calculate_enrichment_execution_time(enrichment_metadata: object) -> float:
    """Return the total execution time reported by enrichment metadata."""
    if not isinstance(enrichment_metadata, dict):
        return 0.0

    total = 0.0
    for metadata in enrichment_metadata.values():
        if not isinstance(metadata, dict):
            continue
        execution_time = metadata.get("execution_time", 0)
        if isinstance(execution_time, (int, float)):
            total += execution_time
    return total


def attach_label_to_part(part_data: dict, label: str, modality: str) -> dict:
    """Attach a query-composition label to a workflow result part."""
    data_to_label = None
    key = None
    if isinstance(part_data, dict):
        if modality == "protein" and part_data.get("uniprot") is not None:
            key = "uniprot"
            data_to_label = part_data.get("uniprot")
        elif modality == "compound":
            key = next(
                (source for source in ("chembl", "pubchem", "chebi") if part_data.get(source) is not None),
                None,
            )
            if key is None:
                return {}
            data_to_label = part_data.get(key)
        elif modality == "interaction" and part_data.get("data") is not None:
            key = "data"
            data_to_label = part_data.get("data")
        else:
            return {}

        if data_to_label is not None:
            if isinstance(data_to_label, pd.DataFrame):
                if "_label" in data_to_label.columns:
                    data_to_label = data_to_label.rename(columns={"_label": "_label_original"})
                data_to_label["_label"] = label
            elif isinstance(data_to_label, list):
                for row in data_to_label:
                    if isinstance(row, dict):
                        row.setdefault("_label", label)
            elif isinstance(data_to_label, dict):
                data_to_label.setdefault("_label", label)
            else:
                data_to_label = {"_label": label}

        if key == "chembl" and modality == "compound":
            return {key: data_to_label, **attach_label_to_part(part_data, label, "protein")}
        return {key: data_to_label}
    return {}


def activity_filter_metadata(activity_filter: dict) -> dict:
    """Return a compact activity filter description for workflow metadata."""
    metadata = {
        "standard_type": activity_filter.get("standard_type"),
        "standard_value_min": activity_filter.get("standard_value_min"),
        "standard_value_max": activity_filter.get("standard_value_max"),
    }
    if "standard_units" in activity_filter:
        metadata["standard_units"] = activity_filter["standard_units"]
    if activity_filter.get("standard_value") is not None:
        metadata["standard_value"] = activity_filter.get("standard_value")
    return metadata


def filter_chembl_activity_dataframe(df: pd.DataFrame, activity_filter: dict) -> tuple[pd.DataFrame, dict]:
    """Apply a defensive ChEMBL activity filter to a DataFrame without changing column types."""
    initial_rows = len(df)
    if df.empty:
        return df.copy(), {
            "applied": True,
            "initial_rows": initial_rows,
            "filtered_rows": 0,
            "removed_rows": 0,
        }

    if "standard_type" not in df.columns or "standard_value" not in df.columns:
        return df.iloc[0:0].copy(), {
            "applied": True,
            "initial_rows": initial_rows,
            "filtered_rows": 0,
            "removed_rows": initial_rows,
            "reason": "missing_standard_type_or_standard_value",
        }

    standard_type = str(activity_filter.get("standard_type", "")).upper()
    type_mask = df["standard_type"].astype(str).str.upper() == standard_type
    standard_units = activity_filter.get("standard_units")
    if standard_units is not None and "standard_units" not in df.columns:
        return df.iloc[0:0].copy(), {
            "applied": True,
            "initial_rows": initial_rows,
            "filtered_rows": 0,
            "removed_rows": initial_rows,
            "reason": "missing_standard_units",
        }

    units_mask = pd.Series(data=True, index=df.index)
    if standard_units is not None:
        normalized_units = (
            df["standard_units"]
            .astype(str)
            .str.strip()
            .str.replace("Âµ", "u", regex=False)
            .str.replace("Î¼", "u", regex=False)
            .str.replace("µ", "u", regex=False)
            .str.replace("μ", "u", regex=False)
        )
        units_mask = normalized_units == standard_units
    values = pd.to_numeric(df["standard_value"], errors="coerce")
    value_mask = values.notna()

    exact_value = activity_filter.get("standard_value")
    if exact_value is not None:
        value_mask &= values == exact_value
    else:
        min_value = activity_filter.get("standard_value_min")
        max_value = activity_filter.get("standard_value_max")
        if min_value is not None:
            if activity_filter.get("standard_value_min_inclusive"):
                value_mask &= values >= min_value
            else:
                value_mask &= values > min_value
        if max_value is not None:
            if activity_filter.get("standard_value_max_inclusive"):
                value_mask &= values <= max_value
            else:
                value_mask &= values < max_value

    filtered = df.loc[type_mask & units_mask & value_mask].copy()
    filtered_rows = len(filtered)
    return filtered, {
        "applied": True,
        "initial_rows": initial_rows,
        "filtered_rows": filtered_rows,
        "removed_rows": initial_rows - filtered_rows,
    }


def filter_chembl_activity_result(result: Any, activity_filter: dict | None) -> tuple[Any, dict]:
    """Apply a defensive ChEMBL activity filter to supported workflow result shapes."""
    if not activity_filter:
        return result, {"applied": False}

    if isinstance(result, pd.DataFrame):
        return filter_chembl_activity_dataframe(result, activity_filter)

    if isinstance(result, list):
        df = pd.DataFrame(result)
        filtered, metadata = filter_chembl_activity_dataframe(df, activity_filter)
        return filtered.to_dict(orient="records"), metadata

    if isinstance(result, dict):
        df = pd.DataFrame([result])
        filtered, metadata = filter_chembl_activity_dataframe(df, activity_filter)
        if filtered.empty:
            return {}, metadata
        return filtered.iloc[0].to_dict(), metadata

    return result, {
        "applied": False,
        "reason": f"unsupported_result_type:{type(result).__name__}",
    }


def normalize_chembl_pages_to_fetch(value: int | None) -> int:
    """Normalize a ChEMBL workflow page cap."""
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


def build_compound_source_query_structure(query: str) -> dict[str, object] | None:
    """Parse a recognized compound-source query string, if present."""
    if is_chembl_prefixed_query(query):
        return build_chembl_query_structure(query)
    if is_pubchem_prefixed_query(query):
        return parse_pubchem_query_builder_string(query)
    if is_chebi_prefixed_query(query):
        return parse_chebi_query_builder_string(query)
    return None


def reject_unsupported_protein_source_query(query: str) -> None:
    """Reject non-UniProt source-prefixed queries before UniProt interpretation."""
    if is_chembl_prefixed_query(query):
        raise ValueError(PROTEIN_CHEMBL_QUERY_ERROR)
    source = get_query_source_prefix(query)
    if is_any_source_prefixed_query(query, PLANNED_COMPOUND_QUERY_SOURCES):
        msg = PROTEIN_SOURCE_QUERY_ERROR.format(source=source)
        raise ValueError(msg)


def reject_unsupported_ppi_source_query(query: str) -> None:
    """Reject non-UniProt source-prefixed queries before protein-protein routing."""
    if is_chembl_prefixed_query(query):
        raise ValueError(PPI_CHEMBL_QUERY_ERROR)
    source = get_query_source_prefix(query)
    if is_any_source_prefixed_query(query, PLANNED_COMPOUND_QUERY_SOURCES):
        msg = PPI_SOURCE_QUERY_ERROR.format(source=source)
        raise ValueError(msg)


def reject_unsupported_pli_source_query(query: str) -> None:
    """Reject unsupported chemical-source prefixes before ChEMBL routing."""
    source = get_query_source_prefix(query)
    if is_any_source_prefixed_query(query, PLANNED_COMPOUND_QUERY_SOURCES):
        msg = PLI_SOURCE_QUERY_ERROR.format(source=source)
        raise ValueError(msg)


def update_compound_source_metadata(
    context: dict[str, Any],
    source: str,
    request_plan: dict[str, Any],
    record_count: int,
    fetch_metadata: object,
) -> None:
    """Record common source execution metadata for a compound workflow."""
    metadata = context.setdefault("metadata", {})
    metadata.update(
        {
            "query_source": source,
            "query_resource": request_plan.get("resource"),
            "query_model": request_plan.get("query_model"),
            "request_plan": request_plan,
            "number_of_records": record_count,
        }
    )
    metadata[source] = {
        "fetch": fetch_metadata if isinstance(fetch_metadata, dict) else {},
        "request_plan": request_plan,
        "number_of_records": record_count,
    }


def merge_enrichment_data(existing: list[Any], new: Any) -> list[Any]:
    """Merge query-composition enrichment result parts by endpoint label."""
    if isinstance(new, dict):
        for db_ep, db_data in new.items():
            if db_data is None:
                continue
            found = False
            for existing_item in existing:
                if db_ep in existing_item:
                    existing_data = existing_item[db_ep]
                    if isinstance(existing_data, pd.DataFrame) and isinstance(db_data, pd.DataFrame):
                        combined_df = pd.concat([existing_data, db_data], ignore_index=True)
                        existing_item[db_ep] = combined_df
                    elif isinstance(existing_data, list) and isinstance(db_data, list):
                        existing_data.extend(db_data)
                        existing_item[db_ep] = existing_data
                    elif isinstance(existing_data, dict) and isinstance(db_data, dict):
                        existing_item[db_ep] = [existing_data, db_data]
                    else:
                        existing_item[db_ep] = [existing_data, db_data]
                    found = True
                    break
            if not found:
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
        pubchem_interface: PubChemInterface | None = None,
        chebi_interface: ChEBIInterface | None = None,
        enricher: CrossRefEnricher | None = None,
        default_export_format: str = "csv",
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize MainWorkflow with optional dependency injection."""
        # Instantiate sensible defaults if not provided
        self.interpreter = interpreter or build_default_uniprot_interpreter()
        self.uniprot = uniprot_interface or UniprotInterface()
        self.pubchem = pubchem_interface
        self.chebi = chebi_interface
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

        # NOTE: declarative pipelines and custom step overrides are disabled for now.
        # Future work: reintroduce `self.pipelines` and `self.step_overrides` for custom pipelines.
        # TODO(diego): Consider normalizing the metadata structure returned by all public methods.
        # Currently metadata is a flexible dict that mixes counters, nested parts, and
        # enrichment outputs (sometimes lists/dicts). Plan: decide on a stable schema
        # (e.g. {'mode':..., 'modality':..., 'results':..., 'enrichment':..., 'parts':...}) and migrate
        # query_first/query_composition to always return (data, metadata)
        # with a consistent metadata shape. Deferred until the CLI/PRISM
        # integration decisions are final.

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
            modality: The modality to run ('protein', 'compound', 'interaction').
            mode: The workflow mode to run ('query_first', 'query_composition').
            **kwargs: Additional arguments passed to the selected mode handler.

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
    def _step_fetch_uniprot(self, context: dict[str, Any]) -> None:
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
        fields = build_effective_uniprot_request_fields(
            args.get("fields", "") or "",
            args.get("additional_crossref_fields"),
            enrich=bool(args.get("enrich", False)),
        )
        sort = args.get("sort", "accession asc")
        include_isoform = args.get("include_isoform", False)
        uniprot_timeout = args.get("uniprot_timeout")

        if isinstance(interpreted, list):
            # Multiple queries: fetch each and combine results
            combined_response = {}
            combined_fetch_meta = {}
            for q in interpreted:
                self.log.info(
                    "Pipeline: fetching UniProt for query=%s fields=%s sort=%s include_isoform=%s",
                    q,
                    fields,
                    sort,
                    include_isoform,
                )
                resp, fetch_meta = self.uniprot.submit_stream(
                    query=q,
                    fields=(fields or ""),
                    sort=sort,
                    include_isoform=include_isoform,
                    timeout=uniprot_timeout,
                )
                if isinstance(fetch_meta, dict):
                    search_process = fetch_meta.get("search_process", {})
                    self.log.info(
                        "Pipeline: UniProt fetch completed (status=%s elapsed=%s size_bytes=%s results=%s)",
                        search_process.get("status_code"),
                        search_process.get("time_taken_seconds"),
                        search_process.get("response_size_bytes"),
                        search_process.get("total_results"),
                    )
                combined_response["results"] = combined_response.get("results", []) + (
                    resp.get("results", []) if isinstance(resp, dict) else []
                )
                combined_fetch_meta[q] = fetch_meta if isinstance(fetch_meta, dict) else {}
            response = combined_response
            fetch_meta = combined_fetch_meta
        else:
            self.log.info(
                "Pipeline: fetching UniProt for query=%s fields=%s sort=%s include_isoform=%s",
                interpreted,
                fields,
                sort,
                include_isoform,
            )
            response, fetch_meta = self.uniprot.submit_stream(
                query=interpreted,
                fields=(fields or ""),
                sort=sort,
                include_isoform=include_isoform,
                timeout=uniprot_timeout,
            )
            if isinstance(fetch_meta, dict):
                search_process = fetch_meta.get("search_process", {})
                self.log.info(
                    "Pipeline: UniProt fetch completed (status=%s elapsed=%s size_bytes=%s results=%s)",
                    search_process.get("status_code"),
                    search_process.get("time_taken_seconds"),
                    search_process.get("response_size_bytes"),
                    search_process.get("total_results"),
                )
        # Always store the latest response under context['data']['uniprot'] (setdefault would not overwrite
        # existing value)
        context.setdefault("data", {})["uniprot"] = response
        context.setdefault("metadata", {}).setdefault("uniprot", {}).update(
            {"fetch": fetch_meta if isinstance(fetch_meta, dict) else {}}
        )
        self.log.debug("Pipeline UniProt fetch metadata: %s", fetch_meta)

    def _step_parse_uniprot(self, context: dict[str, Any]) -> None:
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
            if isinstance(data, (pd.DataFrame, list)):
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
        except Exception as e:  # noqa: BLE001  # defensive catch-all
            parse_elapsed = time.time() - parse_started
            # Defensive: some upstream parsers may evaluate DataFrames in boolean context
            # (e.g., `if results:`) which raises ValueError("The truth value of a DataFrame is ambiguous").
            # Catch any parse error, record it and continue with an empty DataFrame so the
            # workflow can proceed without crashing.
            self.log.warning(
                "_step_parse: parser failed after %.2fs: %s; setting empty DataFrame", parse_elapsed, e
            )
            context["data"]["uniprot"] = pd.DataFrame()
            context.setdefault("metadata", {}).setdefault("uniprot", {}).setdefault(
                "parsing", {"error": str(e)}
            )
            return

    def _step_crossref_enrich(self, context: dict[str, Any], **kwargs: Any) -> None:
        args = context.get("searches", {}).get("uniprot", {})
        input_data = context.get("data", {}).get("uniprot")
        cross_ref_fields = normalize_crossref_fields(args.get("additional_crossref_fields"))
        enrich_flag = args.get("enrich", False)
        export_format = args.get("export_format") or self.default_export_format
        parse_format = normalize_parse_format(export_format) or "dataframe"
        max_workers = kwargs.get("max_workers", 4)
        total_retries = kwargs.get("total_retries", 3)
        download_alphafold_structures = kwargs.get("download_alphafold_structures", True)
        download_pdb_structures = kwargs.get("download_pdb_structures", True)
        output_dir = kwargs.get("output_dir")

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
            data=input_data if input_data is not None else pd.DataFrame(),
            crossref_fields=cross_ref_fields,
            format=cast("Literal['json', 'dataframe', 'xml']", parse_format),
            max_workers=max_workers,
            total_retries=total_retries,
            download_alphafold_structures=download_alphafold_structures,
            download_pdb_structures=download_pdb_structures,
            output_dir=output_dir,
        )
        enrich_elapsed = time.time() - enrich_started
        context["data"].setdefault("uniprot_enrichment", enriched)
        context["metadata"].setdefault("uniprot_enrichment", enriched_meta)
        self.log.debug("Pipeline enrichment metadata: %s", enriched_meta)
        self.log.info("Pipeline: CrossRef enrichment completed (elapsed=%.2fs)", enrich_elapsed)

    def _step_fetch_chembl(self, context: dict[str, Any], search_type: str | None = "activity") -> None:
        """Search ChEMBL using the query stored in the workflow context."""
        chembl_search = context.get("searches", {}).get("chembl", {})
        query = chembl_search.get("interpreted_query") or chembl_search.get("query")
        query_structure = chembl_search.get("query_structure")
        export_format = chembl_search.get("export_format") or self.default_export_format
        pages_to_fetch = normalize_chembl_pages_to_fetch(chembl_search.get("pages_to_fetch", -1))
        limit = int(chembl_search.get("limit", 1000))
        parse_format = normalize_parse_format(export_format) or "dataframe"
        # Because there is two types of queries assosiated with 2 diferent methods,
        #   we need to check which one to use.
        if not query:
            self.log.debug("Pipeline: empty query for ChEMBL fetch; skipping")
            context["chembl_result"] = pd.DataFrame()
            context.setdefault("metadata", {}).setdefault("chembl", {"skipped_empty_query": True})
            return

        self.log.info("Pipeline: fetching ChEMBL for query=%s search_type=%s", query, search_type)
        instance = ChEMBLInterface()
        activity_filter = None
        fetch_query = query
        fetch_method = f"{search_type}-search" or "activity-search"
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
                    "standard_units_constrained": "standard_units" in activity_filter,
                    "pagination_capped": pages_to_fetch != -1,
                }
                meta["post_fetch_filter"] = post_filter_meta
                meta["data_info"] = instance._build_data_info(result)  # noqa: SLF001  # library-internal helper
        context["data"].setdefault("chembl", result)
        context["metadata"].setdefault("chembl", meta)
        self.log.debug("Pipeline ChEMBL fetch metadata: %s", meta)

    def _step_fetch_pubchem(self, context: dict[str, Any]) -> None:
        """Execute a parsed PubChem request plan and normalize its records."""
        search = context.get("searches", {}).get("pubchem", {})
        request_plan = search.get("request_plan")
        if not isinstance(request_plan, dict):
            msg = "PubChem compound workflow execution requires a request plan."
            raise TypeError(msg)
        fetch_query = build_pubchem_fetch_query(request_plan)
        instance = self.pubchem or PubChemInterface(total_retries=int(search.get("total_retries", 3)))
        self.pubchem = instance
        raw_result, fetch_metadata = instance.fetch_single(
            fetch_query,
            method=PUBCHEM_WORKFLOW_METHOD,
            parse=False,
            format="json",
            workflow_request_plan=request_plan,
        )
        result = normalize_pubchem_records(raw_result, request_plan)
        if result.empty:
            msg = "No PubChem records were returned for the query."
            raise ValueError(msg)
        context.setdefault("data", {})["pubchem"] = result
        update_compound_source_metadata(
            context,
            "pubchem",
            request_plan,
            len(result),
            fetch_metadata,
        )

    def _step_fetch_chebi(self, context: dict[str, Any]) -> None:
        """Execute a parsed ChEBI request plan and normalize its records."""
        search = context.get("searches", {}).get("chebi", {})
        request_plan = search.get("request_plan")
        if not isinstance(request_plan, dict):
            msg = "ChEBI compound workflow execution requires a request plan."
            raise TypeError(msg)
        fetch_spec = build_chebi_fetch_spec(request_plan)
        instance = self.chebi or ChEBIInterface(total_retries=int(search.get("total_retries", 3)))
        self.chebi = instance
        raw_result, fetch_metadata = instance.fetch_single(
            fetch_spec["query"],
            method=fetch_spec["method"],
            parse=False,
            format="json",
            workflow_request_plan=request_plan,
            **fetch_spec["kwargs"],
        )
        result = normalize_chebi_records(raw_result, request_plan)
        if result.empty:
            msg = "No ChEBI records were returned for the query."
            raise ValueError(msg)
        context.setdefault("data", {})["chebi"] = result
        update_compound_source_metadata(
            context,
            "chebi",
            request_plan,
            len(result),
            fetch_metadata,
        )

    def _step_chembl_to_uniprot_query(
        self, context: dict[str, Any], keep_original_query: bool = True
    ) -> None:
        # Build UniProt subquery from ChEMBL results (reuse logic similar to _resolve_chembl_search)
        result = context.get("data", {}).get("chembl")
        ids = []
        if isinstance(result, pd.DataFrame) and not result.empty:
            for col in ("target_chembl_id", "chembl_id", "molecule_chembl_id"):
                if col in result.columns:
                    ids = result[col].dropna().unique().tolist()
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
        """Run the protein modality.

        The most basic form of query is a UniProt query string, e.g. "organism:9606 AND reviewed:true".

        Returns (data, metadata).
        """
        if context is None and query is not None:
            reject_unsupported_protein_source_query(query)

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
                        context.get("metadata", {})
                        .get("uniprot", {})
                        .get("fetch", {})
                        .get("search_process", {})
                        .get("time_taken_seconds", 0),
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
        """Run source-specific compound queries through their supported interfaces.

        Compound workflows keep ChEMBL compound or activity outputs and do not
        automatically map ChEMBL targets back to UniProt. Protein-ligand
        interaction workflows own that cross-entity mapping behavior.

        Args:
            query: The user-friendly compound query string.
            search_type: The type of ChEMBL search to perform. Defaults to "activity".
            export_format: The desired export format for the results. Defaults to None.
            chembl_pages_to_fetch: ChEMBL pages to fetch. Use -1 for all pages.
            context: Optional context dictionary to carry state between steps.
            **kwargs: Additional keyword arguments (currently unused, reserved for future use).

        """
        validate_compound_chembl_query_resource(query)
        chembl_interpreter = build_default_chembl_interpreter()
        export_format = export_format or self.default_export_format
        pages_to_fetch = normalize_chembl_pages_to_fetch(chembl_pages_to_fetch)
        query_structure = build_compound_source_query_structure(query)
        query_source = str(query_structure.get("source")) if query_structure else "chembl"
        total_retries = int(_kwargs.get("total_retries", 3))

        if query_source in PLANNED_COMPOUND_QUERY_SOURCES:
            source_args = {
                "query": query,
                "request_plan": query_structure,
                "export_format": export_format,
                "modality": "compound",
                "total_retries": total_retries,
            }
            if context is None:
                context = {
                    "searches": {query_source: source_args},
                    "data": {},
                    "metadata": {
                        "mode": "query_first",
                        "modality": "compound",
                        "origin": "query",
                    },
                }
            else:
                context.setdefault("searches", {})[query_source] = source_args
                context.setdefault("data", {})
                context.setdefault("metadata", {})
            if query_source == "pubchem":
                self._step_fetch_pubchem(context)
            else:
                self._step_fetch_chebi(context)
            return context.get("data", {}), context.get("metadata", {})

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

        Returns (data, metadata).
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
            reject_unsupported_ppi_source_query(query)
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
            reject_unsupported_pli_source_query(query)
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
        """Interpret `query` and route to the modality-specific handler. Returns (data, metadata)."""
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
                modality_type=None,
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

        Returns (data, metadata).
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
        #   "alphafold_prediction": [pd.DataFrame(...)],  # noqa: ERA001
        #   "pdb_entry": [pd.DataFrame(...)],  # noqa: ERA001
        # }  # noqa: ERA001
        # We need to generate the final output merging every part.
        # RResulting in: { "uniprot": pd.DataFrame(...), "chembl": pd.DataFrame(...), "uniprot_enrichment": {
        # ... } }
        # Merge results depending on their type,
        # For dataframes we concat, for lists we extend, for dicts we create a list of dicts, for ET we create
        # a list of ET.
        if not combined_rows:
            return {}, metadata

        final_main: dict = {}
        for part in combined_rows:
            for key, value in part.items():
                if key not in final_main:
                    final_main[key] = value
                else:
                    existing_value = final_main[key]
                    if isinstance(existing_value, pd.DataFrame) and isinstance(value, pd.DataFrame):
                        final_main[key] = pd.concat([existing_value, value], ignore_index=True)
                    elif isinstance(existing_value, list) and isinstance(value, list):
                        existing_value.extend(value)
                        final_main[key] = existing_value
                    elif (isinstance(existing_value, dict) and isinstance(value, dict)) or (
                        isinstance(existing_value, ET.Element) and isinstance(value, ET.Element)
                    ):
                        final_main[key] = [existing_value, value]
                    else:
                        final_main[key] = [existing_value, value]

        if combined_enrichment:
            enrichment_final: dict = {}
            for enrich_part in combined_enrichment:
                for db_ep, db_data in enrich_part.items():
                    if db_ep not in enrichment_final:
                        enrichment_final[db_ep] = db_data
                    else:
                        existing_data = enrichment_final[db_ep]
                        if isinstance(existing_data, pd.DataFrame) and isinstance(db_data, pd.DataFrame):
                            enrichment_final[db_ep] = pd.concat([existing_data, db_data], ignore_index=True)
                        elif isinstance(existing_data, list) and isinstance(db_data, list):
                            existing_data.extend(db_data)
                            enrichment_final[db_ep] = existing_data
                        elif isinstance(existing_data, dict) and isinstance(db_data, dict):
                            enrichment_final[db_ep] = [existing_data, db_data]
                        else:
                            enrichment_final[db_ep] = [existing_data, db_data]
            final_main["uniprot_enrichment"] = enrichment_final

        return final_main, metadata

    # ---- Helpers ----
    def _step_fetch_additional_ppi_interaction_sources(self, context: dict, **kwargs: Any) -> None:
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
            data=input_data if input_data is not None else pd.DataFrame(),
            format=cast("Literal['json', 'dataframe', 'xml']", export_format),
        )

        context["data"].setdefault("uniprot_enrichment", enriched)
        context["metadata"].setdefault("uniprot_enrichment", enriched_meta)
        self.log.debug("Pipeline additional interaction sources enrichment metadata: %s", enriched_meta)
