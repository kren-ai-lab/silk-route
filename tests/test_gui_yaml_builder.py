"""Tests for GUI workflow YAML builder helpers."""

from __future__ import annotations

import asyncio
import importlib
import subprocess
import sys
from copy import deepcopy
from unittest.mock import Mock

import pytest
import yaml

from bioseq_dl.gui.query_builder_state import (
    build_chembl_builder_form_rows,
    build_chembl_builder_ui_rows,
    build_uniprot_builder_form_rows,
    build_uniprot_builder_ui_rows,
)
from bioseq_dl.gui.yaml_builder import (
    DEFAULT_OUTPUT_DIRECTORY_NAME_ERROR,
    LOADED_QUERY_VALUE_WARNING,
    PROTEIN_CHEMBL_QUERY_WARNING,
    QUERY_BUILDER_RESTORE_ERROR_WARNING,
    QUERY_COMPOSITION_VALUE_PARSED_NOTE,
    build_workflow_descriptor,
    build_workflow_filename,
    descriptor_to_form_values,
    load_workflow_yaml_text,
    load_workflow_yaml_to_form_values,
    parse_csv_list,
    render_workflow_yaml,
    resolve_query_value_from_form,
    validate_generated_descriptor,
    workflow_yaml_form_defaults,
)


class FakeNiceGUIUploadFile:
    """Fake NiceGUI upload file with an async text method."""

    def __init__(self, name: str, content: str) -> None:
        """Create a fake upload file."""
        self.name = name
        self.content = content
        self.requested_encoding = ""

    async def text(self, encoding: str) -> str:
        """Return uploaded text content."""
        self.requested_encoding = encoding
        return self.content


class FakeNiceGUIUploadEvent:
    """Fake NiceGUI upload event using the NiceGUI 3.13 file attribute."""

    def __init__(self, name: str, content: str) -> None:
        """Create a fake upload event."""
        self.file = FakeNiceGUIUploadFile(name, content)


class FakeWorkflowUpload:
    """Fake NiceGUI upload control with a reset method."""

    def __init__(self) -> None:
        """Initialize reset call capture."""
        self.reset_count = 0

    def reset(self) -> None:
        """Capture upload reset calls."""
        self.reset_count += 1


class FakeUploadHandlerApp:
    """Small upload handler test double."""

    def __init__(self) -> None:
        """Initialize captured handler state."""
        self.loaded_form_values: dict[str, object] | None = None
        self.warnings: list[str] | None = None
        self.errors: list[str] | None = None
        self.workflow_upload = FakeWorkflowUpload()
        self.loaded_workflow_filename: str | None = None
        self.loaded_workflow_upload_status: str | None = None
        self.loaded_workflow_upload_message: str | None = None
        self.loaded_workflow_upload_warnings: list[str] = []

    def apply_loaded_form_values(self, loaded_form_values: dict[str, object]) -> None:
        """Capture loaded form values."""
        self.loaded_form_values = loaded_form_values

    def regenerate_loaded_yaml_preview(self, warnings: list[str]) -> list[str]:
        """Capture load warnings."""
        self.warnings = warnings
        return []

    def show_errors(self, errors: list[str]) -> None:
        """Capture load errors."""
        self.errors = errors

    def set_workflow_upload_success(self, filename: object, warnings: list[str]) -> None:
        """Capture successful upload status state."""
        self.loaded_workflow_filename = str(filename or "workflow YAML file")
        self.loaded_workflow_upload_status = "success"
        self.loaded_workflow_upload_message = (
            "The form was populated from this file. Upload another YAML file to replace it."
        )
        self.loaded_workflow_upload_warnings = list(warnings)

    def set_workflow_upload_error(self, filename: object, message: str) -> None:
        """Capture failed upload status state."""
        self.loaded_workflow_filename = str(filename or "workflow YAML file")
        self.loaded_workflow_upload_status = "error"
        self.loaded_workflow_upload_message = message
        self.loaded_workflow_upload_warnings = []

    def reset_workflow_upload(self) -> None:
        """Reset the fake upload control."""
        self.workflow_upload.reset()


class FakeInteractionTypeSelect:
    """Small test double for the NiceGUI interaction type select."""

    def __init__(self) -> None:
        """Initialize visible state and captured updates."""
        self.visible = True
        self.value = ""
        self.update_count = 0

    def update(self) -> None:
        """Capture update calls."""
        self.update_count += 1


class FakeValueChangeEvent:
    """Small test double for a NiceGUI value-change event."""

    def __init__(self, value: object) -> None:
        """Store the changed control value."""
        self.value = value


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


