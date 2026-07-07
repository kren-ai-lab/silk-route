"""Focused offline tests for ChEMBL IC50 workflow filtering."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from bioseq_dl.core.interfaces.chembl import ChEMBLInterface
from bioseq_dl.core.workflow import main_workflow as main_workflow_module
from bioseq_dl.core.workflow.main_workflow import (
    MainWorkflow,
    activity_filter_metadata,
    filter_chembl_activity_dataframe,
)

if TYPE_CHECKING:
    import pytest


class FakeChEMBLWorkflowInterface:
    """Return mixed-unit activity records without making external requests."""

    @staticmethod
    def extract_ic50_activity_filter(query: object) -> dict | None:
        """Delegate IC50 extraction to the production interface."""
        return ChEMBLInterface.extract_ic50_activity_filter(query)

    def fetch_single(self, **_kwargs: object) -> tuple[pd.DataFrame, dict]:
        """Return deterministic mixed-unit IC50 records."""
        records = pd.DataFrame(
            [
                {"standard_type": "IC50", "standard_value": 0, "standard_units": "nM"},
                {"standard_type": "IC50", "standard_value": 5, "standard_units": "nM"},
                {"standard_type": "IC50", "standard_value": 5, "standard_units": "uM"},
            ]
        )
        return records, {}

    @staticmethod
    def _build_data_info(result: object) -> dict:
        """Return minimal workflow metadata for the filtered result."""
        return {"number_of_records": len(result)}


def test_defensive_ic50_filter_constrains_requested_standard_units() -> None:
    records = pd.DataFrame(
        [
            {
                "molecule_chembl_id": "CHEMBL1",
                "standard_type": "IC50",
                "standard_value": 5,
                "standard_units": "nM",
            },
            {
                "molecule_chembl_id": "CHEMBL2",
                "standard_type": "IC50",
                "standard_value": 5,
                "standard_units": "uM",
            },
            {
                "molecule_chembl_id": "CHEMBL3",
                "standard_type": "IC50",
                "standard_value": 15,
                "standard_units": "nM",
            },
        ]
    )
    activity_filter = {
        "standard_type": "IC50",
        "standard_value_min": 0.0,
        "standard_value_max": 10.0,
        "standard_value_min_inclusive": True,
        "standard_value_max_inclusive": False,
        "standard_units": "nM",
    }

    filtered, metadata = filter_chembl_activity_dataframe(records, activity_filter)

    assert filtered["molecule_chembl_id"].tolist() == ["CHEMBL1"]
    assert metadata == {
        "applied": True,
        "initial_rows": 3,
        "filtered_rows": 1,
        "removed_rows": 2,
    }
    assert activity_filter_metadata(activity_filter)["standard_units"] == "nM"


def test_defensive_ic50_filter_is_conservative_when_units_column_is_missing() -> None:
    records = pd.DataFrame(
        [{"standard_type": "IC50", "standard_value": 5}]
    )
    activity_filter = {
        "standard_type": "IC50",
        "standard_value_min": 0.0,
        "standard_value_max": 10.0,
        "standard_units": "nM",
    }

    filtered, metadata = filter_chembl_activity_dataframe(records, activity_filter)

    assert filtered.empty
    assert metadata["reason"] == "missing_standard_units"


def test_ic50_metadata_omits_units_when_not_requested() -> None:
    metadata = activity_filter_metadata(
        {
            "standard_type": "IC50",
            "standard_value_min": 0.0,
            "standard_value_max": 10.0,
        }
    )

    assert "standard_units" not in metadata


def test_workflow_metadata_reports_nm_constraint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main_workflow_module,
        "ChEMBLInterface",
        FakeChEMBLWorkflowInterface,
    )
    workflow = MainWorkflow()
    context = {
        "searches": {
            "chembl": {
                "interpreted_query": (
                    "standard_type=IC50 AND standard_units=nM AND "
                    "standard_value>=0 AND standard_value<10"
                ),
                "export_format": "csv",
                "pages_to_fetch": 1,
                "limit": 100,
            }
        },
        "data": {},
        "metadata": {},
    }

    workflow._step_fetch_chembl(context)

    metadata = context["metadata"]["chembl"]
    assert metadata["activity_filter"]["standard_units"] == "nM"
    assert metadata["api_filter"]["standard_units_constrained"] is True
    assert context["data"]["chembl"]["standard_value"].tolist() == [0, 5]
