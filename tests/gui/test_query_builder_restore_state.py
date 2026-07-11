"""Tests for pure loaded query-builder GUI state transitions."""

from __future__ import annotations

import subprocess
import sys

from bioseq_dl.gui.query_builder_state import build_gui_query_builder_state_from_loaded_form
from bioseq_dl.gui.yaml_builder import (
    build_workflow_descriptor,
    load_workflow_yaml_to_form_values,
    render_workflow_yaml,
)


def base_form_values() -> dict[str, object]:
    """Return valid minimal form values for restore-state tests."""
    return {
        "dataset.name": "restore_state",
        "dataset.modality": "protein",
        "dataset.mode": "query_first",
        "query.input_mode": "manual",
        "query.value": "organism_id:9606",
        "execution.enrich": False,
        "execution.max_workers": 5,
        "execution.total_retries": 3,
        "execution.chembl_pages_to_fetch": 1,
        "execution.debug": False,
        "export.output_dir": "results/restore_state",
        "export.format": "csv",
        "export.include_metadata": True,
        "export.include_summary": True,
    }


def restore_state(form_values: dict[str, object]) -> dict[str, object]:
    """Round-trip form values through YAML loading and pure GUI state conversion."""
    descriptor = build_workflow_descriptor(form_values)
    loaded_form_values, _notes = load_workflow_yaml_to_form_values(
        render_workflow_yaml(descriptor)
    )
    return build_gui_query_builder_state_from_loaded_form(loaded_form_values)


def test_chembl_target_metadata_restores_two_visible_rows() -> None:
    state = restore_state(
        base_form_values()
        | {
            "dataset.modality": "interaction",
            "dataset.interaction_type": "protein-ligand",
            "query.input_mode": "advanced_builder",
            "query.builder.key": "chembl_target",
            "query.chembl_builder.rows": [
                {"field": "gene_symbol", "filter_type": "iexact", "value": "EGFR"},
                {"field": "pref_name", "filter_type": "iexact", "value": "epidermal"},
            ],
        }
    )

    assert state["query_input_mode"] == "Advanced builder"
    assert state["builder_key"] == "chembl_target"
    assert state["builder_label"] == "ChEMBL target filter builder"
    assert state["chembl_rows"] == [
        {
            "field": "Gene symbol (gene_symbol)",
            "filter_type": "iexact",
            "value": "EGFR",
        },
        {
            "field": "Preferred name (pref_name)",
            "filter_type": "iexact",
            "value": "epidermal",
        },
    ]


def test_uniprot_metadata_restores_two_visible_rows() -> None:
    state = restore_state(
        base_form_values()
        | {
            "query.input_mode": "advanced_builder",
            "query.builder.key": "uniprot",
            "query.uniprot_builder.rows": [
                {
                    "connector": None,
                    "field": "organism",
                    "match_mode": "any",
                    "values": "Homo sapiens",
                },
                {
                    "connector": "AND",
                    "field": "keywords",
                    "match_mode": "all",
                    "values": "Antimicrobial,Metal-binding",
                },
            ],
        }
    )

    assert state["query_input_mode"] == "Advanced builder"
    assert state["builder_label"] == "UniProt query builder"
    assert state["uniprot_rows"] == [
        {
            "connector": "",
            "field": "Organism (organism)",
            "match_mode": "Any",
            "values": "Homo sapiens",
        },
        {
            "connector": "AND",
            "field": "Keywords (keywords)",
            "match_mode": "All",
            "values": "Antimicrobial,Metal-binding",
        },
    ]


def test_chembl_ic50_metadata_restores_visible_controls() -> None:
    state = restore_state(
        base_form_values()
        | {
            "dataset.modality": "compound",
            "query.input_mode": "advanced_builder",
            "query.builder.key": "chembl_ic50_activity",
            "query.chembl_ic50_builder.row": {
                "comparison_mode": "range",
                "lower_value": "0",
                "upper_value": "10",
                "value": "",
                "standard_units": "nM",
            },
        }
    )

    assert state["builder_key"] == "chembl_ic50_activity"
    assert state["builder_label"] == "ChEMBL IC50 activity builder"
    assert state["chembl_ic50_row"] == {
        "comparison_mode": "Range",
        "lower_value": "0",
        "upper_value": "10",
        "value": "",
        "standard_units_option": "nM",
        "custom_standard_units": "",
    }


def test_missing_builder_metadata_returns_manual_state() -> None:
    state = restore_state(base_form_values())

    assert state["query_input_mode"] == "Manual query"
    assert all(not row["values"] for row in state["uniprot_rows"])
    assert all(not row["value"] for row in state["chembl_rows"])


def test_query_builder_state_module_does_not_import_nicegui() -> None:
    import_script = """
import sys
import bioseq_dl.gui.query_builder_state

if "nicegui" in sys.modules:
    raise RuntimeError("Pure query-builder state helpers imported NiceGUI.")
"""

    subprocess.run(  # noqa: S603
        [sys.executable, "-c", import_script],
        check=True,
        capture_output=True,
        text=True,
    )