def minimal_workflow_yaml(output_dir: str | None = "results/loaded_dataset") -> str:
    """Return minimal valid workflow-v1 YAML text."""
    export_output_dir = f'  output_dir: "{output_dir}"\n' if output_dir else ""
    return f"""
schema_version: "workflow-v1"
dataset:
  name: loaded_dataset
  description: Loaded dataset.
  modality: protein
  mode: query_first
query:
  value: "reviewed:true"
  fields:
    - accession
    - sequence
  crossref_fields:
    - xref_pdb
    - xref_string
  include_isoform: true
execution:
  enrich: false
  max_workers: 4
  total_retries: 2
  chembl_pages_to_fetch: 1
  uniprot_timeout: 12.5
  debug: true
harmonization:
  id_column: "_id"
  label_column: "_label"
  sequence_column: "sequence"
  unique_sequence_strategy: "exact"
  metadata_fields:
    - accession
    - protein_name
export:
{export_output_dir}  format: csv
  include_metadata: true
  include_summary: true
  manifest_file: "metadata.json"
  summary_file: "run_summary.yml"
"""


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
    form_values = minimal_form_values() | {"dataset.mode": label}
    if expected == "query_composition":
        form_values["query.composition.entries"] = [
            {"label": "reviewed", "value": "reviewed:true", "description": ""}
        ]

    descriptor = build_workflow_descriptor(form_values)

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
        "organism_id:9606 AND (cc_bpcp_temp_dependence:20-30 OR cc_bpcp_temp_dependence:50-60)"
    )


def test_advanced_uniprot_builder_mode_includes_builder_metadata() -> None:
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

    assert descriptor["query"]["value"] == "organism_id:9606"
    assert descriptor["query"]["include_isoform"] is False
    assert descriptor["query"]["builder"] == {
        "schema_version": "query-builder-v1",
        "source": "uniprot",
        "builder_key": "uniprot",
        "builder_type": "field_boolean",
        "rows": [
            {
                "connector": None,
                "field": "organism",
                "match_mode": "any",
                "values": ["Homo sapiens"],
            }
        ],
    }
    assert "query.uniprot_builder.rows" not in descriptor
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
    assert descriptor["query"]["builder"]["schema_version"] == "query-builder-v1"
    assert "composition" not in descriptor["query"]


@pytest.mark.parametrize(
    ("builder_key", "rows", "expected_query_value"),
    [
        (
            "chembl_target",
            [
                {"field": "type", "filter_type": "iexact", "value": "protein"},
                {"field": "gene_symbol", "filter_type": "icontains", "value": "EGFR"},
            ],
            "chembl.target:type__iexact=protein AND gene_symbol__icontains=EGFR",
        ),
        (
            "chembl_assay",
            [
                {"field": "label_type", "filter_type": "iexact", "value": "functional"},
                {"field": "organism", "filter_type": "icontains", "value": "virus"},
            ],
            "chembl.assay:label_type__iexact=functional AND organism__icontains=virus",
        ),
        (
            "chembl_cell_line",
            [{"field": "organism", "filter_type": "icontains", "value": "mus"}],
            "chembl.cell_line:organism__icontains=mus",
        ),
        (
            "chembl_molecule",
            [
                {"field": "name", "filter_type": "iexact", "value": "Imatinib"},
                {"field": "molecular_weight", "filter_type": "range", "value": "80,200"},
            ],
            "chembl.molecule:name__iexact=Imatinib AND molecular_weight__range=80,200",
        ),
        (
            "chembl_activity",
            [
                {"field": "target_chembl_id", "filter_type": "exact", "value": "CHEMBL5169197"},
                {"field": "pchembl_value", "filter_type": "exact", "value": "5.83"},
            ],
            "chembl.activity:target_chembl_id=CHEMBL5169197 AND pchembl_value=5.83",
        ),
    ],
)
def test_advanced_chembl_builder_modes_generate_interpreted_query_value(
    builder_key: str,
    rows: list[dict[str, object]],
    expected_query_value: str,
) -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "query.input_mode": "Advanced builder",
            "query.builder.key": builder_key,
            "query.chembl_builder.rows": rows,
        }
    )

    assert descriptor["query"]["value"] == expected_query_value
    assert validate_generated_descriptor(descriptor) == []
    assert descriptor["query"]["builder"]["schema_version"] == "query-builder-v1"
    assert descriptor["query"]["builder"]["source"] == "chembl"
    assert descriptor["query"]["builder"]["builder_key"] == builder_key
    assert "composition" not in descriptor["query"]
    assert "friendly_query" not in descriptor["query"]
    assert "query.chembl_builder.rows" not in descriptor
    assert "resources" not in descriptor
    assert "reporting" not in descriptor


def test_advanced_chembl_builder_rejects_invalid_row() -> None:
    with pytest.raises(ValueError, match="Row 1: value is required"):
        build_workflow_descriptor(
            minimal_form_values()
            | {
                "query.input_mode": "advanced_builder",
                "query.builder.key": "chembl_target",
                "query.chembl_builder.rows": [
                    {"field": "gene_symbol", "filter_type": "icontains", "value": ""}
                ],
            }
        )


def test_selected_chembl_builder_determines_resource() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "query.input_mode": "advanced_builder",
            "query.builder.key": "ChEMBL activity parameter builder",
            "query.chembl_builder.rows": [
                {"field": "standard_type", "filter_type": "exact", "value": "IC50"},
            ],
        }
    )

    assert descriptor["query"]["value"] == "chembl.activity:standard_type=IC50"


