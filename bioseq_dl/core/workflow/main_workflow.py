from __future__ import annotations

import os
import json
import inspect
import logging
from typing import Any, Callable, Iterable, List, Optional, Tuple, Union, cast, Literal

from xml.etree.ElementTree import ElementTree as ET

import pandas as pd

from bioseq_dl import UniprotInterface, ChEMBLInterface, BioGRIDInterface
from bioseq_dl.core.utils.crossref_enrichment import run_crossref_enrichment
from bioseq_dl.core.crossref_enricher import CrossRefEnricher, EndpointSpec
from bioseq_dl.constants.uniprot import XREF_MAPPING

from .query_interpreter import (
    build_default_uniprot_interpreter, 
    UniProtQueryInterpreter,
    build_default_chembl_interpreter,
)

# Optional logger fallback
try:
    from bioseq_dl.logging import get_logger
except Exception:
    def get_logger(name: str) -> logging.Logger:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        return logging.getLogger(name)

log = get_logger("bioseq_dl.core.workflow.main")


class MainWorkflow:
    """
    High-level workflow orchestrator that exposes three main modes:
      - query_first(query, ...): interpret user-friendly queries, fetch from UniProt, optional enrichment
      - import_first(dataset, ...): load a pre-built dataset (DataFrame or path), optional enrichment
      - query_composition(queries_with_labels, ...): run multiple queries and tag results with labels

    By default this class will instantiate reasonable components so the caller does not need
    to provide any dependencies. All I/O (saving to disk, printing) is left to the caller.

    Optional dependency injection is supported via constructor arguments.
    """

    def __init__(
        self,
        interpreter: Optional[UniProtQueryInterpreter] = None,
        uniprot_interface: Optional[UniprotInterface] = None,
        enricher: Optional[CrossRefEnricher] = None,
        default_export_format: str = "dataframe",
        logger: Optional[logging.Logger] = None,
    ) -> None:
        # Instantiate sensible defaults if not provided
        self.interpreter = interpreter or build_default_uniprot_interpreter()
        self.uniprot = uniprot_interface or UniprotInterface()
        self.enricher = enricher or CrossRefEnricher(endpoint_specs=[])
        self.default_export_format = default_export_format
        self.log = logger or log

        # Debug: show resolved components
        try:
            self.log.debug(
                "MainWorkflow initialized (interpreter=%s, uniprot=%s, enricher=%s, default_export_format=%s)",
                type(self.interpreter).__name__,
                type(self.uniprot).__name__,
                type(self.enricher).__name__,
                self.default_export_format,
            )
        except Exception:
            # Avoid breaking if logger misbehaves
            pass

        # NOTE: declarative pipelines and custom step overrides are disabled for now.
        # Future work: reintroduce `self.pipelines` and `self.step_overrides` for custom pipelines.
        # TODO: Consider normalizing the metadata structure returned by all public methods.
        # Currently metadata is a flexible dict that mixes counters, nested parts, and
        # enrichment outputs (sometimes lists/dicts). Plan: decide on a stable schema
        # (e.g. {'mode':..., 'results':..., 'enrichment':..., 'parts':...}) and migrate
        # query_first/import_first/query_composition to always return (data, metadata)
        # with a consistent metadata shape. Leaving this as a TODO until the CLI/PRISM
        # integration decisions are final.

    # Public run entry that routes by mode
    def run(
            self, 
            modality: str, 
            mode: str = "query_first", 
            **kwargs
        ) -> Tuple[Any, dict]:
        """
        Primary public entry. modality is mandatory and selects the declarative
        pipeline to use (e.g. 'protein', 'compound', 'interaction'). `mode` keeps
        backward-compatible routing semantics but modality must always be provided.

        Examples:
          run('protein', mode='query_first', query='...')
          run('interaction', mode='query_composition', queries_with_labels=[...])
        
        Args:
            modality: The modality to run ('protein', 'compound', 'interaction').
            mode: The mode to run ('query_first', 'import_first', 'query_composition').
            **kwargs: Additional arguments passed to the selected mode handler.
        """
        if not modality:
            raise ValueError("`modality` is required for MainWorkflow.run")

        modality = modality.lower()
        mode = (mode or "").lower()
        # Debug: log entry into workflow run with provided parameters
        try:
            self.log.debug("Run invoked with mode=%s modality=%s kwargs=%s", mode, modality, kwargs)
        except Exception:
            pass

        if mode == "query_first":
            return self.query_first(modality=modality, **kwargs)
        if mode == "import_first":
            return self.import_first(modality=modality, **kwargs)
        if mode == "query_composition":
            return self.query_composition(modality=modality, **kwargs)
        raise ValueError(f"Unknown mode: {mode}")


    # ---- Pipeline step implementations ----
    def _step_interpret(self, context: dict) -> None:
        args = context.get("args", {})
        # If interpreted_query already present in context, do not re-interpret to avoid
        # overwriting or alias-rewriting (e.g., 'xref:' -> 'database:') produced by later
        # pipeline stages such as compound -> chembl -> uniprot. This preserves the
        # subquery built from ChEMBL IDs.
        if context.get("interpreted_query"):
            # Ensure crossref fields are present for enrichment steps if missing
            if "additional_crossref_fields" not in context:
                query = args.get("query")
                if query:
                    crossref_fields = self.interpreter.extract_databases(query)
                    context["additional_crossref_fields"] = crossref_fields
            return

        query = args.get("query")
        if not query:
            return
        # Get the main query
        interpreted = self.interpreter.interpret(query)
        context["interpreted_query"] = interpreted
        # Get crossref fields
        crossref_fields = self.interpreter.extract_databases(query)
        context["additional_crossref_fields"] = crossref_fields
        # Get additional searches (e.g., ChEMBL)
        # additional_searches = self.interpreter.extract_additional_searches(query)
        # context.setdefault("metadata", {})["additional_searches"] = additional_searches

        self.log.debug("Interpreted query: %s", interpreted)
        self.log.debug("Additional crossref fields: %s", crossref_fields)

    def _step_fetch_uniprot(self, context: dict) -> None:
        args = context.get("args", {})
        interpreted = context.get("searches", {}).get("uniprot", {}).get("interpreted_query") or args.get("query")
        # Defensive: do not call Uniprot with None/empty query
        if not interpreted:
            self.log.debug("Pipeline: empty/uninterpreted query provided to _step_fetch_uniprot; skipping fetch")
            context["response"] = []
            context.setdefault("metadata", {}).setdefault("fetch", {}).update({"uniprot": {"skipped_empty_query": True}})
            return
        fields = args.get("fields", "")
        sort = args.get("sort", "accession asc")
        include_isoform = args.get("include_isoform", False)
        
        if isinstance(interpreted, list):
            # Multiple queries: fetch each and combine results
            combined_response = {}
            combined_fetch_meta = {}
            for q in interpreted:
                self.log.info("Pipeline: fetching UniProt for query=%s fields=%s", q, fields)
                resp, fetch_meta = self.uniprot.submit_stream(query=q, fields=(fields or ""), sort=sort, include_isoform=include_isoform)
                combined_response["results"] = combined_response.get("results", []) + (resp.get("results", []) if isinstance(resp, dict) else [])
                combined_fetch_meta[q] = fetch_meta if isinstance(fetch_meta, dict) else {}
            response = combined_response
            fetch_meta = combined_fetch_meta
        else:
            self.log.info("Pipeline: fetching UniProt for query=%s fields=%s", interpreted, fields)
            response, fetch_meta = self.uniprot.submit_stream(query=interpreted, fields=(fields or ""), sort=sort, include_isoform=include_isoform)
        # Always store the latest response under context['data']['uniprot'] (setdefault would not overwrite existing value)
        context.setdefault("data", {})["uniprot"] = response
        context.setdefault("metadata", {}).setdefault("uniprot", {}).update({"fetch": fetch_meta if isinstance(fetch_meta, dict) else {}})
        self.log.debug("Pipeline UniProt fetch metadata: %s", fetch_meta)

    def _step_parse_uniprot(self, context: dict) -> None:
        format = context.get("args", {}).get("export_format") or self.default_export_format
        resp_val = context.get("data", {}).get("uniprot")
        response = resp_val if resp_val is not None else {}
        # cast fmt to Any to avoid strict Literal typing issues when passing runtime variables
        try:
            data, parse_meta = self.uniprot.parse(results=response, extract_fields=None, format=cast(Any, format))
            context["data"]["uniprot"] = data
            context.setdefault("metadata", {}).setdefault("uniprot", {}).setdefault("parsing", parse_meta if isinstance(parse_meta, dict) else {})
            self.log.debug("Pipeline UniProt parse metadata: %s", parse_meta)
        except Exception as e:
            # Defensive: some upstream parsers may evaluate DataFrames in boolean context
            # (e.g., `if results:`) which raises ValueError("The truth value of a DataFrame is ambiguous").
            # Catch any parse error, record it and continue with an empty DataFrame so the
            # workflow can proceed without crashing.
            self.log.warning("_step_parse: parser failed: %s; setting empty DataFrame", e)
            context["data"]["uniprot"] = pd.DataFrame()
            context.setdefault("metadata", {}).setdefault("uniprot", {}).setdefault("parsing", {"error": str(e)})
            return

    def _step_crossref_enrich(self, context: dict, **kwargs) -> None:
        args = context.get("searches", {}).get("uniprot", {})
        input_data = context.get("data", {}).get("uniprot")
        cross_ref_fields = args.get("additional_crossref_fields") or []
        enrich_flag = args.get("enrich", False)
        export_format = args.get("export_format") or self.default_export_format
        max_workers = kwargs.get("max_workers", 4)
        total_retries = kwargs.get("total_retries", 3)

        if not enrich_flag:
            self.log.debug("Pipeline: enrichment skipped (enrich=False)")
            return

        self.log.info("Pipeline: performing CrossRef enrichment with fields=%s", cross_ref_fields)
        enriched, enriched_meta = run_crossref_enrichment(
            data=input_data if input_data is not None else pd.DataFrame(),
            crossref_fields=cross_ref_fields.split(",") if isinstance(cross_ref_fields, str) else cross_ref_fields,
            format=cast(Literal["json", "dataframe", "xml"], export_format),
            max_workers=max_workers,
            total_retries=total_retries
        )
        context["data"].setdefault("uniprot_enrichment", enriched)
        context.setdefault("metadata", {}).setdefault("uniprot_enrichment", enriched_meta)
        self.log.debug("Pipeline enrichment metadata: %s", enriched_meta)

    def _step_fetch_chembl(self, context: dict, search_type: Optional[str] = "activity") -> None:
        '''
        Searches ChEMBL for queries found in context['searches']['chembl'].
        '''
        chembl_search = context.get("searches", {}).get("chembl", {})
        query = chembl_search.get("interpreted_query") or chembl_search.get("query")
        export_format = chembl_search.get("export_format") or self.default_export_format
        # Because there is two types of queries assosiated with 2 diferent methods,
        #   we need to check which one to use.
        if not query:
            self.log.debug("Pipeline: empty query for ChEMBL fetch; skipping")
            context["chembl_result"] = pd.DataFrame()
            context.setdefault("metadata", {}).setdefault("chembl", {"skipped_empty_query": True})
            return
        
        self.log.info("Pipeline: fetching ChEMBL for query=%s search_type=%s", query, search_type)
        instance = ChEMBLInterface()
        result, meta = instance.fetch_single(
            query=query,
            method=f"{search_type}-search" or "activity-search",
            parse=True,
            format=cast(Any, export_format),
            pages_to_fetch=-1,
            limit=100
        )
        context["data"].setdefault("chembl", result)
        context["metadata"].setdefault("chembl", meta)
        self.log.debug("Pipeline ChEMBL fetch metadata: %s", meta)

    def _step_chembl_to_uniprot_query(self, context: dict, keep_original_query: bool = True) -> None:
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
        if len(ids) > 100:
            self.log.warning("Pipeline: large number of ChEMBL IDs (%s); UniProt query may be too long", len(ids))
            self.log.info("Searches will be divided into chunks of 100 IDs")
            output_list = []
            for i in range(0, len(ids), 100):
                chunk_ids = ids[i:i+100]
                chunk_query = "(" + " OR ".join([f"xref:chembl-{i}" for i in chunk_ids]) + ")"
                # attatch or extend existing interpreted_query for each chunk
                prev = context.get("searches", {}).get("uniprot", {}).get("query") if keep_original_query else None
                if prev:
                    new_query = f"{prev} AND {chunk_query}"
                else:
                    new_query = chunk_query
                output_list.append(new_query)
            context["searches"]["uniprot"]["query"] = output_list
            self.log.debug("Pipeline built UniProt subqueries from ChEMBL IDs in %s chunks", len(output_list))
        else:
            out = "(" + " OR ".join([f"xref:chembl-{i}" for i in ids]) + ")"
            # attach or extend existing interpreted_query
            prev = context.get("searches", {}).get("uniprot", {}).get("query") 
            if prev and keep_original_query:
                new_query = f"{prev} AND {out}"
            else:
                new_query = out
            context["searches"]["uniprot"]["query"] = new_query
            self.log.debug("Pipeline built UniProt subquery from ChEMBL IDs: %s", out)

    def _step_build_interactions(self, context: dict) -> None:
        """Transform fetched candidates into an interactions dataset. Minimal default behaviour:
        - If Biogrid response is a DataFrame, return as-is
        - If ChEMBL response, attempt to build protein-ligand mapping via target_chembl_id -> xref:chembl-...
        Users can override via `self.step_overrides['build_interactions']`.
        """
        resp = context.get("response")
        if isinstance(resp, pd.DataFrame):
            context["data"] = resp
            return
        if isinstance(resp, list):
            context["data"] = resp
            return
        # Fallback empty
        context["data"] = pd.DataFrame()

    # ---- Core modes ----
    def run_protein(
        self,
        query: Optional[str] = None,
        fields: Optional[str] = None,
        sort: str = "accession asc",
        include_isoform: bool = False,
        export_format: Optional[str] = None,
        enrich: bool = False,
        crossref_endpoint_specs: Optional[List[EndpointSpec]] = None,
        context: Optional[dict] = None,
        **kwargs,
    ) -> Tuple[dict, dict]:
        """Run the protein modality.
        The most basic form of query is a UniProt query string, e.g. "organism:9606 AND reviewed:true".


        Returns (data, metadata).
        """
        uniprot_interpreter = build_default_uniprot_interpreter()

        export_format = export_format or self.default_export_format

        args = {
            "query": query,
            "interpreted_query": None,
            "additional_crossref_fields": None,
            "fields": fields or "",
            "sort": sort,
            "include_isoform": include_isoform,
            "export_format": export_format,
            "enrich": enrich,
            "crossref_endpoint_specs": crossref_endpoint_specs,
        }
        if context is not None:
            existing_args = context.get("searches", {}).get("uniprot", {}) or {}
            # Only override keys that are not None from this call
            override = {k: v for k, v in args.items() if v is not None}
            context["searches"]["uniprot"] = {**existing_args, **override}
        else:
            context = {"searches": {"uniprot": args}, "data": {"uniprot": {}}, "metadata": {"mode": "protein", "origin": "query"}}
            context["searches"]["uniprot"]["interpreted_query"] = uniprot_interpreter.interpret(query=args.get("query", ""))
           
        context["searches"]["uniprot"]["additional_crossref_fields"] = uniprot_interpreter.extract_databases(
            query=context["searches"]["uniprot"].get("query", "")
        )

        self._step_fetch_uniprot(context)
        self._step_parse_uniprot(context)
        self._step_crossref_enrich(context, **kwargs)

        return context["data"], context.get("metadata") or {}

    def run_compound(
        self,
        query: str,
        search_type: Optional[str] = "activity",
        export_format: Optional[str] = None,
        context: Optional[dict] = None,
        **kwargs,
    ) -> Tuple[dict, dict]:
        """
        Run the compound modality. Query path goes through ChEMBL -> UniProt.
        Some queries can include just ChEMBL searches or ChEMBL + UniProt searches.
        For example we can search:
        - By target: "Proteases" or "dopamine D2 receptor"
        - By activity: "IC50:<1000" or "Ki:<50"

        Args:
            query: The user-friendly compound query string.
            search_type: The type of ChEMBL search to perform. Defaults to "activity".
            export_format: The desired export format for the results. Defaults to None.
            context: Optional context dictionary to carry state between steps.

            Returns (data, metadata).
        """
        chembl_interpreter = build_default_chembl_interpreter()
        uniprot_interpreter = build_default_uniprot_interpreter()
        export_format = export_format or self.default_export_format

        args = {
            "query": query,
            "interpreted_query": None,
            "export_format": export_format,
            "search_type": search_type,
            "mode": "compound"
        }
        if context is None:
            context = {
                "searches": {
                    "chembl": args,
                    "uniprot": {
                        "query": None,
                    }
                },
                "data": {},
                "metadata": {}
            }
        else:
            # Merge explicit function args into existing context args so callers that pass
            # a prepared context (e.g. run_interaction) have their desired parameters honored.
            existing_searches = context.get("searches") or {}
            # Only override keys that are not None from this call
            override = {k: v for k, v in args.items() if v is not None}
            merged = {**existing_searches, **override}
            context["searches"] = merged


        # Interpret original compound query
        context["searches"]["chembl"]["interpreted_query"] = chembl_interpreter.interpret(query=args.get("query", ""))

        # Fetch ChEMBL results
        self._step_fetch_chembl(context, search_type=search_type)
        # Build UniProt-compatible subquery from ChEMBL IDs (if any)
        self._step_chembl_to_uniprot_query(context)

        uniprot_query = context.get("searches", {}).get("uniprot", {}).get("query")
        if not uniprot_query:
            self.log.debug("Pipeline: no UniProt query generated from ChEMBL IDs")
            return context["data"], context.get("metadata", {})
        
        # Interpret UniProt query and append to ChEMBL IDs search
        chembl_ids_query = context["searches"]["uniprot"]["query"]
        # We extract the UniProt part of the original query
        interpreted_uniprot_query = uniprot_interpreter.interpret(query=query)

        combined_queries: str | List[str] = []
        if chembl_ids_query and isinstance(chembl_ids_query, list):
            for chembl_query in chembl_ids_query:
                if interpreted_uniprot_query:
                    combined_query = f"({interpreted_uniprot_query}) AND {chembl_query}"
                else:
                    combined_query = chembl_query
                combined_queries.append(combined_query)
        else:
            combined_queries = f"({interpreted_uniprot_query}) AND {chembl_ids_query}" if interpreted_uniprot_query else chembl_ids_query
            
        # Combine both queries
        context["searches"]["uniprot"] = {
            "query": query,
            "interpreted_query": combined_queries,
            "export_format": export_format,
        }

        run_protein_sig = inspect.signature(self.run_protein)
        run_protein_args = {
            k: v for k, v in kwargs.items() if k in run_protein_sig.parameters
        }

        return self.run_protein(context=context, **run_protein_args)

    def run_interaction(
        self,
        query: str,
        interaction_type: Optional[Literal["protein-protein", "protein-ligand"]] = None,
        export_format: Optional[str] = None,
        **kwargs,
    ) -> Tuple[dict, dict]:
        """
        Run the interaction modality. If query provided, fetch interaction candidates (BioGRID/ChEMBL) 
        and build interactions dataset.
        This will do more than 1 search if needed (e.g., ChEMBL + UniProt).
        For example:
        - "pli:'Proteases' AND {uniprot_filter_query}" 
        Will search in ChEMBL using the query "target:'Proteases' AND {uniprot_filter_query}", 
          extract the ChEMBL IDs, then search UniProt for those IDs.
          A new request will be made to UniProt, merging the uniprot_filter_query and the IDs from ChEMBL.
        - "ppi: 'disease:cancer' AND {uniprot_filter_query}"
        Will search in UniProt for the PPI query, additional BioGRID search will be made to fetch interactions.
          In this specific example all the query will be sent to UniProt since it supports disease and all
          the necessary filters. From BioGRID only interactions will be fetched for the resulting accessions.
        

        Returns (data, metadata).
        """

        # ====== Short PPI search explanation ======
        # After searching UniProt with a desired query (e.g., "disease:cancer AND reviewed:true"),
        # We get a list of columns that we can use to retrieve data from different databases.
        # For example,
        # string_ids: '9606.ENSP00000269305' (from STRING database) can be used to get interactions giving us gene_a vs gene_b and score
        # biogrid_ids: '108356' (from BioGRID database) can be used to get interactions giving us gene_a vs gene_b and experimental details
        # ====== Short PLI search explanation ======
        # We do a similar approach for PLI, but we use ChEMBL to get the interactions with a target.
        # After that we search UniProt for the target details.
        if not interaction_type:
            raise ValueError("interaction_type is required for run_interaction")

        export_format = export_format or self.default_export_format

        uniprot_interpreter = build_default_uniprot_interpreter()
        chembl_interpreter = build_default_chembl_interpreter()
        
        args = {
            "query": query,
            "export_format": export_format,
            "interaction_type": interaction_type,
            "mode": "interaction"
        }
        context = {
            "searches": {
                "uniprot": args,
            },
            "data": {},
            "metadata": {"mode": "interaction", "origin": "query"}
        }


        # Fetch interaction candidates
        if interaction_type == "protein-protein":
            # Interpret original interaction query
            context["searches"]["uniprot"]["interpreted_query"] = uniprot_interpreter.interpret(query=args.get("query", ""))
            # For PPI, we first search UniProt to get accessions matching the query,
            # then use those accessions to fetch interactions from BioGRID and StringDB.
            self._step_fetch_uniprot(context)
            self._step_parse_uniprot(context)
            # Instead of doing a enrichment we use another method to fetch specific endpoint from Biogrid and StringDB.
            self._step_fetch_additional_ppi_interaction_sources(context, **kwargs)

            return context.get("data") or {}, context.get("metadata") or {}
        elif interaction_type == "protein-ligand":
            context["searches"]["chembl"] = {
                "query": query,
                "export_format": export_format,
                "search_type": "target",
            }
            # Interpret original interaction query
            context["searches"]["chembl"]["interpreted_query"] = chembl_interpreter.interpret(query=args.get("query", ""))
            # For PLI, we first search ChEMBL to get compounds/targets matching the query,
            self._step_fetch_chembl(context, search_type="target")
            # then use those targets to fetch UniProt details.
            self._step_chembl_to_uniprot_query(context, keep_original_query=False)
            uniprot_query = context.get("searches", {}).get("uniprot", {}).get("query")
            if not uniprot_query:
                self.log.debug("Pipeline: no UniProt query generated from ChEMBL IDs for PLI")
                return context["data"], context.get("metadata", {})
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
        fields: Optional[str] = None,
        sort: str = "accession asc",
        include_isoform: bool = False,
        export_format: Optional[str] = None,
        enrich: bool = False,
        crossref_endpoint_specs: Optional[List[EndpointSpec]] = None,
        search_type: Optional[str] = "activity",
        interaction_type: Optional[str] = None,
        **kwargs,
    ) -> Tuple[dict, dict]:
        """Interpret `query` and dispatch to modality-specific handler. Returns (data, metadata)."""
        modality = (modality or "").lower()
        if modality == "protein":
            return self.run_protein(query=query, fields=fields, sort=sort, include_isoform=include_isoform, export_format=export_format, enrich=enrich, crossref_endpoint_specs=crossref_endpoint_specs, **kwargs)
        if modality == "compound":
            return self.run_compound(query=query, fields=fields, export_format=export_format, enrich=enrich, crossref_endpoint_specs=crossref_endpoint_specs, search_type=search_type, **kwargs)
        if modality == "interaction":
            return self.run_interaction(query=query, modality_type=None, export_format=export_format, enrich=enrich, crossref_endpoint_specs=crossref_endpoint_specs, interaction_type=interaction_type, **kwargs)
        raise ValueError(f"Unknown modality: {modality}")

    def import_first(
        self,
        modality: str,
        dataset: Union[pd.DataFrame, str],
        dataset_format: Optional[str] = None,
        enrich: bool = False,
        crossref_endpoint_specs: Optional[List[EndpointSpec]] = None,
        **kwargs,
    ) -> Tuple[dict, dict]:
        """Load a dataset and dispatch to modality-specific handler. Returns (data, metadata)."""
        raise NotImplementedError("Import first not implemented yet.")

    def query_composition(
        self,
        modality: str,
        queries_with_labels: Iterable[Tuple[str, str]],
        fields: Optional[str] = None,
        export_format: Optional[str] = None,
        enrich: bool = False,
        crossref_endpoint_specs: Optional[List[EndpointSpec]] = None,
        search_type: Optional[str] = "activity",
        **kwargs,
    ) -> Tuple[dict, dict]:
        """
        Run several queries and tag every row with the provided label. 
        This requires a more complex query composition, for example:
            queries_with_labels = [
                ("Proteases AND reviewed:true", "protease_reviewed"),
                ("Kinases AND reviewed:false", "kinase_unreviewed"),
            ]
        Basically it runs several query_first calls and attach the label to every row.
    
        Returns (data, metadata).
        """
        combined_rows: List[Any] = []
        combined_enrichment: List[Any] = []
        metadata: dict = {"mode": "query_composition", "origin": "query", "parts": []}

        for query, label in queries_with_labels:
            if modality == "protein":
                part_data, part_meta = self.run_protein(query=query, fields=fields, export_format=export_format, enrich=enrich, crossref_endpoint_specs=crossref_endpoint_specs, **kwargs)
            elif modality == "compound":
                part_data, part_meta = self.run_compound(query=query, fields=fields, export_format=export_format, enrich=enrich, crossref_endpoint_specs=crossref_endpoint_specs, search_type=search_type, **kwargs)
            elif modality == "interaction":
                part_data, part_meta = self.run_interaction(query=query, export_format=export_format, enrich=enrich, crossref_endpoint_specs=crossref_endpoint_specs, **kwargs)
            else:
                raise ValueError(f"Unknown modality: {modality}")

            # Note: Normally, at this point the body of part data should be
            #  {"uniprot": pd.DataFrame(...), "uniprot_enrichment": {...}} for protein modality,
            #  {"chembl": pd.DataFrame(...), "uniprot": pd.DataFrame(...), "uniprot_enrichment": {...}} for compound modality
            # On the other hand, part_meta should contain the metadata for that specific run
            #  {"mode": "protein", "origin": "query", "uniprot": {...}, "uniprot_enrichment": {...}} for protein modality,
            #  {"mode": "compound", "origin": "query",  "chembl": {...}, "uniprot": {...}, "uniprot_enrichment": {...}} for compound modality 

            # Attach label
            def attach_label_to_part(part_data: dict, label: str, modality: str) -> dict:
                # Depending if protein or compound was run, the data can be diferent.
                # For example, for run_protein, the label should be attached on the part_data["data"]["uniprot"] dataframe.
                # While for run_compound, the label should be attached on the part_data["data"]["chembl"] dataframe.
                data_to_label = None
                key = None
                if isinstance(part_data, dict):
                    if modality == "protein" and part_data.get("uniprot") is not None:
                        key = "uniprot"
                        data_to_label = part_data.get("uniprot")
                    elif modality == "compound" and part_data.get("chembl") is not None:
                        key = "chembl"
                        data_to_label = part_data.get("chembl")
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
                    else:
                        return {key: data_to_label}
                return {}

            labeled_part = attach_label_to_part(part_data, label, modality)
            if isinstance(labeled_part, dict):
                combined_rows.append(labeled_part)

            # Handle enrichment data
            def merge_enrichment_data(existing: List[Any], new: Any) -> List[Any]:
                # Uniprot enrichment is separated in {database}_{endpoint} so for every
                # every one we combine the data without attaching any label
                # For example:
                # {
                #   "alphafold_prediciton": pd.DataFrame(...),
                #   "pdb_entry": pd.DataFrame(...),
                # }
                # Every iteration should have
                # {
                #   "alphafold_prediciton": pd.DataFrame(..., ...),
                #   "pdb_entry": None
                # }
                # This should be merged in a way that the final result should have only 1
                # instance of every database_endpoint with all the data combined.
                # Also dict, list and ET types should be handled.
                # Merges new enrichment data into existing list
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

            enrichment_data = part_data.get("uniprot_enrichment") if isinstance(part_data, dict) else None
            if enrichment_data:
                combined_enrichment = merge_enrichment_data(combined_enrichment, enrichment_data)
                
            metadata["parts"].append({"query": query, "label": label, "meta": part_meta})


        
        # Combined_rows now contains only the labeled data parts in a list.
        # For example
        # { "uniprot": [...], "chembl": [...] }
        # On the other hand, combined_enrichment contains only the enrichment data combined.
        # For example
        # {
        #   "alphafold_prediction": [pd.DataFrame(...)],
        #   "pdb_entry": [pd.DataFrame(...)],
        # }
        # We need to generate the final output merging every part.
        # RResulting in: { "uniprot": pd.DataFrame(...), "chembl": pd.DataFrame(...), "uniprot_enrichment": { ... } }
        # Merge results depending on their type,
        # For dataframes we concat, for lists we extend, for dicts we create a list of dicts, for ET we create a list of ET.
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
                    elif isinstance(existing_value, dict) and isinstance(value, dict):
                        final_main[key] = [existing_value, value]
                    elif isinstance(existing_value, ET.Element) and isinstance(value, ET.Element):
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
    def _step_fetch_additional_ppi_interaction_sources(self, context: dict, **kwargs) -> None:
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
            specs.append(
                EndpointSpec(
                    database="biogrid",
                    endpoint="interactions"
                )
            )
        else:
            self.log.debug("No biogrid_ids column found in input data; skipping BioGRID interaction fetch")
        # Fetch StringDB interactions
        if "string_ids" in input_data.columns:
            specs.append(
                EndpointSpec(
                    database="string",
                    endpoint="interaction_partners"
                )
            )
        else:
            self.log.debug("No string_ids column found in input data; skipping StringDB interaction fetch")
        
        crossref_enricher = CrossRefEnricher(
            endpoint_specs=specs,
            max_workers=max_workers,
            total_retries=total_retries
        )
        enriched, enriched_meta = crossref_enricher.enrich(
            data=input_data if input_data is not None else pd.DataFrame(),
            format=cast(Literal["json", "dataframe", "xml"], export_format)
        )

        context["data"].setdefault("uniprot_enrichment", enriched)
        context.setdefault("metadata", {}).setdefault("uniprot_enrichment", enriched_meta)
        self.log.debug("Pipeline additional interaction sources enrichment metadata: %s", enriched_meta)
