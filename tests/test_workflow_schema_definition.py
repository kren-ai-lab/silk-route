"""Tests for the lightweight workflow schema definition."""

from __future__ import annotations

import importlib
import sys

import pytest

REQUIRED_GUI_FIELDS = {
    "dataset.name",
    "dataset.description",
    "dataset.modality",
    "dataset.mode",
    "dataset.interaction_type",
    "query.value",
    "query.fields",
    "query.crossref_fields",
    "query.include_isoform",
    "query.builder",
    "query.composition",
    "execution.enrich",
    "execution.max_workers",
    "execution.total_retries",
    "execution.chembl_pages_to_fetch",
    "execution.uniprot_timeout",
    "execution.debug",
    "harmonization.id_column",
    "harmonization.label_column",
    "harmonization.sequence_column",
    "harmonization.unique_sequence_strategy",
    "harmonization.metadata_fields",
    "export.output_dir",
    "export.format",
    "export.include_metadata",
    "export.include_summary",
    "export.manifest_file",
    "export.summary_file",
}

FUTURE_ONLY_FIELDS = {
    "resources.primary",
    "resources.integration",
    "interaction_retrieval",
    "activity_retrieval",
    "chemical_metadata_integration",
    "protein_target_integration",
    "temperature_enrichment",
    "cross_source_integration",
    "export.result_files",
}

HEAVY_MODULE_PREFIXES = (
    "bioseq_dl.cli.workflows",
    "bioseq_dl.core.export",
    "bioseq_dl.core.interfaces.",
    "bioseq_dl.core.workflow.",
    "nicegui",
    "pandas",
)


def minimal_workflow_descriptor() -> dict[str, object]:
    """Return a minimal descriptor for lightweight validator tests."""
    return {
        "schema_version": "workflow-v1",
        "dataset": {
            "name": "protein_dataset",
            "modality": "protein",
            "mode": "query_first",
        },
        "query": {"value": "reviewed:true"},
        "execution": {"chembl_pages_to_fetch": 1},
        "export": {"format": ".CSV"},
    }


def test_workflow_v1_schema_definition_returns_dictionary() -> None:
    from bioseq_dl.workflow_schema_definition import get_workflow_v1_schema_definition

    schema_definition = get_workflow_v1_schema_definition()

    assert isinstance(schema_definition, dict)
    assert schema_definition["schema_version"]["default"] == "workflow-v1"
    assert schema_definition["execution.enrich"]["default"] is False


def test_workflow_v1_schema_definition_includes_required_gui_fields() -> None:
    from bioseq_dl.workflow_schema_definition import get_workflow_v1_schema_definition

    schema_definition = get_workflow_v1_schema_definition()

    assert set(schema_definition) >= REQUIRED_GUI_FIELDS
    assert schema_definition["query.value"]["gui_visible"] is True
    assert schema_definition["query.builder"]["role"] == "preserved_metadata"
    assert schema_definition["query.composition"]["role"] == "preserved_metadata"
    assert schema_definition["harmonization.metadata_fields"]["type"] == "string_list"
    assert schema_definition["harmonization.unique_sequence_strategy"]["allowed_values"] is None


def test_workflow_validator_accepts_complete_harmonization_section() -> None:
    from bioseq_dl.workflow_schema_definition import validate_workflow_v1_descriptor

    descriptor = minimal_workflow_descriptor()
    descriptor["harmonization"] = {
        "id_column": "_id",
        "label_column": "_label",
        "sequence_column": "sequence",
        "unique_sequence_strategy": "exact",
        "metadata_fields": ["accession", "protein_name", "organism_name", "sequence"],
    }

    validated = validate_workflow_v1_descriptor(descriptor)

    assert validated["harmonization"] == descriptor["harmonization"]


@pytest.mark.parametrize(
    "field_name",
    ["id_column", "label_column", "sequence_column", "unique_sequence_strategy"],
)
def test_workflow_validator_rejects_non_string_harmonization_fields(field_name: str) -> None:
    from bioseq_dl.workflow_schema_definition import validate_workflow_v1_descriptor

    descriptor = minimal_workflow_descriptor()
    descriptor["harmonization"] = {field_name: 42}

    with pytest.raises(ValueError, match=rf"harmonization\.{field_name}"):
        validate_workflow_v1_descriptor(descriptor)


def test_workflow_validator_rejects_scalar_harmonization_metadata_fields() -> None:
    from bioseq_dl.workflow_schema_definition import validate_workflow_v1_descriptor

    descriptor = minimal_workflow_descriptor()
    descriptor["harmonization"] = {"metadata_fields": "accession"}

    with pytest.raises(ValueError, match=r"harmonization\.metadata_fields"):
        validate_workflow_v1_descriptor(descriptor)


def test_workflow_v1_schema_definition_hides_future_only_fields() -> None:
    from bioseq_dl.workflow_schema_definition import get_workflow_v1_schema_definition

    schema_definition = get_workflow_v1_schema_definition()

    for field_name in FUTURE_ONLY_FIELDS:
        assert field_name in schema_definition
        assert schema_definition[field_name]["role"] == "future_feature"
        assert schema_definition[field_name]["gui_visible"] is False


def test_workflow_schema_definition_import_is_lightweight() -> None:
    for module_name in list(sys.modules):
        if module_name == "bioseq_dl.workflow_schema_definition":
            sys.modules.pop(module_name)

    imported_before = set(sys.modules)
    importlib.import_module("bioseq_dl.workflow_schema_definition")

    imported_modules = set(sys.modules) - imported_before
    for module_prefix in HEAVY_MODULE_PREFIXES:
        assert not any(module_name.startswith(module_prefix) for module_name in imported_modules)


def test_lightweight_workflow_validator_normalizes_descriptor_without_heavy_imports() -> None:
    from bioseq_dl.workflow_schema_definition import validate_workflow_v1_descriptor

    imported_before = set(sys.modules)
    validated = validate_workflow_v1_descriptor(minimal_workflow_descriptor())
    imported_modules = set(sys.modules) - imported_before

    assert validated["schema_version"] == "workflow-v1"
    assert validated["export"]["format"] == "csv"
    for module_prefix in HEAVY_MODULE_PREFIXES:
        assert not any(module_name.startswith(module_prefix) for module_name in imported_modules)
