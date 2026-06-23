"""Tests for GUI workflow YAML builder helpers."""

from __future__ import annotations

import importlib
import subprocess
import sys

import pytest
import yaml

from bioseq_dl.gui.yaml_builder import (
    build_workflow_descriptor,
    build_workflow_filename,
    parse_csv_list,
    render_workflow_yaml,
    resolve_query_value_from_form,
    validate_generated_descriptor,
    workflow_yaml_form_defaults,
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
            "harmonization.label_column": "",
            "harmonization.sequence_column": "",
            "harmonization.unique_sequence_strategy": "",
            "harmonization.metadata_fields": "",
        }
    )

    assert "description" not in descriptor["dataset"]
    assert "interaction_type" not in descriptor["dataset"]
    assert "fields" not in descriptor["query"]
    assert "crossref_fields" not in descriptor["query"]
    assert "uniprot_timeout" not in descriptor["execution"]
    assert "harmonization" not in descriptor


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


def test_empty_return_fields_and_crossref_placeholders_do_not_generate_lists() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "query.fields": "",
            "query.crossref_fields": "",
        }
    )

    assert "fields" not in descriptor["query"]
    assert "crossref_fields" not in descriptor["query"]


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Protein", "protein"),
        ("Compound", "compound"),
        ("Interaction", "interaction"),
    ],
)
def test_human_readable_modality_labels_map_to_schema_values(label: str, expected: str) -> None:
    form_values = minimal_form_values() | {"dataset.modality": label}
    if label == "Interaction":
        form_values["dataset.interaction_type"] = "Protein-protein interaction"

    descriptor = build_workflow_descriptor(form_values)

    assert descriptor["dataset"]["modality"] == expected


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Query First", "query_first"),
        ("Query Composition", "query_composition"),
    ],
)
def test_human_readable_workflow_mode_labels_map_to_schema_values(label: str, expected: str) -> None:
    descriptor = build_workflow_descriptor(minimal_form_values() | {"dataset.mode": label})

    assert descriptor["dataset"]["mode"] == expected


@pytest.mark.parametrize(
    ("label", "expected"),
    [("CSV", "csv"), ("JSON", "json"), ("XML", "xml"), ("Parquet", "parquet")],
)
def test_human_readable_export_format_labels_map_to_schema_values(label: str, expected: str) -> None:
    descriptor = build_workflow_descriptor(minimal_form_values() | {"export.format": label})

    assert descriptor["export"]["format"] == expected


def test_query_builder_and_composition_are_not_generated() -> None:
    descriptor = build_workflow_descriptor(minimal_form_values())

    assert "builder" not in descriptor["query"]
    assert "composition" not in descriptor["query"]


def test_manual_query_mode_generates_manual_query_value() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "query.input_mode": "Manual query",
            "query.value": "reviewed:true AND organism_id:9606",
        }
    )

    assert descriptor["query"]["value"] == "reviewed:true AND organism_id:9606"


def test_resolve_query_value_from_manual_mode_does_not_call_builder() -> None:
    form_values = minimal_form_values() | {
        "query.input_mode": "manual",
        "query.value": "reviewed:true",
        "query.uniprot_builder.rows": [
            {
                "connector": None,
                "field": "organism",
                "values": "",
                "match_mode": "any",
            }
        ],
    }

    assert resolve_query_value_from_form(form_values) == "reviewed:true"


def test_advanced_uniprot_builder_mode_generates_interpreted_query_value() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "query.input_mode": "Advanced UniProt builder",
            "query.value": "manual text ignored",
            "query.uniprot_builder.rows": [
                {
                    "connector": None,
                    "field": "organism",
                    "values": "Homo sapiens",
                    "match_mode": "Any",
                },
                {
                    "connector": "AND",
                    "field": "temperature",
                    "values": "20-30,50-60",
                    "match_mode": "Any",
                },
            ],
        }
    )

    assert descriptor["query"]["value"] == (
        "organism_id:9606 AND "
        "(cc_bpcp_temp_dependence:20-30 OR cc_bpcp_temp_dependence:50-60)"
    )


def test_advanced_uniprot_builder_mode_omits_builder_metadata() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "query.input_mode": "uniprot_builder",
            "query.uniprot_builder.rows": [
                {
                    "connector": None,
                    "field": "organism",
                    "values": "Homo sapiens",
                    "match_mode": "any",
                    "friendly_query": 'organism_any:"Homo sapiens"',
                }
            ],
        }
    )

    assert descriptor["query"] == {
        "value": "organism_id:9606",
        "include_isoform": False,
    }
    assert "query.uniprot_builder.rows" not in descriptor
    assert "builder" not in descriptor["query"]
    assert "composition" not in descriptor["query"]
    assert "friendly_query" not in descriptor["query"]


