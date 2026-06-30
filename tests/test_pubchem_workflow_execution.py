"""Offline tests for PubChem compound workflow execution."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from bioseq_dl.cli.workflows import build_metadata_document, build_summary_document, export_workflow_outputs
from bioseq_dl.core.workflow.main_workflow import MainWorkflow
from bioseq_dl.core.workflow.pubchem_execution import PUBCHEM_WORKFLOW_METHOD


class FakePubChemInterface:
    """Record PubChem workflow calls and return frozen property records."""

    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        self.records = records if records is not None else [{"CID": 5793, "Title": "Glucose"}]
        self.calls: list[dict[str, Any]] = []

    def fetch_single(self, query: dict[str, Any], **kwargs: Any) -> tuple[list[dict[str, Any]], dict]:
        self.calls.append({"query": query, "kwargs": kwargs})
        return self.records, {"api_name": "PubChem", "method": kwargs.get("method")}


@pytest.mark.parametrize(
    ("query", "expected_namespace", "expected_mode"),
    [
        ('pubchem.compound:name="glucose"', "name", "lookup"),
        ("pubchem.compound:cid=2244", "cid", "lookup"),
        ('pubchem.structure:smiles_substructure="c1ccccc1"', "smiles", "substructure"),
        ("pubchem.structure:similarity_2d_cid=446157 AND threshold=80", "cid", "similarity_2d"),
    ],
)
def test_compound_pubchem_query_dispatches_to_pubchem_interface(
    query: str,
    expected_namespace: str,
    expected_mode: str,
) -> None:
    interface = FakePubChemInterface()
    workflow = MainWorkflow(pubchem_interface=interface)

    data, metadata = workflow.run(modality="compound", mode="query_first", query=query)

    assert set(data) == {"pubchem"}
    assert isinstance(data["pubchem"], pd.DataFrame)
    assert interface.calls[0]["query"]["namespace"] == expected_namespace
    assert interface.calls[0]["query"]["search_mode"] == expected_mode
    assert interface.calls[0]["kwargs"]["method"] == PUBCHEM_WORKFLOW_METHOD
    assert interface.calls[0]["kwargs"]["workflow_request_plan"] == metadata["request_plan"]
    assert metadata["query_source"] == "pubchem"
    assert metadata["number_of_records"] == 1


def test_pubchem_workflow_rejects_empty_results() -> None:
    workflow = MainWorkflow(pubchem_interface=FakePubChemInterface(records=[]))

    with pytest.raises(ValueError, match="No PubChem records were returned"):
        workflow.run(
            modality="compound",
            mode="query_first",
            query='pubchem.compound:name="missing"',
        )


def test_pubchem_workflow_exports_source_aware_results(tmp_path) -> None:
    workflow = MainWorkflow(pubchem_interface=FakePubChemInterface())
    data, _metadata = workflow.run(
        modality="compound",
        mode="query_first",
        query='pubchem.compound:name="glucose"',
    )

    output_infos = export_workflow_outputs(data, tmp_path, "csv", None)

    assert (tmp_path / "pubchem_results.csv").exists()
    assert output_infos[0]["file"] == "pubchem_results.csv"


def test_pubchem_metadata_and_summary_include_request_plan(tmp_path) -> None:
    workflow = MainWorkflow(pubchem_interface=FakePubChemInterface())
    data, workflow_metadata = workflow.run(
        modality="compound",
        mode="query_first",
        query='pubchem.compound:name="glucose"',
    )
    output_infos = export_workflow_outputs(data, tmp_path, "csv", None)
    workflow_values = {
        "query": 'pubchem.compound:name="glucose"',
        "query_descriptor": {"value": 'pubchem.compound:name="glucose"'},
        "modality": "compound",
        "mode": "query_first",
        "output": str(tmp_path),
        "export_format": "csv",
    }

    metadata = build_metadata_document(
        workflow_metadata,
        workflow_values,
        output_infos,
        {},
        "2026-01-01T00:00:00+00:00",
        "2026-01-01T00:00:01+00:00",
        1.0,
    )
    summary = build_summary_document(
        workflow_values,
        output_infos,
        {},
        "2026-01-01T00:00:00+00:00",
        "2026-01-01T00:00:01+00:00",
        1.0,
        tmp_path / "metadata.json",
        tmp_path / "run_summary.yml",
        workflow_metadata=workflow_metadata,
    )

    assert metadata["workflow_metadata"]["request_plan"] == workflow_metadata["request_plan"]
    assert metadata["output_files"][0]["file"] == "pubchem_results.csv"
    assert summary["query"]["source"] == "pubchem"
    assert summary["query"]["request_plan"] == workflow_metadata["request_plan"]
    assert summary["execution"]["number_of_records"] == 1
