"""Tests for workflow YAML descriptor validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from bioseq_dl.cli.workflows import (
    ALLOWED_DESCRIPTOR_SECTION_NAMES,
    WORKFLOW_SCHEMA_VERSION,
    build_metadata_document,
    build_summary_document,
    validate_workflow_recipe,
)

EXPECTED_TOOL_IDENTITY_KEYS = {
    "tool_name",
    "distribution_name",
    "import_package_name",
    "version",
}

EXPECTED_ALLOWED_DESCRIPTOR_SECTIONS = [
    "schema_version",
    "dataset",
    "query",
    "resources",
    "execution",
    "harmonization",
    "export",
    "reporting",
    "interaction_retrieval",
    "activity_retrieval",
    "chemical_metadata_integration",
    "protein_target_integration",
    "temperature_enrichment",
    "cross_source_integration",
]


CANONICAL_CORE_DESCRIPTOR_ORDER = [
    "schema_version",
    "dataset",
    "query",
    "resources",
    "execution",
    "harmonization",
    "export",
    "reporting",
]


def base_workflow_descriptor() -> dict:
    """Return a minimal valid workflow-v1 descriptor."""
    return {
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "dataset": {
            "name": "protein_dataset",
            "modality": "protein",
            "mode": "query_first",
        },
        "query": {
            "value": "reviewed:true",
        },
        "execution": {
            "enrich": False,
        },
        "export": {
            "output_dir": "results/protein_dataset",
            "format": "csv",
        },
    }


def descriptor_with_all_core_sections() -> dict:
    """Return a valid descriptor that includes every core workflow-v1 section."""
    descriptor = base_workflow_descriptor()
    descriptor["resources"] = {
        "primary": ["uniprot"],
        "integration": [],
    }
    descriptor["harmonization"] = {
        "id_column": "_id",
        "label_column": None,
        "sequence_column": "sequence",
        "metadata_fields": ["accession", "sequence"],
    }
    descriptor["reporting"] = {
        "workflow_execution_time_seconds": None,
        "notes": "Filled after execution.",
    }
    return descriptor


def build_preserved_metadata_descriptor() -> dict:
    """Return a descriptor with GUI-oriented query metadata."""
    descriptor = descriptor_with_all_core_sections()
    descriptor["query"]["builder"] = {
        "source": "gui",
        "filters": [
            {
                "field": "reviewed",
                "operator": "equals",
                "value": True,
                "nested": {"arbitrary": ["metadata", 1, None]},
            }
        ],
    }
    descriptor["query"]["composition"] = [
        {"label": "reviewed", "value": "reviewed:true", "description": None},
        {"label": "disease", "value": "cc_disease:cancer", "description": "Disease filter"},
    ]
    return descriptor


def test_allowed_top_level_sections_are_exactly_workflow_v1_sections() -> None:
    assert ALLOWED_DESCRIPTOR_SECTION_NAMES == EXPECTED_ALLOWED_DESCRIPTOR_SECTIONS


def test_valid_minimal_workflow_v1_descriptor() -> None:
    values = validate_workflow_recipe(base_workflow_descriptor())

    assert values["schema_version"] == WORKFLOW_SCHEMA_VERSION
    assert values["query"] == "reviewed:true"
    assert values["query_descriptor"] == {"value": "reviewed:true", "include_isoform": False}


def test_schema_version_is_required() -> None:
    descriptor = base_workflow_descriptor()
    descriptor.pop("schema_version")

    with pytest.raises(ValueError, match="missing required top-level key 'schema_version'"):
        validate_workflow_recipe(descriptor)


def test_unsupported_schema_version_is_rejected() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["schema_version"] = "workflow-v2"

    with pytest.raises(ValueError, match="Unsupported workflow schema_version 'workflow-v2'"):
        validate_workflow_recipe(descriptor)


def test_old_version_key_remains_forbidden() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["version"] = "workflow-v1"

    with pytest.raises(ValueError, match=r"Use schema_version: \"workflow-v1\""):
        validate_workflow_recipe(descriptor)


def test_unknown_top_level_section_is_rejected() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["unknown_section"] = {}

    with pytest.raises(ValueError, match="Unknown workflow YAML section 'unknown_section'"):
        validate_workflow_recipe(descriptor)


def test_invalid_dataset_modality_is_rejected() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["dataset"]["modality"] = "rna"

    with pytest.raises(ValueError, match="Unsupported dataset\\.modality 'rna'"):
        validate_workflow_recipe(descriptor)


def test_invalid_dataset_mode_is_rejected() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["dataset"]["mode"] = "pipeline"

    with pytest.raises(ValueError, match="Unsupported dataset\\.mode 'pipeline'"):
        validate_workflow_recipe(descriptor)


def test_interaction_modality_requires_interaction_type() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["dataset"]["modality"] = "interaction"

    with pytest.raises(ValueError, match=r"dataset\.interaction_type is required"):
        validate_workflow_recipe(descriptor)


def test_unsupported_interaction_type_is_rejected() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["dataset"]["interaction_type"] = "compound-compound"

    with pytest.raises(ValueError, match=r"Unsupported dataset\.interaction_type 'compound-compound'"):
        validate_workflow_recipe(descriptor)


def test_missing_query_value_is_rejected() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["query"].pop("value")

    with pytest.raises(ValueError, match=r"query.*missing required key.*value"):
        validate_workflow_recipe(descriptor)


@pytest.mark.parametrize("empty_value", ["", "   "])
def test_empty_query_value_is_rejected(empty_value: str) -> None:
    descriptor = base_workflow_descriptor()
    descriptor["query"]["value"] = empty_value

    with pytest.raises(ValueError, match=r"query\.value.*non-empty string"):
        validate_workflow_recipe(descriptor)


def test_invalid_export_format_is_rejected() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["export"]["format"] = "xlsx"

    with pytest.raises(ValueError, match="Unsupported export format 'xlsx'"):
        validate_workflow_recipe(descriptor)


def test_query_builder_must_be_mapping() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["query"]["builder"] = ["not", "a", "mapping"]

    with pytest.raises(TypeError, match=r"query\.builder"):
        validate_workflow_recipe(descriptor)


def test_query_builder_allows_arbitrary_nested_metadata() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["query"]["builder"] = {
        "nodes": [
            {"field": "reviewed", "value": True},
            {"field": "score", "range": {"minimum": 10, "maximum": None}},
        ],
        "layout": {"x": 1.25, "y": [0, 1, 2]},
    }

    values = validate_workflow_recipe(descriptor)

    assert values["query_descriptor"]["builder"] == descriptor["query"]["builder"]


def test_query_composition_must_be_list() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["query"]["composition"] = {"label": "reviewed", "value": "reviewed:true"}

    with pytest.raises(TypeError, match=r"query\.composition.*list of mappings"):
        validate_workflow_recipe(descriptor)


def test_query_composition_items_must_be_mappings() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["query"]["composition"] = ["reviewed:true"]

    with pytest.raises(TypeError, match=r"query\.composition\[0\].*mapping"):
        validate_workflow_recipe(descriptor)


@pytest.mark.parametrize(
    ("composition_item", "expected_error"),
    [
        ({"value": "reviewed:true"}, r"query\.composition\[0\]\.label"),
        ({"label": "", "value": "reviewed:true"}, r"query\.composition\[0\]\.label"),
        ({"label": "reviewed", "value": ""}, r"query\.composition\[0\]\.value"),
        ({"label": "reviewed", "value": None}, r"query\.composition\[0\]\.value"),
    ],
)
def test_query_composition_items_require_non_empty_label_and_value(
    composition_item: dict,
    expected_error: str,
) -> None:
    descriptor = base_workflow_descriptor()
    descriptor["query"]["composition"] = [composition_item]

    with pytest.raises(ValueError, match=expected_error):
        validate_workflow_recipe(descriptor)


@pytest.mark.parametrize("description", ["Reviewed proteins", None])
def test_query_composition_description_may_be_string_or_null(description: str | None) -> None:
    descriptor = base_workflow_descriptor()
    descriptor["query"]["composition"] = [
        {"label": "reviewed", "value": "reviewed:true", "description": description},
    ]

    values = validate_workflow_recipe(descriptor)

    assert values["query_descriptor"]["composition"] == descriptor["query"]["composition"]


def test_invalid_query_composition_description_is_rejected() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["query"]["composition"] = [
        {"label": "reviewed", "value": "reviewed:true", "description": ["not", "valid"]},
    ]

    with pytest.raises(ValueError, match=r"query\.composition\[0\]\.description"):
        validate_workflow_recipe(descriptor)


def test_query_composition_matching_query_value_passes_validation() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["dataset"]["mode"] = "query_composition"
    descriptor["query"]["value"] = "gene:TP53=tp53,gene:BRCA1=brca1"
    descriptor["query"]["composition"] = [
        {"label": "tp53", "value": "gene:TP53", "description": "TP53 query."},
        {"label": "brca1", "value": "gene:BRCA1", "description": None},
    ]

    values = validate_workflow_recipe(descriptor)

    assert values["query_descriptor"]["composition"] == descriptor["query"]["composition"]


def test_query_composition_contradicting_query_value_fails_validation() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["dataset"]["mode"] = "query_composition"
    descriptor["query"]["value"] = "gene:TP53=tp53"
    descriptor["query"]["composition"] = [
        {"label": "brca1", "value": "gene:BRCA1"},
    ]

    with pytest.raises(ValueError, match=r"query\.composition does not match executable query\.value"):
        validate_workflow_recipe(descriptor)


def test_query_composition_with_unparsable_query_value_fails_validation() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["dataset"]["mode"] = "query_composition"
    descriptor["query"]["value"] = "gene:TP53"
    descriptor["query"]["composition"] = [
        {"label": "tp53", "value": "gene:TP53"},
    ]

    with pytest.raises(ValueError, match=r"query\.composition does not match executable query\.value"):
        validate_workflow_recipe(descriptor)


def test_schema_version_and_gui_query_metadata_are_preserved_in_outputs() -> None:
    descriptor = build_preserved_metadata_descriptor()

    values = validate_workflow_recipe(descriptor)
    metadata = build_metadata_document(
        workflow_metadata={},
        workflow_values=values,
        output_infos=[],
        reporting={},
        started_at="2026-06-16T00:00:00+00:00",
        finished_at="2026-06-16T00:00:01+00:00",
        duration_seconds=1.0,
    )
    summary = build_summary_document(
        workflow_values=values,
        output_infos=[],
        reporting={},
        started_at="2026-06-16T00:00:00+00:00",
        finished_at="2026-06-16T00:00:01+00:00",
        duration_seconds=1.0,
        metadata_path=Path("metadata.json"),
        summary_path=Path("run_summary.yml"),
    )

    normalized_descriptor = metadata["normalized_descriptor"]
    original_descriptor = metadata["original_descriptor"]

    assert list(normalized_descriptor)[: len(CANONICAL_CORE_DESCRIPTOR_ORDER)] == (
        CANONICAL_CORE_DESCRIPTOR_ORDER
    )
    assert normalized_descriptor["schema_version"] == WORKFLOW_SCHEMA_VERSION
    assert original_descriptor["schema_version"] == WORKFLOW_SCHEMA_VERSION
    assert normalized_descriptor["query"]["builder"] == descriptor["query"]["builder"]
    assert normalized_descriptor["query"]["composition"] == descriptor["query"]["composition"]
    assert metadata["normalized_workflow_values"]["schema_version"] == WORKFLOW_SCHEMA_VERSION
    assert set(metadata["tool"]) == EXPECTED_TOOL_IDENTITY_KEYS
    assert metadata["tool"]["tool_name"] == "BioSeqDownloader"
    assert metadata["tool"]["distribution_name"] == "bioseqdownloader"
    assert metadata["tool"]["import_package_name"] == "bioseq_dl"
    assert metadata["tool"]["version"]
    assert set(summary["tool"]) == EXPECTED_TOOL_IDENTITY_KEYS
    assert summary["tool"] == metadata["tool"]
    assert summary["schema_version"] == WORKFLOW_SCHEMA_VERSION
    assert summary["query"]["builder"] == descriptor["query"]["builder"]
    assert summary["query"]["composition"] == descriptor["query"]["composition"]
