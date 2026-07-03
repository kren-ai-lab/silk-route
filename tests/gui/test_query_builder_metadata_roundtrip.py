"""Tests for query-builder metadata restoration during workflow YAML loading."""

from __future__ import annotations

from copy import deepcopy

import yaml

from bioseq_dl.gui.yaml_builder import (
    LOADED_QUERY_VALUE_WARNING,
    QUERY_BUILDER_MISMATCH_WARNING,
    QUERY_BUILDER_RESTORE_ERROR_WARNING,
    build_workflow_descriptor,
    load_workflow_yaml_to_form_values,
    render_workflow_yaml,
)


def base_form_values() -> dict[str, object]:
    """Return valid minimal GUI form values for metadata round-trip tests."""
    return {
        "dataset.name": "metadata_roundtrip",
        "dataset.modality": "protein",
        "dataset.mode": "query_first",
        "query.value": "manual fallback",
        "query.input_mode": "manual",
        "execution.enrich": False,
        "execution.max_workers": 5,
        "execution.total_retries": 3,
        "execution.chembl_pages_to_fetch": 1,
        "execution.debug": False,
        "export.output_dir": "results/metadata_roundtrip",
        "export.format": "csv",
        "export.include_metadata": True,
        "export.include_summary": True,
    }


def load_descriptor(descriptor: dict[str, object]) -> tuple[dict[str, object], list[str]]:
    """Load one descriptor through the workflow YAML form conversion path."""
    return load_workflow_yaml_to_form_values(yaml.safe_dump(descriptor, sort_keys=False))


def test_uniprot_builder_metadata_round_trip_restores_advanced_rows() -> None:
    descriptor = build_workflow_descriptor(
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

    form_values, warnings = load_workflow_yaml_to_form_values(
        render_workflow_yaml(descriptor)
    )

    assert form_values["query.input_mode"] == "Advanced builder"
    assert form_values["query.builder.key"] == "uniprot"
    assert form_values["query.uniprot_builder.rows"] == [
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
    ]
    assert LOADED_QUERY_VALUE_WARNING not in warnings


def test_chembl_builder_metadata_round_trip_restores_advanced_rows() -> None:
    descriptor = build_workflow_descriptor(
        base_form_values()
        | {
            "dataset.modality": "compound",
            "query.input_mode": "advanced_builder",
            "query.builder.key": "chembl_activity",
            "query.chembl_builder.rows": [
                {
                    "field": "target_chembl_id",
                    "filter_type": "exact",
                    "value": "CHEMBL203",
                },
                {
                    "field": "pchembl_value",
                    "filter_type": "gte",
                    "value": "7",
                },
            ],
        }
    )

    form_values, warnings = load_workflow_yaml_to_form_values(
        render_workflow_yaml(descriptor)
    )

    assert form_values["query.input_mode"] == "Advanced builder"
    assert form_values["query.builder.key"] == "chembl_activity"
    assert form_values["query.chembl_builder.rows"] == [
        {"field": "target_chembl_id", "filter_type": "exact", "value": "CHEMBL203"},
        {"field": "pchembl_value", "filter_type": "gte", "value": "7"},
    ]
    assert warnings == []


def test_missing_builder_metadata_loads_manual_query_with_soft_note() -> None:
    descriptor = build_workflow_descriptor(base_form_values())

    form_values, warnings = load_descriptor(descriptor)

    assert form_values["query.input_mode"] == "Manual query"
    assert LOADED_QUERY_VALUE_WARNING in warnings


def test_invalid_builder_schema_version_falls_back_to_manual_query() -> None:
    descriptor = build_workflow_descriptor(
        base_form_values()
        | {
            "query.input_mode": "advanced_builder",
            "query.builder.key": "uniprot",
            "query.uniprot_builder.rows": [
                {"connector": None, "field": "organism", "match_mode": "any", "values": "human"}
            ],
        }
    )
    descriptor["query"]["builder"]["schema_version"] = "query-builder-v2"

    form_values, warnings = load_descriptor(descriptor)

    assert form_values["query.input_mode"] == "Manual query"
    assert QUERY_BUILDER_RESTORE_ERROR_WARNING in warnings


def test_unsupported_builder_key_falls_back_to_manual_query() -> None:
    descriptor = build_workflow_descriptor(
        base_form_values()
        | {
            "query.input_mode": "advanced_builder",
            "query.builder.key": "uniprot",
            "query.uniprot_builder.rows": [
                {"connector": None, "field": "organism", "match_mode": "any", "values": "human"}
            ],
        }
    )
    descriptor["query"]["builder"]["builder_key"] = "unsupported"

    form_values, warnings = load_descriptor(descriptor)

    assert form_values["query.input_mode"] == "Manual query"
    assert QUERY_BUILDER_RESTORE_ERROR_WARNING in warnings


def test_malformed_builder_rows_fall_back_to_manual_query() -> None:
    descriptor = build_workflow_descriptor(
        base_form_values()
        | {
            "query.input_mode": "advanced_builder",
            "query.builder.key": "uniprot",
            "query.uniprot_builder.rows": [
                {"connector": None, "field": "organism", "match_mode": "any", "values": "human"}
            ],
        }
    )
    descriptor["query"]["builder"]["rows"] = [{"field": "organism"}]

    form_values, warnings = load_descriptor(descriptor)

    assert form_values["query.input_mode"] == "Manual query"
    assert QUERY_BUILDER_RESTORE_ERROR_WARNING in warnings


def test_builder_query_mismatch_falls_back_to_manual_query() -> None:
    descriptor = build_workflow_descriptor(
        base_form_values()
        | {
            "query.input_mode": "advanced_builder",
            "query.builder.key": "uniprot",
            "query.uniprot_builder.rows": [
                {"connector": None, "field": "organism", "match_mode": "any", "values": "human"}
            ],
        }
    )
    descriptor["query"]["value"] = "reviewed:true"

    form_values, warnings = load_descriptor(descriptor)

    assert form_values["query.input_mode"] == "Manual query"
    assert form_values["query.value"] == "reviewed:true"
    assert QUERY_BUILDER_MISMATCH_WARNING in warnings


def test_incompatible_builder_metadata_falls_back_to_manual_query() -> None:
    descriptor = build_workflow_descriptor(
        base_form_values()
        | {
            "dataset.modality": "compound",
            "query.input_mode": "advanced_builder",
            "query.builder.key": "chembl_activity",
            "query.chembl_builder.rows": [
                {"field": "target_chembl_id", "filter_type": "exact", "value": "CHEMBL203"}
            ],
        }
    )
    incompatible_descriptor = deepcopy(descriptor)
    incompatible_descriptor["dataset"]["modality"] = "protein"

    form_values, warnings = load_descriptor(incompatible_descriptor)

    assert form_values["query.input_mode"] == "Manual query"
    assert QUERY_BUILDER_RESTORE_ERROR_WARNING in warnings


def test_manual_mode_omits_restored_builder_metadata() -> None:
    descriptor = build_workflow_descriptor(
        base_form_values()
        | {
            "query.input_mode": "advanced_builder",
            "query.builder.key": "uniprot",
            "query.uniprot_builder.rows": [
                {"connector": None, "field": "organism", "match_mode": "any", "values": "human"}
            ],
        }
    )
    form_values, warnings = load_descriptor(descriptor)
    assert warnings == []
    form_values["query.input_mode"] = "Manual query"
    form_values["query.value"] = "reviewed:true"

    regenerated = build_workflow_descriptor(form_values)

    assert regenerated["query"]["value"] == "reviewed:true"
    assert "builder" not in regenerated["query"]
