"""Offline tests for ChEBI compound workflow execution."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from bioseq_dl.cli.workflows import export_workflow_outputs
from bioseq_dl.core.workflow.main_workflow import MainWorkflow


class FakeChEBIInterface:
    """Record ChEBI workflow calls and return frozen entity records."""

    def __init__(self, records: object = None) -> None:
        self.records = (
            records if records is not None else {"chebi_accession": "CHEBI:27732", "name": "caffeine"}
        )
        self.calls: list[dict[str, Any]] = []

    def fetch_single(self, query: object, **kwargs: Any) -> tuple[object, dict]:
        self.calls.append({"query": query, "kwargs": kwargs})
        return self.records, {"api_name": "ChEBI", "method": kwargs.get("method")}


@pytest.mark.parametrize(
    ("query", "expected_method", "expected_interface_query"),
    [
        ("chebi.entity:chebi_id=CHEBI:15377", "compound", "CHEBI:15377"),
        (
            'chebi.entity:name_contains="caffeine"',
            "es_search",
            {"term": "caffeine", "page": 1, "size": 100},
        ),
    ],
)
def test_compound_chebi_query_dispatches_to_chebi_interface(
    query: str,
    expected_method: str,
    expected_interface_query: object,
) -> None:
    interface = FakeChEBIInterface()
    workflow = MainWorkflow(chebi_interface=interface)

    data, metadata = workflow.run(modality="compound", mode="query_first", query=query)

    assert set(data) == {"chebi"}
    assert isinstance(data["chebi"], pd.DataFrame)
    assert interface.calls[0]["query"] == expected_interface_query
    assert interface.calls[0]["kwargs"]["method"] == expected_method
    assert interface.calls[0]["kwargs"]["workflow_request_plan"] == metadata["request_plan"]
    assert metadata["query_source"] == "chebi"
    assert metadata["number_of_records"] == 1


@pytest.mark.parametrize(
    ("query", "message"),
    [
        (
            'chebi.entity:formula="C8H10N4O2"',
            "ChEBI entity parameters 'formula' are not executable yet",
        ),
        (
            "chebi.ontology:relation=has_role AND term=metabolite",
            "ChEBI ontology search is not executable yet",
        ),
        (
            'chebi.structure:substructure="c1ccccc1"',
            "ChEBI structure search is not executable yet",
        ),
    ],
)
def test_chebi_pending_query_models_fail_clearly(query: str, message: str) -> None:
    workflow = MainWorkflow(chebi_interface=FakeChEBIInterface())

    with pytest.raises(ValueError, match=message):
        workflow.run(modality="compound", mode="query_first", query=query)


def test_chebi_workflow_rejects_empty_results() -> None:
    workflow = MainWorkflow(chebi_interface=FakeChEBIInterface(records=[]))

    with pytest.raises(ValueError, match="No ChEBI records were returned"):
        workflow.run(
            modality="compound",
            mode="query_first",
            query='chebi.entity:name_contains="missing"',
        )


def test_chebi_workflow_exports_source_aware_results(tmp_path) -> None:
    workflow = MainWorkflow(chebi_interface=FakeChEBIInterface())
    data, _metadata = workflow.run(
        modality="compound",
        mode="query_first",
        query='chebi.entity:name_contains="caffeine"',
    )

    output_infos = export_workflow_outputs(data, tmp_path, "csv", None)

    assert (tmp_path / "chebi_results.csv").exists()
    assert output_infos[0]["file"] == "chebi_results.csv"