@pytest.mark.parametrize(
    ("builder_key", "row", "expected_query_value"),
    [
        (
            "pubchem_compound",
            {"field": "name", "value": "glucose", "threshold": ""},
            'pubchem.compound:name="glucose"',
        ),
        (
            "pubchem_structure",
            {"field": "smiles_substructure", "value": "c1ccccc1", "threshold": ""},
            'pubchem.structure:smiles_substructure="c1ccccc1"',
        ),
        (
            "pubchem_structure",
            {"field": "similarity_2d", "value": "446157", "threshold": 80},
            "pubchem.structure:similarity_2d_cid=446157 AND threshold=80",
        ),
    ],
)
def test_advanced_pubchem_builder_modes_generate_interpreted_query_value(
    builder_key: str,
    row: dict[str, object],
    expected_query_value: str,
) -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "query.input_mode": "Advanced builder",
            "query.builder.key": builder_key,
            "query.pubchem_builder.row": row,
        }
    )

    assert descriptor["query"]["value"] == expected_query_value
    assert "builder" not in descriptor["query"]


@pytest.mark.parametrize(
    ("builder_key", "rows", "expected_query_value"),
    [
        (
            "chebi_entity",
            [{"field": "name", "operator": "contains", "value": "caffeine"}],
            'chebi.entity:name_contains="caffeine"',
        ),
        (
            "chebi_ontology",
            [
                {
                    "field": "ontology_relation",
                    "operator": "exact",
                    "value": "has_role",
                    "secondary_value": "metabolite",
                }
            ],
            "chebi.ontology:relation=has_role AND term=metabolite",
        ),
        (
            "chebi_structure",
            [{"field": "substructure", "operator": "substructure", "value": "c1ccccc1"}],
            'chebi.structure:substructure="c1ccccc1"',
        ),
    ],
)
def test_advanced_chebi_builder_modes_generate_interpreted_query_value(
    builder_key: str,
    rows: list[dict[str, object]],
    expected_query_value: str,
) -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "query.input_mode": "Advanced builder",
            "query.builder.key": builder_key,
            "query.chebi_builder.rows": rows,
        }
    )

    assert descriptor["query"]["value"] == expected_query_value
    assert "builder" not in descriptor["query"]


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
    descriptor = build_workflow_descriptor(minimal_form_values() | {"harmonization.id_column": ""})

    assert "harmonization" not in descriptor


def test_non_empty_harmonization_id_column_includes_harmonization_section() -> None:
    descriptor = build_workflow_descriptor(minimal_form_values() | {"harmonization.id_column": "_id"})

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
        | {"harmonization.metadata_fields": ("accession, protein_name, , organism_name, sequence")}
    )

    assert descriptor["harmonization"]["metadata_fields"] == [
        "accession",
        "protein_name",
        "organism_name",
        "sequence",
    ]


def test_empty_harmonization_metadata_fields_are_omitted() -> None:
    descriptor = build_workflow_descriptor(minimal_form_values() | {"harmonization.metadata_fields": " , , "})

    assert "harmonization" not in descriptor


def test_complete_harmonization_block_validates_as_workflow_v1() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "harmonization.id_column": "_id",
            "harmonization.label_column": "_label",
            "harmonization.sequence_column": "sequence",
            "harmonization.unique_sequence_strategy": "exact",
            "harmonization.metadata_fields": ("accession, protein_name, organism_name, sequence"),
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

    assert errors == ["dataset.interaction_type is required when dataset.modality is 'interaction'."]


def test_default_output_directory_mode_uses_dataset_name() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "export.output_dir_mode": "Use default results folder",
            "export.output_dir": "ignored/custom/path",
        }
    )

    assert descriptor["export"]["output_dir"] == "results/example_dataset"


def test_numeric_execution_strings_are_converted_to_numbers() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "execution.max_workers": "5",
            "execution.total_retries": "3",
            "execution.chembl_pages_to_fetch": "-1",
        }
    )

    assert descriptor["execution"]["max_workers"] == 5
    assert descriptor["execution"]["total_retries"] == 3
    assert descriptor["execution"]["chembl_pages_to_fetch"] == -1
    assert validate_generated_descriptor(descriptor) == []


def test_numeric_execution_integer_floats_are_converted_to_numbers() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "execution.max_workers": 5.0,
            "execution.total_retries": 3.0,
            "execution.chembl_pages_to_fetch": -1.0,
        }
    )

    assert descriptor["execution"]["max_workers"] == 5
    assert descriptor["execution"]["total_retries"] == 3
    assert descriptor["execution"]["chembl_pages_to_fetch"] == -1
    assert validate_generated_descriptor(descriptor) == []


def test_optional_uniprot_timeout_empty_string_is_omitted() -> None:
    descriptor = build_workflow_descriptor(minimal_form_values() | {"execution.uniprot_timeout": "  "})

    assert "uniprot_timeout" not in descriptor["execution"]


def test_optional_uniprot_timeout_string_is_converted_to_number() -> None:
    descriptor = build_workflow_descriptor(minimal_form_values() | {"execution.uniprot_timeout": " 12.5 "})

    assert descriptor["execution"]["uniprot_timeout"] == 12.5


def test_invalid_required_integer_string_raises_clear_error() -> None:
    with pytest.raises(ValueError, match=r"execution\.chembl_pages_to_fetch must be an integer"):
        build_workflow_descriptor(minimal_form_values() | {"execution.chembl_pages_to_fetch": "abc"})