def test_advanced_uniprot_builder_mode_keeps_query_fields_separate() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "query.input_mode": "uniprot_builder",
            "query.uniprot_builder.rows": [
                {
                    "connector": None,
                    "field": "organism",
                    "values": "Homo sapiens",
                    "match_mode": "any",
                }
            ],
            "query.fields": "accession, protein_name",
            "query.crossref_fields": "xref_alphafolddb",
        }
    )

    assert descriptor["query"]["value"] == "organism_id:9606"
    assert descriptor["query"]["fields"] == ["accession", "protein_name"]
    assert descriptor["query"]["crossref_fields"] == ["xref_alphafolddb"]


def test_advanced_uniprot_builder_mode_rejects_invalid_rows() -> None:
    with pytest.raises(ValueError, match="Row 1: values are required"):
        build_workflow_descriptor(
            minimal_form_values()
            | {
                "query.input_mode": "uniprot_builder",
                "query.uniprot_builder.rows": [
                    {
                        "connector": None,
                        "field": "organism",
                        "values": "",
                        "match_mode": "any",
                    }
                ],
            }
        )


def test_advanced_uniprot_builder_descriptor_validates_as_workflow_v1() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "query.input_mode": "uniprot_builder",
            "query.uniprot_builder.rows": [
                {
                    "connector": None,
                    "field": "databases",
                    "values": "alphafold,pdb",
                    "match_mode": "any",
                }
            ],
        }
    )

    assert descriptor["query"]["value"] == "(database:alphafolddb OR database:pdb)"
    assert validate_generated_descriptor(descriptor) == []
    assert "resources" not in descriptor
    assert "reporting" not in descriptor
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


def test_non_interaction_descriptor_omits_interaction_type() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "dataset.modality": "protein",
            "dataset.interaction_type": "protein-protein",
        }
    )

    assert "interaction_type" not in descriptor["dataset"]


def test_no_interaction_label_omits_interaction_type_for_protein_modality() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "dataset.modality": "Protein",
            "dataset.interaction_type": "No interaction",
        }
    )

    assert "interaction_type" not in descriptor["dataset"]


def test_empty_harmonization_id_column_omits_harmonization_section() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values() | {"harmonization.id_column": ""}
    )

    assert "harmonization" not in descriptor


def test_non_empty_harmonization_id_column_includes_harmonization_section() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values() | {"harmonization.id_column": "_id"}
    )

    assert descriptor["harmonization"] == {"id_column": "_id"}


@pytest.mark.parametrize(
    ("field_name", "yaml_key", "value"),
    [
        ("harmonization.label_column", "label_column", "_label"),
        ("harmonization.sequence_column", "sequence_column", "sequence"),
        ("harmonization.unique_sequence_strategy", "unique_sequence_strategy", "exact"),
    ],
)
def test_non_empty_harmonization_text_fields_are_included(
    field_name: str,
    yaml_key: str,
    value: str,
) -> None:
    descriptor = build_workflow_descriptor(minimal_form_values() | {field_name: value})

    assert descriptor["harmonization"] == {yaml_key: value}


def test_harmonization_metadata_fields_are_parsed_as_csv() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "harmonization.metadata_fields": (
                "accession, protein_name, , organism_name, sequence"
            )
        }
    )

    assert descriptor["harmonization"]["metadata_fields"] == [
        "accession",
        "protein_name",
        "organism_name",
        "sequence",
    ]


def test_empty_harmonization_metadata_fields_are_omitted() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values() | {"harmonization.metadata_fields": " , , "}
    )

    assert "harmonization" not in descriptor


def test_complete_harmonization_block_validates_as_workflow_v1() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "harmonization.id_column": "_id",
            "harmonization.label_column": "_label",
            "harmonization.sequence_column": "sequence",
            "harmonization.unique_sequence_strategy": "exact",
            "harmonization.metadata_fields": (
                "accession, protein_name, organism_name, sequence"
            ),
        }
    )

    assert descriptor["harmonization"] == {
        "id_column": "_id",
        "label_column": "_label",
        "sequence_column": "sequence",
        "unique_sequence_strategy": "exact",
        "metadata_fields": [
            "accession",
            "protein_name",
            "organism_name",
            "sequence",
        ],
    }
    assert validate_generated_descriptor(descriptor) == []
    assert "resources" not in descriptor
    assert "reporting" not in descriptor
    assert "builder" not in descriptor["query"]
    assert "composition" not in descriptor["query"]


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


