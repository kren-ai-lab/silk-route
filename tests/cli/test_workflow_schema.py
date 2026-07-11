"""Tests for workflow YAML descriptor validation."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml
from typer.testing import CliRunner

import bioseq_dl.cli.workflows as workflows_cli
from bioseq_dl.cli.workflows import (
    ALLOWED_DESCRIPTOR_SECTION_NAMES,
    WORKFLOW_SCHEMA_VERSION,
    build_metadata_document,
    build_summary_document,
    export_workflow_outputs,
    split_pair,
    validate_workflow_recipe,
)
from bioseq_dl.cli.workflows import (
    app as workflow_app,
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
CAPTURED_WORKFLOW_KWARGS: dict[str, Any] = {}


class CapturingWorkflow:
    """Capture workflow execution kwargs without API calls."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        """Initialize the fake workflow."""

    def run(self, **kwargs: Any) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
        """Return deterministic tabular output while recording kwargs."""
        CAPTURED_WORKFLOW_KWARGS.clear()
        CAPTURED_WORKFLOW_KWARGS.update(kwargs)
        return {"uniprot": pd.DataFrame([{"accession": "P02776"}])}, {}


class PlaceholderUniprotInterface:
    """Placeholder UniProt interface for CLI construction."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        """Initialize the fake UniProt interface."""


def graph_enrichment_data() -> dict[str, dict[str, pd.DataFrame]]:
    """Return graph enrichment output with one non-empty and one empty graph."""
    return {
        "uniprot_enrichment": {
            "pathwaycommons_neighborhood": pd.DataFrame(
                [
                    {
                        "source_accession": "P02776",
                        "source_protein_name": "Platelet factor 4",
                        "source_organism_id": "9606",
                        "source_query": {"source": "uniprot:P02776"},
                        "source_database": "pathwaycommons",
                        "source_endpoint": "neighborhood",
                        "graph_format": "jsonld",
                        "graph_record_count": 1,
                        "graph_json": json.dumps({"@graph": [{"id": "node-1"}]}),
                    },
                    {
                        "source_accession": "P31151",
                        "source_protein_name": "S100-A7",
                        "source_organism_id": "9606",
                        "source_query": {"source": "uniprot:P31151"},
                        "source_database": "pathwaycommons",
                        "source_endpoint": "neighborhood",
                        "graph_format": "jsonld",
                        "graph_record_count": 0,
                        "graph_json": "[]",
                    },
                ]
            )
        }
    }


def graph_enrichment_metadata() -> dict[str, Any]:
    """Return raw-graph enrichment metadata."""
    return {
        "uniprot_enrichment": {
            "pathwaycommons_neighborhood": {
                "output_kind": "raw_graph",
                "graph_serialization": "json",
                "graph_tabularization": "one_row_per_source",
            }
        }
    }


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
    """Return a descriptor with neutral query-builder metadata."""
    descriptor = descriptor_with_all_core_sections()
    descriptor["query"]["builder"] = {
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
    assert values["download_alphafold_structures"] is True
    assert values["download_pdb_structures"] is True
    assert values["execution"]["download_alphafold_structures"] is True
    assert values["execution"]["download_pdb_structures"] is True
    assert values["graph_payload_storage"] == "inline"
    assert values["graph_payload_compression"] == "gzip"
    assert values["export"]["graph_payload_storage"] == "inline"
    assert values["export"]["graph_payload_compression"] == "gzip"


def test_workflow_v1_preserves_explicit_structure_download_flags() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["execution"]["download_alphafold_structures"] = False
    descriptor["execution"]["download_pdb_structures"] = False

    values = validate_workflow_recipe(descriptor)

    assert values["download_alphafold_structures"] is False
    assert values["download_pdb_structures"] is False
    assert values["execution"]["download_alphafold_structures"] is False
    assert values["execution"]["download_pdb_structures"] is False


@pytest.mark.parametrize("storage_mode", ["inline", "file", "both", "none"])
def test_workflow_v1_accepts_graph_payload_storage_modes(storage_mode: str) -> None:
    descriptor = base_workflow_descriptor()
    descriptor["export"]["graph_payload_storage"] = storage_mode

    values = validate_workflow_recipe(descriptor)

    assert values["graph_payload_storage"] == storage_mode
    assert values["export"]["graph_payload_storage"] == storage_mode


def test_workflow_v1_rejects_invalid_graph_payload_storage_mode() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["export"]["graph_payload_storage"] = "database"

    with pytest.raises(ValueError, match=r"export\.graph_payload_storage"):
        validate_workflow_recipe(descriptor)


@pytest.mark.parametrize("compression", ["none", "gzip"])
def test_workflow_v1_accepts_graph_payload_compression_modes(compression: str) -> None:
    descriptor = base_workflow_descriptor()
    descriptor["export"]["graph_payload_storage"] = "file"
    descriptor["export"]["graph_payload_compression"] = compression

    values = validate_workflow_recipe(descriptor)

    assert values["graph_payload_compression"] == compression
    assert values["export"]["graph_payload_compression"] == compression


def test_workflow_v1_rejects_invalid_graph_payload_compression_mode() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["export"]["graph_payload_compression"] = "zip"

    with pytest.raises(ValueError, match=r"export\.graph_payload_compression"):
        validate_workflow_recipe(descriptor)


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


def test_query_builder_metadata_does_not_change_executable_query() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["query"]["builder"] = {
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

    values = validate_workflow_recipe(descriptor)

    assert values["query"] == "reviewed:true"


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
    descriptor["query"]["value"] = "ic50:0-10=active,ic50:10-100=inactive"
    descriptor["query"]["composition"] = [
        {"label": "active", "value": "ic50:0-10"},
        {"label": "inactive", "value": "ic50:10-100"},
    ]

    values = validate_workflow_recipe(descriptor)

    assert values["query_descriptor"]["composition"] == descriptor["query"]["composition"]


def test_query_composition_with_equals_in_query_value_passes_validation() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["dataset"]["mode"] = "query_composition"
    descriptor["query"]["value"] = "chembl.target:gene_symbol__iexact=EGFR=egfr"
    descriptor["query"]["composition"] = [
        {"label": "egfr", "value": "chembl.target:gene_symbol__iexact=EGFR"},
    ]

    values = validate_workflow_recipe(descriptor)

    assert values["query_descriptor"]["composition"] == descriptor["query"]["composition"]


def test_query_composition_with_ic50_standard_units_passes_validation() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["dataset"]["mode"] = "query_composition"
    descriptor["query"]["value"] = (
        "ic50:0-10 AND standard_units:nM=very_high_potency,"
        "ic50:10-100 AND standard_units:nM=high_potency"
    )
    descriptor["query"]["composition"] = [
        {
            "label": "very_high_potency",
            "value": "ic50:0-10 AND standard_units:nM",
        },
        {
            "label": "high_potency",
            "value": "ic50:10-100 AND standard_units:nM",
        },
    ]

    values = validate_workflow_recipe(descriptor)

    assert values["query_descriptor"]["composition"] == descriptor["query"]["composition"]


def test_cli_composition_pair_splits_on_last_equals_sign() -> None:
    assert split_pair("chembl.target:gene_symbol__iexact=EGFR=egfr") == (
        "chembl.target:gene_symbol__iexact=EGFR",
        "egfr",
    )


def test_query_composition_crossed_pairs_fail_validation() -> None:
    descriptor = base_workflow_descriptor()
    descriptor["dataset"]["mode"] = "query_composition"
    descriptor["query"]["value"] = "ic50:0-10=active,ic50:10-100=inactive"
    descriptor["query"]["composition"] = [
        {"label": "active", "value": "ic50:10-100"},
        {"label": "inactive", "value": "ic50:0-10"},
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
    assert metadata["normalized_workflow_values"]["download_alphafold_structures"] is True
    assert metadata["normalized_workflow_values"]["download_pdb_structures"] is True
    assert metadata["normalized_workflow_values"]["graph_payload_storage"] == "inline"
    assert metadata["normalized_workflow_values"]["graph_payload_compression"] == "gzip"
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
    assert summary["execution"]["download_alphafold_structures"] is True
    assert summary["execution"]["download_pdb_structures"] is True
    assert summary["export"]["graph_payload_storage"] == "inline"
    assert summary["export"]["graph_payload_compression"] == "gzip"


def test_cli_workflow_run_passes_structure_download_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descriptor = base_workflow_descriptor()
    descriptor["execution"]["download_alphafold_structures"] = False
    descriptor["execution"]["download_pdb_structures"] = False
    descriptor["export"]["output_dir"] = str(tmp_path / "out")
    config_path = tmp_path / "workflow.yml"
    config_path.write_text(yaml.safe_dump(descriptor), encoding="utf-8")
    CAPTURED_WORKFLOW_KWARGS.clear()
    monkeypatch.setattr(workflows_cli, "MainWorkflow", CapturingWorkflow)
    monkeypatch.setattr(workflows_cli, "UniprotInterface", PlaceholderUniprotInterface)

    result = CliRunner().invoke(workflow_app, ["--config", str(config_path)])

    assert result.exit_code == 0, result.output
    assert CAPTURED_WORKFLOW_KWARGS["download_alphafold_structures"] is False
    assert CAPTURED_WORKFLOW_KWARGS["download_pdb_structures"] is False
    assert CAPTURED_WORKFLOW_KWARGS["output_dir"] == str(tmp_path / "out")
    metadata = workflows_cli.load_workflow_recipe(tmp_path / "out" / "metadata.json")
    summary = yaml.safe_load((tmp_path / "out" / "run_summary.yml").read_text(encoding="utf-8"))
    assert metadata["normalized_workflow_values"]["download_alphafold_structures"] is False
    assert metadata["normalized_workflow_values"]["download_pdb_structures"] is False
    assert summary["execution"]["download_alphafold_structures"] is False
    assert summary["execution"]["download_pdb_structures"] is False


def test_graph_payload_file_mode_writes_files_and_lightweight_csv(tmp_path: Path) -> None:
    metadata = graph_enrichment_metadata()

    output_infos = export_workflow_outputs(
        graph_enrichment_data(),
        tmp_path,
        "csv",
        None,
        graph_payload_storage="file",
        graph_payload_compression="gzip",
        workflow_metadata=metadata,
    )

    assert output_infos[0]["graph_payload_directory"] == "graphs/pathwaycommons_neighborhood"
    csv_df = pd.read_csv(tmp_path / "pathwaycommons_neighborhood.csv")
    assert "graph_json" not in csv_df.columns
    assert {"graph_file", "graph_file_size_bytes", "graph_sha256"} <= set(csv_df.columns)
    non_empty_row = csv_df.loc[csv_df["graph_record_count"] == 1].iloc[0]
    graph_file = tmp_path / str(non_empty_row["graph_file"])
    assert graph_file.suffixes[-2:] == [".json", ".gz"]
    assert graph_file.exists()
    assert int(non_empty_row["graph_file_size_bytes"]) == graph_file.stat().st_size
    with gzip.open(graph_file, "rt", encoding="utf-8") as handle:
        assert json.load(handle) == {"@graph": [{"id": "node-1"}]}
    empty_row = csv_df.loc[csv_df["graph_record_count"] == 0].iloc[0]
    assert pd.isna(empty_row["graph_file"])
    assert output_infos[0]["graph_payload_files_written"] == 1
    label_metadata = metadata["uniprot_enrichment"]["pathwaycommons_neighborhood"]
    assert label_metadata["graph_payload_storage"] == "file"
    assert label_metadata["graph_payload_compression"] == "gzip"
    assert label_metadata["graph_payload_directory"] == "graphs/pathwaycommons_neighborhood"


def test_graph_payload_inline_mode_preserves_graph_json(tmp_path: Path) -> None:
    metadata = graph_enrichment_metadata()

    output_infos = export_workflow_outputs(
        graph_enrichment_data(),
        tmp_path,
        "csv",
        None,
        graph_payload_storage="inline",
        graph_payload_compression="gzip",
        workflow_metadata=metadata,
    )

    csv_df = pd.read_csv(tmp_path / "pathwaycommons_neighborhood.csv")
    assert "graph_json" in csv_df.columns
    assert "graph_file" not in csv_df.columns
    assert "graph_payload_directory" not in output_infos[0]
    assert not (tmp_path / "graphs").exists()
    label_metadata = metadata["uniprot_enrichment"]["pathwaycommons_neighborhood"]
    assert label_metadata["graph_payload_storage"] == "inline"


def test_graph_payload_none_mode_drops_graph_json_without_writing_files(tmp_path: Path) -> None:
    metadata = graph_enrichment_metadata()

    output_infos = export_workflow_outputs(
        graph_enrichment_data(),
        tmp_path,
        "csv",
        None,
        graph_payload_storage="none",
        graph_payload_compression="gzip",
        workflow_metadata=metadata,
    )

    csv_df = pd.read_csv(tmp_path / "pathwaycommons_neighborhood.csv")
    assert "graph_json" not in csv_df.columns
    assert "graph_file" not in csv_df.columns
    assert "graph_payload_directory" not in output_infos[0]
    assert not (tmp_path / "graphs").exists()
    label_metadata = metadata["uniprot_enrichment"]["pathwaycommons_neighborhood"]
    assert label_metadata["graph_payload_storage"] == "none"


def test_graph_payload_both_mode_keeps_inline_and_file_metadata(tmp_path: Path) -> None:
    output_infos = export_workflow_outputs(
        graph_enrichment_data(),
        tmp_path,
        "csv",
        None,
        graph_payload_storage="both",
        graph_payload_compression="none",
    )

    csv_df = pd.read_csv(tmp_path / "pathwaycommons_neighborhood.csv")
    assert "graph_json" in csv_df.columns
    assert "graph_file" in csv_df.columns
    graph_file = tmp_path / str(csv_df.loc[csv_df["graph_record_count"] == 1, "graph_file"].iloc[0])
    assert graph_file.suffix == ".json"
    assert json.loads(graph_file.read_text(encoding="utf-8")) == {"@graph": [{"id": "node-1"}]}
    assert output_infos[0]["graph_payload_files_written"] == 1