def test_non_integer_required_float_raises_clear_error() -> None:
    with pytest.raises(ValueError, match=r"execution\.max_workers must be an integer"):
        build_workflow_descriptor(minimal_form_values() | {"execution.max_workers": 1.5})


def test_non_integer_required_string_raises_clear_error() -> None:
    with pytest.raises(ValueError, match=r"execution\.max_workers must be an integer"):
        build_workflow_descriptor(minimal_form_values() | {"execution.max_workers": "1.5"})


def test_boolean_required_integer_raises_clear_error() -> None:
    with pytest.raises(TypeError, match=r"execution\.max_workers must be an integer"):
        build_workflow_descriptor(minimal_form_values() | {"execution.max_workers": True})


def test_empty_required_integer_string_raises_clear_error() -> None:
    with pytest.raises(
        ValueError,
        match=r"execution\.max_workers is required and must be an integer",
    ):
        build_workflow_descriptor(minimal_form_values() | {"execution.max_workers": ""})


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

    assert errors == [DEFAULT_OUTPUT_DIRECTORY_NAME_ERROR]


def test_default_output_directory_error_explains_dataset_name_source() -> None:
    descriptor = build_workflow_descriptor(
        minimal_form_values()
        | {
            "dataset.name": "",
            "export.output_dir_mode": "Use default results folder",
        }
    )

    errors = validate_generated_descriptor(descriptor)

    assert errors == [DEFAULT_OUTPUT_DIRECTORY_NAME_ERROR]
    assert "results/{dataset.name}" in errors[0]


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


def test_load_workflow_yaml_text_parses_mapping() -> None:
    descriptor = load_workflow_yaml_text(minimal_workflow_yaml())

    assert descriptor["schema_version"] == "workflow-v1"
    assert descriptor["query"]["value"] == "reviewed:true"


def test_descriptor_to_form_values_loads_supported_fields() -> None:
    descriptor = load_workflow_yaml_text(minimal_workflow_yaml())

    form_values = descriptor_to_form_values(descriptor)

    assert form_values["dataset.name"] == "loaded_dataset"
    assert form_values["dataset.description"] == "Loaded dataset."
    assert form_values["dataset.modality"] == "Protein"
    assert form_values["dataset.mode"] == "Query First"
    assert form_values["dataset.interaction_type"] == "No interaction"
    assert form_values["query.value"] == "reviewed:true"
    assert form_values["query.input_mode"] == "Manual query"
    assert form_values["query.include_isoform"] is True
    assert form_values["execution.max_workers"] == 4
    assert form_values["execution.total_retries"] == 2
    assert form_values["execution.chembl_pages_to_fetch"] == 1
    assert form_values["execution.uniprot_timeout"] == 12.5
    assert form_values["execution.debug"] is True
    assert form_values["harmonization.id_column"] == "_id"
    assert form_values["harmonization.label_column"] == "_label"
    assert form_values["harmonization.sequence_column"] == "sequence"
    assert form_values["harmonization.unique_sequence_strategy"] == "exact"
    assert form_values["export.format"] == "CSV"
    assert form_values["export.include_metadata"] is True
    assert form_values["export.include_summary"] is True


def test_loaded_list_fields_become_comma_separated_text() -> None:
    form_values, _warnings = load_workflow_yaml_to_form_values(minimal_workflow_yaml())

    assert form_values["query.fields"] == "accession, sequence"
    assert form_values["query.crossref_fields"] == "xref_pdb, xref_string"
    assert form_values["harmonization.metadata_fields"] == "accession, protein_name"


def test_missing_optional_list_fields_become_empty_strings() -> None:
    yaml_text = """
schema_version: "workflow-v1"
dataset:
  name: loaded_dataset
  modality: protein
  mode: query_first
query:
  value: "reviewed:true"
execution:
  enrich: false
export:
  format: csv
"""

    form_values, _warnings = load_workflow_yaml_to_form_values(yaml_text)

    assert form_values["query.fields"] == ""
    assert form_values["query.crossref_fields"] == ""
    assert form_values["harmonization.metadata_fields"] == ""


def test_loaded_output_dir_selects_custom_output_directory_mode() -> None:
    form_values, _warnings = load_workflow_yaml_to_form_values(minimal_workflow_yaml())

    assert form_values["export.output_dir_mode"] == "Use custom relative path"
    assert form_values["export.output_dir"] == "results/loaded_dataset"


def test_missing_output_dir_selects_default_output_directory_mode() -> None:
    form_values, _warnings = load_workflow_yaml_to_form_values(minimal_workflow_yaml(output_dir=None))

    assert form_values["export.output_dir_mode"] == "Use default results folder"
    assert form_values["export.output_dir"] == ""


def test_loaded_query_value_warns_and_uses_manual_query_mode() -> None:
    form_values, warnings = load_workflow_yaml_to_form_values(minimal_workflow_yaml())

    assert form_values["query.input_mode"] == "Manual query"
    assert form_values["query.value"] == "reviewed:true"
    assert LOADED_QUERY_VALUE_WARNING in warnings


def test_loaded_protein_descriptor_with_chembl_query_warns() -> None:
    yaml_text = minimal_workflow_yaml().replace(
        'value: "reviewed:true"',
        'value: "chembl.target:gene_symbol__iexact=EGFR"',
    )

    _form_values, warnings = load_workflow_yaml_to_form_values(yaml_text)

    assert PROTEIN_CHEMBL_QUERY_WARNING in warnings


