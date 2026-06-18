"""Tests for GUI workflow YAML builder helpers."""

from __future__ import annotations

import importlib
import sys

import pytest
import yaml

from bioseq_dl.gui.yaml_builder import (
    build_workflow_descriptor,
    parse_csv_list,
    render_workflow_yaml,
    validate_generated_descriptor,
)


def minimal_form_values() -> dict[str, object]:
    """Return minimal valid GUI form values."""
    return {
        "dataset.name": "example_dataset",
        "dataset.modality": "protein",
        "dataset.mode": "query_first",
        "query.value": "reviewed:true",
        "execution.enrich": False,
        "execution.max_workers": 5,
        "execution.total_retries": 3,
        "execution.chembl_pages_to_fetch": 1,
        "execution.debug": False,
        "export.output_dir": "examples/results/example_dataset",
        "export.format": "csv",
        "export.include_metadata": True,
        "export.include_summary": True,
        "export.manifest_file": "metadata.json",
        "export.summary_file": "run_summary.yml",
    }


def test_build_workflow_descriptor_generates_workflow_v1_schema_version() -> None:
    descriptor = build_workflow_descriptor(minimal_form_values())

    assert descriptor["schema_version"] == "workflow-v1"


def test_build_workflow_descriptor_generates_required_sections() -> None:
    descriptor = build_workflow_descriptor(minimal_form_values())

    assert list(descriptor) == [
        "schema_version",
        "dataset",
        "query",
        "execution",
        "harmonization",
        "export",
    ]


def test_build_workflow_descriptor_removes_empty_optional_fields() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "dataset.description": "",
            "dataset.interaction_type": "",
            "query.fields": "",
            "query.crossref_fields": "",
            "execution.uniprot_timeout": "",
            "harmonization.id_column": "",
        }
    )

    assert "description" not in descriptor["dataset"]
    assert "interaction_type" not in descriptor["dataset"]
    assert "fields" not in descriptor["query"]
    assert "crossref_fields" not in descriptor["query"]
    assert "uniprot_timeout" not in descriptor["execution"]
    assert descriptor["harmonization"] == {}


def test_parse_csv_list_removes_empty_values() -> None:
    assert parse_csv_list("accession, id,, protein_name") == ["accession", "id", "protein_name"]


def test_build_workflow_descriptor_parses_comma_separated_fields() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "query.fields": "accession,id",
            "query.crossref_fields": "go, interpro",
        }
    )

    assert descriptor["query"]["fields"] == ["accession", "id"]
    assert descriptor["query"]["crossref_fields"] == ["go", "interpro"]


def test_query_builder_and_composition_are_not_generated() -> None:
    descriptor = build_workflow_descriptor(minimal_form_values())

    assert "builder" not in descriptor["query"]
    assert "composition" not in descriptor["query"]


def test_future_only_sections_are_not_generated() -> None:
    descriptor = build_workflow_descriptor(minimal_form_values())

    assert "resources" not in descriptor
    assert "reporting" not in descriptor
    assert "interaction_retrieval" not in descriptor
    assert "activity_retrieval" not in descriptor
    assert "export.result_files" not in descriptor


def test_interaction_descriptor_includes_interaction_type_when_provided() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "dataset.modality": "interaction",
            "dataset.interaction_type": "protein-protein",
        }
    )

    assert descriptor["dataset"]["interaction_type"] == "protein-protein"


def test_validation_returns_error_for_missing_query_value() -> None:
    descriptor = build_workflow_descriptor(minimal_form_values() | {"query.value": ""})

    errors = validate_generated_descriptor(descriptor)

    assert any("query.value" in error for error in errors)


def test_validation_returns_error_for_missing_interaction_type() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "dataset.modality": "interaction",
            "dataset.interaction_type": "",
        }
    )

    errors = validate_generated_descriptor(descriptor)

    assert any("interaction_type" in error for error in errors)


def test_render_workflow_yaml_round_trips_equivalent_dictionary() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "dataset.description": "Example dataset.",
            "harmonization.id_column": "_id",
        }
    )

    yaml_text = render_workflow_yaml(descriptor)

    assert yaml.safe_load(yaml_text) == descriptor


def test_builder_does_not_require_nicegui_to_be_installed() -> None:
    sys.modules.pop("nicegui", None)
    module = importlib.import_module("bioseq_dl.gui.yaml_builder")

    assert module.build_workflow_descriptor(minimal_form_values())["schema_version"] == "workflow-v1"


def test_nicegui_app_imports_when_nicegui_is_installed() -> None:
    pytest.importorskip("nicegui")

    module = importlib.import_module("bioseq_dl.gui.nicegui_app")

    assert callable(module.main)
