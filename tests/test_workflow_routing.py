"""Tests for workflow modality routing behavior."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from bioseq_dl.core.workflow.chembl_query_parser import is_chembl_prefixed_query
from bioseq_dl.core.workflow.main_workflow import (
    COMPOUND_SOURCE_NOT_EXECUTABLE_ERROR,
    PLI_SOURCE_QUERY_ERROR,
    PPI_CHEMBL_QUERY_ERROR,
    PPI_SOURCE_QUERY_ERROR,
    PROTEIN_CHEMBL_QUERY_ERROR,
    PROTEIN_SOURCE_QUERY_ERROR,
    MainWorkflow,
    build_compound_source_query_structure,
)
from bioseq_dl.core.workflow.query_prefixes import (
    get_query_source_prefix,
    is_any_source_prefixed_query,
    is_source_prefixed_query,
    is_supported_source_prefixed_query,
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
        context.setdefault("data", {})["uniprot"] = pd.DataFrame()

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
        context.setdefault("data", {})["chembl"] = pd.DataFrame(
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
        context.setdefault("data", {})["ppi"] = pd.DataFrame()


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
    ("query", "source"),
    [
        ("chembl.target:gene_symbol__iexact=EGFR", "chembl"),
        ('pubchem.compound:name="glucose"', "pubchem"),
        ("chebi.ontology:relation=has_role AND term=metabolite", "chebi"),
    ],
)
def test_shared_query_source_prefix_helpers(query: str, source: str) -> None:
    assert get_query_source_prefix(query) == source
    assert is_source_prefixed_query(query, source)
    assert is_any_source_prefixed_query(query, ("chembl", "pubchem", "chebi"))
    assert is_supported_source_prefixed_query(query)


def test_shared_query_source_prefix_helpers_reject_plain_queries() -> None:
    query = "reviewed:true"

    assert get_query_source_prefix(query) is None
    assert not is_any_source_prefixed_query(query, ("chembl", "pubchem", "chebi"))
    assert not is_supported_source_prefixed_query(query)


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
    ("query", "source"),
    [
        ('pubchem.compound:name="glucose"', "pubchem"),
        ('chebi.entity:name_contains="caffeine"', "chebi"),
    ],
)
def test_protein_rejects_chemical_source_prefixed_queries_before_uniprot(
    query: str,
    source: str,
) -> None:
    workflow = RoutingProbeWorkflow()
    expected_error = PROTEIN_SOURCE_QUERY_ERROR.format(source=source)

    with pytest.raises(ValueError, match=expected_error):
        workflow.run(modality="protein", mode="query_first", query=query)

    assert "fetch_uniprot" not in workflow.calls


def test_chembl_prefixed_query_is_detected_without_truncation() -> None:
    query = "chembl.target:gene_symbol__iexact=EGFR"

    assert is_chembl_prefixed_query(query)
    assert query.startswith("chembl.target:")


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


@pytest.mark.parametrize(
    ("query", "source", "expected_resource"),
    [
        ('pubchem.compound:name="glucose"', "pubchem", "compound"),
        ('chebi.entity:name_contains="caffeine"', "chebi", "entity"),
    ],
)
def test_compound_pubchem_and_chebi_prefixes_are_recognized_but_not_executable(
    query: str,
    source: str,
    expected_resource: str,
) -> None:
    workflow = CompoundNoMappingWorkflow()
    expected_error = COMPOUND_SOURCE_NOT_EXECUTABLE_ERROR.format(source=source)

    plan = build_compound_source_query_structure(query)
    assert plan is not None
    assert plan["source"] == source
    assert plan["resource"] == expected_resource

    with pytest.raises(ValueError, match=expected_error):
        workflow.run(modality="compound", mode="query_first", query=query)

    assert "fetch_uniprot" not in workflow.calls
    assert not any(call.startswith("fetch_chembl") for call in workflow.calls)


def test_compound_workflow_does_not_produce_uniprot_results_by_default() -> None:
    workflow = CompoundNoMappingWorkflow()

    data, _metadata = workflow.run(
        modality="compound",
        mode="query_first",
        query="chembl.molecule:name__iexact=Imatinib",
    )

    assert set(data) == {"chembl"}


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


@pytest.mark.parametrize(
    ("query", "source"),
    [
        ('pubchem.compound:name="glucose"', "pubchem"),
        ("chebi.ontology:relation=has_role AND term=metabolite", "chebi"),
    ],
)
def test_protein_ligand_interaction_rejects_unsupported_chemical_source_query(
    query: str,
    source: str,
) -> None:
    workflow = RoutingProbeWorkflow()
    expected_error = PLI_SOURCE_QUERY_ERROR.format(source=source)

    with pytest.raises(ValueError, match=expected_error):
        workflow.run(
            modality="interaction",
            mode="query_first",
            interaction_type="protein-ligand",
            query=query,
        )

    assert not any(call.startswith("fetch_chembl") for call in workflow.calls)
    assert "fetch_uniprot" not in workflow.calls


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


@pytest.mark.parametrize(
    ("query", "source"),
    [
        ('pubchem.structure:smiles_substructure="c1ccccc1"', "pubchem"),
        ("chebi.ontology:relation=has_role AND term=metabolite", "chebi"),
    ],
)
def test_protein_protein_interaction_rejects_chemical_source_prefixed_query(
    query: str,
    source: str,
) -> None:
    workflow = RoutingProbeWorkflow()
    expected_error = PPI_SOURCE_QUERY_ERROR.format(source=source)

    with pytest.raises(ValueError, match=expected_error):
        workflow.run(
            modality="interaction",
            mode="query_first",
            interaction_type="protein-protein",
            query=query,
        )

    assert "fetch_uniprot" not in workflow.calls