def test_invalid_yaml_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="Invalid YAML"):
        load_workflow_yaml_text("dataset: [")


def test_non_mapping_yaml_raises_clear_error() -> None:
    with pytest.raises(TypeError, match="root must be a mapping"):
        load_workflow_yaml_text("- one\n- two\n")


def test_invalid_schema_version_is_rejected_on_load() -> None:
    yaml_text = minimal_workflow_yaml().replace('"workflow-v1"', '"workflow-v2"')

    with pytest.raises(ValueError, match="Unsupported workflow schema_version"):
        load_workflow_yaml_to_form_values(yaml_text)


def test_invalid_query_builder_metadata_falls_back_to_manual_mode() -> None:
    yaml_text = minimal_workflow_yaml().replace(
        "  include_isoform: true\n",
        "  include_isoform: true\n  builder:\n    name: uniprot\n",
    )

    form_values, warnings = load_workflow_yaml_to_form_values(yaml_text)

    assert QUERY_BUILDER_RESTORE_ERROR_WARNING in warnings
    assert form_values["query.input_mode"] == "Manual query"
    assert "query.builder" not in form_values
    assert "query.composition" not in form_values


def test_query_composition_metadata_loads_as_editable_form_values() -> None:
    yaml_text = minimal_workflow_yaml().replace("mode: query_first", "mode: query_composition").replace(
        "  include_isoform: true\n",
        (
            "  value: reviewed:true=reviewed\n"
            "  include_isoform: true\n"
            "  composition:\n"
            "    - label: reviewed\n"
            "      value: reviewed:true\n"
        ),
    ).replace('  value: "reviewed:true"\n', "", 1)

    form_values, warnings = load_workflow_yaml_to_form_values(yaml_text)

    assert warnings == []
    entry = form_values["query.composition.entries"][0]
    assert entry["label"] == "reviewed"
    assert entry["value"] == "reviewed:true"
    assert entry["description"] == ""
    assert entry["query_input_mode"] == "Manual query"


def test_query_composition_value_without_metadata_loads_with_note() -> None:
    yaml_text = minimal_workflow_yaml().replace("mode: query_first", "mode: query_composition").replace(
        'value: "reviewed:true"',
        'value: "reviewed:true=reviewed"',
    )

    form_values, warnings = load_workflow_yaml_to_form_values(yaml_text)

    assert QUERY_COMPOSITION_VALUE_PARSED_NOTE in warnings
    entry = form_values["query.composition.entries"][0]
    assert entry["label"] == "reviewed"
    assert entry["value"] == "reviewed:true"
    assert entry["description"] == ""
    assert entry["query_input_mode"] == "Manual query"


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


def test_read_upload_event_text_uses_nicegui_file_text() -> None:
    pytest.importorskip("nicegui")
    module = importlib.import_module("bioseq_dl.gui.nicegui_app")
    event = FakeNiceGUIUploadEvent("workflow.yml", minimal_workflow_yaml())

    yaml_text = asyncio.run(module.read_upload_event_text(event))

    assert yaml_text == minimal_workflow_yaml()
    assert event.file.requested_encoding == "utf-8"


def test_load_yaml_upload_uses_event_file_name_and_async_text() -> None:
    pytest.importorskip("nicegui")
    module = importlib.import_module("bioseq_dl.gui.nicegui_app")
    app = FakeUploadHandlerApp()
    event = FakeNiceGUIUploadEvent("workflow.yaml", minimal_workflow_yaml())

    asyncio.run(module.WorkflowYamlBuilderApp.load_yaml_upload(app, event))

    assert app.errors is None
    assert app.loaded_form_values is not None
    assert app.loaded_form_values["query.value"] == "reviewed:true"
    assert app.loaded_form_values["query.input_mode"] == "Manual query"
    assert app.warnings is not None
    assert LOADED_QUERY_VALUE_WARNING in app.warnings
    assert event.file.requested_encoding == "utf-8"
    assert app.workflow_upload.reset_count == 1
    assert app.loaded_workflow_filename == "workflow.yaml"
    assert app.loaded_workflow_upload_status == "success"
    assert app.loaded_workflow_upload_message == (
        "The form was populated from this file. Upload another YAML file to replace it."
    )
    assert LOADED_QUERY_VALUE_WARNING in app.loaded_workflow_upload_warnings


def test_load_yaml_upload_rejects_unsupported_event_file_name() -> None:
    pytest.importorskip("nicegui")
    module = importlib.import_module("bioseq_dl.gui.nicegui_app")
    app = FakeUploadHandlerApp()
    event = FakeNiceGUIUploadEvent("workflow.txt", minimal_workflow_yaml())

    asyncio.run(module.WorkflowYamlBuilderApp.load_yaml_upload(app, event))

    assert app.errors == ["Unsupported file type. Upload a .yml or .yaml workflow file."]
    assert app.loaded_form_values is None
    assert event.file.requested_encoding == ""
    assert app.workflow_upload.reset_count == 1
    assert app.loaded_workflow_filename == "workflow.txt"
    assert app.loaded_workflow_upload_status == "error"
    assert app.loaded_workflow_upload_message == (
        "Unsupported file type. Upload a .yml or .yaml workflow file."
    )
    assert app.loaded_workflow_upload_warnings == []


