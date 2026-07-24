"""Tests for workflow modality routing behavior."""

from __future__ import annotations

from typing import Any

import polars as pl
import pytest

from silkroute.core.workflow.main_workflow import (
    PPI_CHEMBL_QUERY_ERROR,
    PROTEIN_CHEMBL_QUERY_ERROR,
    MainWorkflow,
)


class RoutingProbeWorkflow(MainWorkflow):
    """Workflow test double that records step calls without network access."""

    def __init__(self) -> None:
        """Initialize the routing probe."""
        super().__init__()
        self.calls: list[str] = []
        self.last_chembl_context: dict[str, Any] | None = None

    def _step_fetch_uniprot(self, context: dict[str, Any]) -> None:
        """Record UniProt fetch calls."""
        self.calls.append("fetch_uniprot")
        context.setdefault("data", {})["uniprot"] = {"results": []}

    def _step_parse_uniprot(self, context: dict[str, Any]) -> None:
        """Record UniProt parse calls."""
        self.calls.append("parse_uniprot")
        context.setdefault("data", {})["uniprot"] = pl.DataFrame()

    def _step_crossref_enrich(self, context: dict[str, Any], **_kwargs: Any) -> None:
        """Record cross-reference enrichment calls."""
        self.calls.append("crossref_enrich")

    def _step_fetch_chembl(
        self,
        context: dict[str, Any],
        search_type: str | None = "activity",
    ) -> None:
        """Record ChEMBL fetch calls."""
        self.calls.append(f"fetch_chembl:{search_type}")
        self.last_chembl_context = context
        context.setdefault("data", {})["chembl"] = pl.DataFrame(
            [{"target_chembl_id": "CHEMBL279", "molecule_chembl_id": "CHEMBL25"}]
        )
        context.setdefault("metadata", {})["chembl"] = {"mocked": True}

    def _step_chembl_to_uniprot_query(
        self,
        context: dict[str, Any],
        keep_original_query: bool = True,
    ) -> None:
        """Record ChEMBL-to-UniProt mapping calls."""
        self.calls.append(f"chembl_to_uniprot:{keep_original_query}")
        context.setdefault("searches", {}).setdefault("uniprot", {})["query"] = "xref:chembl-CHEMBL279"

    def _step_fetch_additional_ppi_interaction_sources(
        self,
        context: dict[str, Any],
        **_kwargs: Any,
    ) -> None:
        """Record PPI enrichment source calls."""
        self.calls.append("fetch_ppi_sources")
        context.setdefault("data", {})["ppi"] = pl.DataFrame()


class CompoundNoMappingWorkflow(RoutingProbeWorkflow):
    """Workflow probe that fails if compound routing attempts UniProt mapping."""

    def _step_chembl_to_uniprot_query(
        self,
        context: dict[str, Any],
        keep_original_query: bool = True,
    ) -> None:
        """Fail if compound workflows call ChEMBL-to-UniProt mapping."""
        msg = "Compound workflows must not map ChEMBL IDs to UniProt."
        raise AssertionError(msg)


@pytest.mark.parametrize(
    "query",
    [
        "chembl.target:gene_symbol__iexact=EGFR",
        "chembl.activity:target_chembl_id=CHEMBL279",
    ],
)
def test_protein_rejects_chembl_prefixed_queries_before_uniprot(query: str) -> None:
    workflow = RoutingProbeWorkflow()

    with pytest.raises(ValueError, match=PROTEIN_CHEMBL_QUERY_ERROR):
        workflow.run(modality="protein", mode="query_first", query=query)

    assert "fetch_uniprot" not in workflow.calls


@pytest.mark.parametrize(
    ("query", "expected_search_type"),
    [
        ("chembl.activity:target_chembl_id=CHEMBL279 AND pchembl_value=5.83", "activity"),
        ("chembl.molecule:name__iexact=Imatinib", "molecule"),
    ],
)
def test_compound_chembl_queries_route_to_chembl_without_uniprot(
    query: str,
    expected_search_type: str,
) -> None:
    workflow = CompoundNoMappingWorkflow()

    data, _metadata = workflow.run(modality="compound", mode="query_first", query=query)

    assert f"fetch_chembl:{expected_search_type}" in workflow.calls
    assert "fetch_uniprot" not in workflow.calls
    assert "uniprot" not in data
    assert "chembl" in data
    assert workflow.last_chembl_context is not None
    chembl_search = workflow.last_chembl_context["searches"]["chembl"]
    assert chembl_search["query"] == query
    assert chembl_search["interpreted_query"] == query
    assert chembl_search["query_structure"]["resource"] == expected_search_type


def test_compound_target_query_is_rejected_without_uniprot() -> None:
    workflow = CompoundNoMappingWorkflow()

    with pytest.raises(ValueError, match="not valid for compound workflows"):
        workflow.run(
            modality="compound",
            mode="query_first",
            query="chembl.target:gene_symbol__iexact=EGFR",
        )

    assert "fetch_uniprot" not in workflow.calls


def test_protein_ligand_interaction_can_use_chembl_to_uniprot_mapping() -> None:
    workflow = RoutingProbeWorkflow()

    data, _metadata = workflow.run(
        modality="interaction",
        mode="query_first",
        interaction_type="protein-ligand",
        query="chembl.target:gene_symbol__iexact=EGFR",
    )

    assert "fetch_chembl:target" in workflow.calls
    assert "chembl_to_uniprot:False" in workflow.calls
    assert "fetch_uniprot" in workflow.calls
    assert "uniprot" in data


def test_protein_protein_interaction_preserves_uniprot_oriented_behavior() -> None:
    workflow = RoutingProbeWorkflow()

    workflow.run(
        modality="interaction",
        mode="query_first",
        interaction_type="protein-protein",
        query="reviewed:true",
    )

    assert "fetch_uniprot" in workflow.calls
    assert "parse_uniprot" in workflow.calls
    assert "fetch_ppi_sources" in workflow.calls
    assert not any(call.startswith("fetch_chembl") for call in workflow.calls)


def test_protein_protein_interaction_rejects_chembl_prefixed_query() -> None:
    workflow = RoutingProbeWorkflow()

    with pytest.raises(ValueError, match=PPI_CHEMBL_QUERY_ERROR):
        workflow.run(
            modality="interaction",
            mode="query_first",
            interaction_type="protein-protein",
            query="chembl.activity:target_chembl_id=CHEMBL279",
        )

    assert "fetch_uniprot" not in workflow.calls