def test_no_interaction_label_is_rejected_for_interaction_modality() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "dataset.modality": "Interaction",
            "dataset.interaction_type": "No interaction",
        }
    )

    errors = validate_generated_descriptor(descriptor)

    assert errors == [
        "dataset.interaction_type is required when dataset.modality is 'interaction'."
    ]


def test_default_output_directory_mode_uses_dataset_name() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "export.output_dir_mode": "Use default results folder",
            "export.output_dir": "ignored/custom/path",
        }
    )

    assert descriptor["export"]["output_dir"] == "results/example_dataset"


def test_custom_output_directory_mode_normalizes_relative_path() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "export.output_dir_mode": "Use custom relative path",
            "export.output_dir": "  custom\\nested\\results  ",
        }
    )

    assert descriptor["export"]["output_dir"] == "custom/nested/results"


@pytest.mark.parametrize("output_dir", ["C:\\results\\dataset", "/results/dataset"])
def test_absolute_output_directories_are_rejected(output_dir: str) -> None:
    with pytest.raises(ValueError, match="must be a relative path"):
        build_workflow_descriptor(
            minimal_form_values()
            | {
                "export.output_dir_mode": "Use custom relative path",
                "export.output_dir": output_dir,
            }
        )


def test_output_directory_path_traversal_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not contain path traversal"):
        build_workflow_descriptor(
            minimal_form_values()
            | {
                "export.output_dir_mode": "Use custom relative path",
                "export.output_dir": "results/../outside",
            }
        )


def test_prevalidation_allows_missing_dataset_name_with_output_directory() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "dataset.name": "",
            "export.output_dir": "results/unnamed_dataset",
        }
    )

    assert validate_generated_descriptor(descriptor) == []


def test_prevalidation_requires_dataset_name_without_output_directory() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "dataset.name": "",
            "export.output_dir": "",
        }
    )

    errors = validate_generated_descriptor(descriptor)

    assert errors == ["dataset.name is required when export.output_dir is not provided."]


def test_default_generated_descriptor_validates_as_workflow_v1() -> None:
    form_values = workflow_yaml_form_defaults()
    form_values["dataset.name"] = "default_dataset"
    form_values["query.value"] = "reviewed:true"

    descriptor = build_workflow_descriptor(form_values)

    assert descriptor["schema_version"] == "workflow-v1"
    assert descriptor["execution"]["enrich"] is False
    assert descriptor["execution"]["max_workers"] == 5
    assert descriptor["execution"]["total_retries"] == 3
    assert descriptor["execution"]["chembl_pages_to_fetch"] == -1
    assert "uniprot_timeout" not in descriptor["execution"]
    assert validate_generated_descriptor(descriptor) == []


@pytest.mark.parametrize(
    ("dataset_name", "expected"),
    [
        (None, "workflow-v1.yml"),
        ("", "workflow-v1.yml"),
        ("My Dataset", "my_dataset.workflow-v1.yml"),
        ("../Unsafe\\Name", "unsafe_name.workflow-v1.yml"),
        ("Dataset: 2026 / Final", "dataset_2026_final.workflow-v1.yml"),
    ],
)
def test_build_workflow_filename_is_safe(dataset_name: object, expected: str) -> None:
    assert build_workflow_filename(dataset_name) == expected


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


def test_yaml_builder_import_does_not_load_gui_cli_or_interfaces() -> None:
    import_script = """
import sys
import bioseq_dl.gui.yaml_builder

blocked_prefixes = (
    "bioseq_dl.cli.workflows",
    "bioseq_dl.core.export",
    "bioseq_dl.core.interfaces",
    "bioseq_dl.core.workflow",
    "nicegui",
    "pandas",
)
for blocked_prefix in blocked_prefixes:
    loaded = [
        module_name
        for module_name in sys.modules
        if module_name == blocked_prefix or module_name.startswith(f"{blocked_prefix}.")
    ]
    if loaded:
        raise RuntimeError(f"Unexpected imports for {blocked_prefix}: {loaded}")
"""

    subprocess.run(  # noqa: S603
        [sys.executable, "-c", import_script],
        check=True,
        capture_output=True,
        text=True,
    )


def test_nicegui_app_imports_when_nicegui_is_installed() -> None:
    pytest.importorskip("nicegui")

    module = importlib.import_module("bioseq_dl.gui.nicegui_app")

    assert callable(module.main)