def test_load_yaml_upload_resets_upload_control_after_invalid_yaml() -> None:
    pytest.importorskip("nicegui")
    module = importlib.import_module("bioseq_dl.gui.nicegui_app")
    app = FakeUploadHandlerApp()
    event = FakeNiceGUIUploadEvent("workflow.yml", "dataset: [")

    asyncio.run(module.WorkflowYamlBuilderApp.load_yaml_upload(app, event))

    assert app.errors is not None
    assert app.errors[0].startswith("Could not load workflow YAML: Invalid YAML")
    assert app.loaded_form_values is None
    assert event.file.requested_encoding == "utf-8"
    assert app.workflow_upload.reset_count == 1
    assert app.loaded_workflow_filename == "workflow.yml"
    assert app.loaded_workflow_upload_status == "error"
    assert app.loaded_workflow_upload_message is not None
    assert app.loaded_workflow_upload_message.startswith("Could not load workflow YAML: Invalid YAML")
    assert app.loaded_workflow_upload_warnings == []


def test_load_yaml_upload_replaces_previous_success_with_error_status() -> None:
    pytest.importorskip("nicegui")
    module = importlib.import_module("bioseq_dl.gui.nicegui_app")
    app = FakeUploadHandlerApp()

    asyncio.run(
        module.WorkflowYamlBuilderApp.load_yaml_upload(
            app,
            FakeNiceGUIUploadEvent("first.workflow-v1.yml", minimal_workflow_yaml()),
        )
    )
    asyncio.run(
        module.WorkflowYamlBuilderApp.load_yaml_upload(
            app,
            FakeNiceGUIUploadEvent("second.workflow-v1.yml", "dataset: ["),
        )
    )

    assert app.loaded_workflow_filename == "second.workflow-v1.yml"
    assert app.loaded_workflow_upload_status == "error"
    assert app.loaded_workflow_upload_message is not None
    assert app.loaded_workflow_upload_message.startswith("Could not load workflow YAML: Invalid YAML")
    assert app.loaded_workflow_upload_warnings == []
    assert app.workflow_upload.reset_count == 2


def test_interaction_type_selector_visibility_helper_matches_modality() -> None:
    pytest.importorskip("nicegui")
    module = importlib.import_module("bioseq_dl.gui.nicegui_app")

    assert module.should_show_interaction_type_selector({"dataset.modality": "Interaction"})
    assert not module.should_show_interaction_type_selector({"dataset.modality": "Protein"})
    assert not module.should_show_interaction_type_selector({"dataset.modality": "Compound"})


def test_update_interaction_type_visibility_resets_non_interaction_value() -> None:
    pytest.importorskip("nicegui")
    module = importlib.import_module("bioseq_dl.gui.nicegui_app")
    app = object.__new__(module.WorkflowYamlBuilderApp)
    app.form_values = {
        "dataset.modality": "Protein",
        "dataset.interaction_type": "Protein-ligand interaction",
    }
    app.interaction_type_select = FakeInteractionTypeSelect()

    module.WorkflowYamlBuilderApp.update_interaction_type_visibility(app)

    assert app.form_values["dataset.interaction_type"] == "No interaction"
    assert app.interaction_type_select.value == "No interaction"
    assert app.interaction_type_select.visible is False
    assert app.interaction_type_select.update_count == 1


def test_update_interaction_type_visibility_shows_interaction_value() -> None:
    pytest.importorskip("nicegui")
    module = importlib.import_module("bioseq_dl.gui.nicegui_app")
    app = object.__new__(module.WorkflowYamlBuilderApp)
    app.form_values = {
        "dataset.modality": "Interaction",
        "dataset.interaction_type": "Protein-protein interaction",
    }
    app.interaction_type_select = FakeInteractionTypeSelect()
    app.interaction_type_select.visible = False

    module.WorkflowYamlBuilderApp.update_interaction_type_visibility(app)

    assert app.form_values["dataset.interaction_type"] == "Protein-protein interaction"
    assert app.interaction_type_select.visible is True
    assert app.interaction_type_select.update_count == 1


