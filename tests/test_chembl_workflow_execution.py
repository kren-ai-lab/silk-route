"""Focused offline tests for ChEMBL IC50 workflow filtering."""

from __future__ import annotations

import pandas as pd

from bioseq_dl.core.workflow.main_workflow import (
    activity_filter_metadata,
    filter_chembl_activity_dataframe,
)


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
        "standard_value_min_inclusive": False,
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