def test_apply_loaded_chembl_builder_preserves_rows_and_rebuilds_query_section() -> None:
    pytest.importorskip("nicegui")
    module = importlib.import_module("bioseq_dl.gui.nicegui_app")
    descriptor = build_workflow_descriptor(
        minimal_form_values()
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
    loaded_form_values, warnings = load_workflow_yaml_to_form_values(
        render_workflow_yaml(descriptor)
    )
    app = module.WorkflowYamlBuilderApp()
    app.build_query_controls = Mock()

    app.apply_loaded_form_values(loaded_form_values)

    assert warnings == []
    assert app.form_values["query.input_mode"] == "Advanced builder"
    assert app.form_values["query.builder.key"] == "ChEMBL activity parameter builder"
    assert [row["value"] for row in app.chembl_builder_rows] == ["CHEMBL203", "7"]
    app.build_query_controls.refresh.assert_called_once_with()


def test_loaded_chembl_builder_state_rebuilds_query_without_patching_widgets() -> None:
    pytest.importorskip("nicegui")
    module = importlib.import_module("bioseq_dl.gui.nicegui_app")
    descriptor = build_workflow_descriptor(
        minimal_form_values()
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
    loaded_form_values, warnings = load_workflow_yaml_to_form_values(
        render_workflow_yaml(descriptor)
    )
    app = module.WorkflowYamlBuilderApp()
    app.build_query_controls = Mock()

    app.apply_loaded_form_values(loaded_form_values)

    assert warnings == []
    assert app.form_values["query.input_mode"] == "Advanced builder"
    assert app.form_values["query.builder.key"] == "ChEMBL target filter builder"
    assert [row["value"] for row in app.chembl_builder_rows] == ["EGFR", "epidermal"]
    app.build_query_controls.refresh.assert_called_once_with()


def test_compatible_builder_refresh_without_reset_preserves_chembl_rows() -> None:
    pytest.importorskip("nicegui")
    module = importlib.import_module("bioseq_dl.gui.nicegui_app")
    app = module.WorkflowYamlBuilderApp()
    app.form_values["dataset.modality"] = "Interaction"
    app.form_values["dataset.interaction_type"] = "Protein-ligand interaction"
    app.form_values["query.builder.key"] = "ChEMBL target filter builder"
    app.active_query_builder_label = "ChEMBL target filter builder"
    app.chembl_builder_rows = build_chembl_builder_ui_rows(
        "chembl_target",
        [
            {"field": "gene_symbol", "filter_type": "iexact", "value": "EGFR"},
            {"field": "pref_name", "filter_type": "iexact", "value": "epidermal"},
        ],
    )

    app.refresh_query_builder_options(refresh_rows=False, reset_chembl_rows=False)

    assert [row["value"] for row in app.chembl_builder_rows] == ["EGFR", "epidermal"]
    assert len(app.form_values["query.chembl_builder.rows"]) == 2


def test_loaded_compatible_builder_survives_delayed_dataset_and_builder_events() -> None:
    pytest.importorskip("nicegui")
    module = importlib.import_module("bioseq_dl.gui.nicegui_app")
    descriptor = build_workflow_descriptor(
        minimal_form_values()
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
    loaded_form_values, warnings = load_workflow_yaml_to_form_values(
        render_workflow_yaml(descriptor)
    )
    app = module.WorkflowYamlBuilderApp()
    app.build_chembl_builder_rows = Mock()
    app.build_uniprot_builder_rows = Mock()

    app.apply_loaded_form_values_to_state(loaded_form_values)
    app.refresh_query_builder_options(refresh_rows=False)
    app.handle_query_builder_change()

    assert warnings == []
    assert app.form_values["query.builder.key"] == "ChEMBL target filter builder"
    assert [row["value"] for row in app.chembl_builder_rows] == ["EGFR", "epidermal"]
    assert len(app.form_values["query.chembl_builder.rows"]) == 2


def test_chembl_form_rows_convert_to_complete_gui_rows() -> None:
    form_rows = [
        {"field": "gene_symbol", "filter_type": "iexact", "value": "EGFR"},
        {"field": "pref_name", "filter_type": "iexact", "value": "epidermal"},
    ]

    ui_rows = build_chembl_builder_ui_rows("chembl_target", form_rows)

    assert len(ui_rows) == 2
    assert [row["filter_type"] for row in ui_rows] == ["iexact", "iexact"]
    assert [row["value"] for row in ui_rows] == ["EGFR", "epidermal"]
    assert build_chembl_builder_form_rows("chembl_target", ui_rows) == form_rows


def test_uniprot_form_rows_convert_to_complete_gui_rows() -> None:
    form_rows = [
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

    ui_rows = build_uniprot_builder_ui_rows(form_rows)

    assert len(ui_rows) == 2
    assert [row["connector"] for row in ui_rows] == ["", "AND"]
    assert [row["values"] for row in ui_rows] == [
        "Homo sapiens",
        "Antimicrobial,Metal-binding",
    ]
    assert build_uniprot_builder_form_rows(ui_rows) == form_rows


def test_chembl_row_event_updates_restored_state_and_form_values() -> None:
    pytest.importorskip("nicegui")
    module = importlib.import_module("bioseq_dl.gui.nicegui_app")
    app = module.WorkflowYamlBuilderApp()
    app.form_values["query.builder.key"] = "ChEMBL target filter builder"
    app.chembl_builder_rows = build_chembl_builder_ui_rows(
        "chembl_target",
        [
            {"field": "gene_symbol", "filter_type": "iexact", "value": "EGFR"},
            {"field": "pref_name", "filter_type": "iexact", "value": "epidermal"},
        ],
    )
    app.build_chembl_builder_rows = Mock()
    app.update_builder_previews = Mock()

    app.set_chembl_builder_row_value(1, "value", FakeValueChangeEvent("EGFR receptor"))

    assert app.chembl_builder_rows[1]["value"] == "EGFR receptor"
    assert app.form_values["query.chembl_builder.rows"][1]["value"] == "EGFR receptor"
    app.build_chembl_builder_rows.refresh.assert_not_called()
    app.update_builder_previews.assert_called_once_with()


def test_uniprot_row_event_updates_restored_state_and_form_values() -> None:
    pytest.importorskip("nicegui")
    module = importlib.import_module("bioseq_dl.gui.nicegui_app")
    app = module.WorkflowYamlBuilderApp()
    app.uniprot_builder_rows = build_uniprot_builder_ui_rows(
        [
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
    )
    app.build_uniprot_builder_rows = Mock()
    app.update_builder_previews = Mock()

    app.set_uniprot_builder_row_value(
        1,
        "values",
        FakeValueChangeEvent("Antimicrobial"),
    )

    assert app.uniprot_builder_rows[1]["values"] == "Antimicrobial"
    assert app.form_values["query.uniprot_builder.rows"][1]["values"] == "Antimicrobial"
    app.build_uniprot_builder_rows.refresh.assert_not_called()
    app.update_builder_previews.assert_called_once_with()


def test_nicegui_app_imports_when_nicegui_is_installed() -> None:
    pytest.importorskip("nicegui")

    module = importlib.import_module("bioseq_dl.gui.nicegui_app")

    assert callable(module.main)


def test_nicegui_main_uses_root_factory_without_reload(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("nicegui")
    module = importlib.import_module("bioseq_dl.gui.nicegui_app")
    create_app = Mock()
    run = Mock()
    monkeypatch.setattr(module, "create_app", create_app)
    monkeypatch.setattr(module.ui, "run", run)

    module.main()

    create_app.assert_not_called()
    run.assert_called_once_with(
        root=create_app,
        title="BioSeqDownloader Workflow YAML Builder",
        reload=False,
    )
def test_composition_mode_initializes_only_selected_entry_local_rows() -> None:
    pytest.importorskip("nicegui")
    module = importlib.import_module("bioseq_dl.gui.nicegui_app")
    app = module.WorkflowYamlBuilderApp()
    app.form_values["dataset.modality"] = "Protein"
    app.form_values["dataset.mode"] = "Query Composition"
    app.form_values["query.composition.entries"] = [
        {
            "label": "antimicrobial",
            "value": "keywords:Antimicrobial",
            "description": "",
            "query_input_mode": "Manual query",
            "query_builder_key": "uniprot",
            "uniprot_builder_rows": [],
            "chembl_builder_rows": [],
        },
        {
            "label": "antiviral",
            "value": "keywords:Antiviral",
            "description": "",
            "query_input_mode": "Manual query",
            "query_builder_key": "uniprot",
            "uniprot_builder_rows": [],
            "chembl_builder_rows": [],
        },
    ]
    global_rows_before = deepcopy(app.uniprot_builder_rows)
    second_entry_before = deepcopy(app.form_values["query.composition.entries"][1])
    app.build_query_composition_rows = Mock()

    app.handle_query_composition_entry_mode_change(
        0,
        FakeValueChangeEvent("Advanced builder"),
    )

    first_entry = app.form_values["query.composition.entries"][0]
    assert first_entry["query_input_mode"] == "Advanced builder"
    assert first_entry["query_builder_key"] == "uniprot"
    assert first_entry["uniprot_builder_rows"] == [
        {"connector": None, "field": "organism", "values": "", "match_mode": "any"}
    ]
    assert app.form_values["query.composition.entries"][1] == second_entry_before
    assert app.uniprot_builder_rows == global_rows_before


def test_composition_builder_change_resets_only_selected_entry() -> None:
    pytest.importorskip("nicegui")
    module = importlib.import_module("bioseq_dl.gui.nicegui_app")
    app = module.WorkflowYamlBuilderApp()
    app.form_values["dataset.modality"] = "Interaction"
    app.form_values["dataset.interaction_type"] = "Protein-ligand interaction"
    app.form_values["dataset.mode"] = "Query Composition"
    app.form_values["query.composition.entries"] = [
        {
            "label": "egfr",
            "value": "",
            "description": "",
            "query_input_mode": "Advanced builder",
            "query_builder_key": "chembl_activity",
            "uniprot_builder_rows": [],
            "chembl_builder_rows": [
                {"field": "target_chembl_id", "filter_type": "exact", "value": "CHEMBL203"}
            ],
        },
        {
            "label": "other",
            "value": "chembl.target:gene_symbol__iexact=ALK",
            "description": "",
            "query_input_mode": "Manual query",
            "query_builder_key": "chembl_target",
            "uniprot_builder_rows": [],
            "chembl_builder_rows": [],
        },
    ]
    second_entry_before = deepcopy(app.form_values["query.composition.entries"][1])
    global_rows_before = deepcopy(app.chembl_builder_rows)
    app.build_query_composition_rows = Mock()

    app.handle_query_composition_entry_builder_change(
        0,
        FakeValueChangeEvent("ChEMBL target filter builder"),
    )

    first_entry = app.form_values["query.composition.entries"][0]
    assert first_entry["query_builder_key"] == "chembl_target"
    assert len(first_entry["chembl_builder_rows"]) == 1
    assert first_entry["chembl_builder_rows"][0]["field"] == "gene_symbol"
    assert app.form_values["query.composition.entries"][1] == second_entry_before
    assert app.chembl_builder_rows == global_rows_before
