"""Offline validation tests for workflow example YAML descriptors."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml
from typer.testing import CliRunner

import bioseq_dl.cli.workflows as workflows_cli
from bioseq_dl.cli.workflows import (
    WORKFLOW_SCHEMA_VERSION,
    load_workflow_recipe,
    validate_workflow_recipe,
)
from bioseq_dl.cli.workflows import (
    app as workflow_app,
)
from bioseq_dl.core.workflow.main_workflow import build_compound_source_query_structure

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO_ROOT / "examples" / "workflows"
DOCS_PATH = REPO_ROOT / "docs" / "workflow_yaml.md"
REFERENCE_FILENAME = "full_options_reference.yml"
REMOVED_LEGACY_WORKFLOW_FILENAMES = {
    "protein-dataset-construction.yml",
    "compound-dataset-construction.yml",
    "interaction-aware-dataset-construction.yml",
    "disease_query.yml",
}
FUTURE_ONLY_SECTIONS = {
    "interaction_retrieval",
    "activity_retrieval",
    "chemical_metadata_integration",
    "protein_target_integration",
    "temperature_enrichment",
    "cross_source_integration",
}
GENERATED_REPORTING_FIELDS = {
    "workflow_execution_time_seconds",
    "retrieved_records",
    "unique_sequences",
}
MISLEADING_EXPORT_PLACEHOLDERS = {"result_files"}
REQUIRED_EXECUTABLE_SECTIONS = {"schema_version", "dataset", "query", "export"}
LOCAL_PATH_PATTERNS = ("C:\\", "/Users/", "/home/")
CREDENTIAL_LIKE_STRINGS = ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "PRIVATE_KEY")
COMPOUND_SOURCE_EXAMPLE_EXPECTATIONS = {
    "compound_pubchem_name.yml": ("pubchem", "pubchem_results.csv"),
    "compound_pubchem_substructure.yml": ("pubchem", "pubchem_results.csv"),
    "compound_chebi_name.yml": ("chebi", "chebi_results.csv"),
}


class FakeExampleWorkflow:
    """Workflow test double that returns source-aware compound results without API calls."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        """Initialize the fake workflow."""

    def run(
        self,
        *,
        mode: str,
        modality: str,
        query: str,
        **_kwargs: Any,
    ) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
        """Return deterministic source-aware data and metadata for example CLI tests."""
        request_plan = build_compound_source_query_structure(query)
        if request_plan is None:
            msg = f"Unexpected non-source query in example test: {query}"
            raise AssertionError(msg)
        source = str(request_plan["source"])
        data = {
            source: pd.DataFrame(
                [
                    {
                        "source": source,
                        "compound_id": "PUBCHEM:5793" if source == "pubchem" else "CHEBI:27732",
                        "name": "glucose" if source == "pubchem" else "caffeine",
                    }
                ]
            )
        }
        metadata = {
            "mode": mode,
            "modality": modality,
            "origin": "query",
            "query_source": source,
            "query_resource": request_plan.get("resource"),
            "query_model": request_plan.get("query_model"),
            "request_plan": request_plan,
            "number_of_records": 1,
            source: {
                "fetch": {
                    "api_name": "PubChem" if source == "pubchem" else "ChEBI",
                    "method": "workflow/compound-properties" if source == "pubchem" else "es_search",
                    "fetched_length": 1,
                    "data_info": {"total_entries": 1, "data_type": "list", "columns": []},
                },
                "request_plan": request_plan,
                "number_of_records": 1,
            },
        }
        return data, metadata


class FakeUniprotInterface:
    """Placeholder to keep CLI example tests fully offline."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        """Initialize the fake UniProt interface."""


def iter_valid_example_paths() -> list[Path]:
    """Return runnable workflow example descriptors."""
    return [
        path
        for path in sorted(WORKFLOW_DIR.glob("*.yml"))
        if path.name != REFERENCE_FILENAME
    ]


def iter_workflow_yaml_paths() -> list[Path]:
    """Return every organized workflow YAML example descriptor."""
    return sorted(WORKFLOW_DIR.rglob("*.yml"))


def collect_mapping_keys(value: Any) -> set[str]:
    """Return all mapping keys found in a nested YAML-compatible value."""
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, nested_value in value.items():
            if isinstance(key, str):
                keys.add(key)
            keys.update(collect_mapping_keys(nested_value))
    elif isinstance(value, list):
        for item in value:
            keys.update(collect_mapping_keys(item))
    return keys


@pytest.mark.parametrize(
    ("filename", "expected"),
    sorted(COMPOUND_SOURCE_EXAMPLE_EXPECTATIONS.items()),
)
def test_compound_source_workflow_examples_execute_through_cli_without_api_calls(
    filename: str,
    expected: tuple[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, expected_output_file = expected
    config_path = WORKFLOW_DIR / filename
    output_dir = tmp_path / config_path.stem
    recipe = load_workflow_recipe(config_path)
    normalized = validate_workflow_recipe(recipe)
    monkeypatch.setattr(workflows_cli, "MainWorkflow", FakeExampleWorkflow)
    monkeypatch.setattr(workflows_cli, "UniprotInterface", FakeUniprotInterface)

    result = CliRunner().invoke(
        workflow_app,
        ["--config", str(config_path), "--output", str(output_dir)],
    )

    assert result.exit_code == 0, result.output
    assert normalized["schema_version"] == WORKFLOW_SCHEMA_VERSION
    assert (output_dir / expected_output_file).exists()
    assert (output_dir / "metadata.json").exists()
    assert (output_dir / "run_summary.yml").exists()

    metadata = workflows_cli.load_workflow_recipe(output_dir / "metadata.json")
    summary = yaml.safe_load((output_dir / "run_summary.yml").read_text(encoding="utf-8"))
    assert metadata["workflow_metadata"]["query_source"] == source
    assert metadata["workflow_metadata"]["query_resource"] in {"compound", "structure", "entity"}
    assert metadata["workflow_metadata"]["query_model"] in {
        "compound_lookup",
        "structure_search",
        "advanced_search",
    }
    assert metadata["workflow_metadata"]["number_of_records"] == 1
    assert metadata["workflow_metadata"]["request_plan"]["source"] == source
    assert metadata["output_files"][0]["file"] == expected_output_file
    assert metadata["output_files"][0]["category"] == "result"
    assert summary["query"]["source"] == source
    assert summary["query"]["resource"] == metadata["workflow_metadata"]["query_resource"]
    assert summary["query"]["model"] == metadata["workflow_metadata"]["query_model"]
    assert summary["query"]["request_plan"]["source"] == source
    assert summary["execution"]["number_of_records"] == 1
    assert summary["outputs"][Path(expected_output_file).stem]["file"] == expected_output_file


@pytest.mark.parametrize("config_path", iter_valid_example_paths(), ids=lambda path: path.name)
def test_valid_workflow_examples_validate_offline(config_path: Path) -> None:
    recipe = load_workflow_recipe(config_path)
    normalized = validate_workflow_recipe(recipe)

    assert normalized["schema_version"] == WORKFLOW_SCHEMA_VERSION
    assert normalized["query"]
    assert normalized["query_descriptor"]["value"] == normalized["query"]

    output_dir = Path(normalized["output"])
    assert output_dir.parts[:2] == ("examples", "results")


@pytest.mark.parametrize("config_path", iter_valid_example_paths(), ids=lambda path: path.name)
def test_executable_workflow_examples_are_minimal_and_honest(config_path: Path) -> None:
    recipe = load_workflow_recipe(config_path)

    assert set(recipe) >= REQUIRED_EXECUTABLE_SECTIONS
    assert recipe["schema_version"] == WORKFLOW_SCHEMA_VERSION
    assert isinstance(recipe["query"]["value"], str)
    assert recipe["query"]["value"].strip()
    assert not (FUTURE_ONLY_SECTIONS & set(recipe))

    all_keys = collect_mapping_keys(recipe)
    assert not (GENERATED_REPORTING_FIELDS & all_keys)
    assert not (MISLEADING_EXPORT_PLACEHOLDERS & all_keys)


@pytest.mark.parametrize("config_path", iter_valid_example_paths(), ids=lambda path: path.name)
def test_chembl_examples_use_small_page_cap(config_path: Path) -> None:
    recipe = load_workflow_recipe(config_path)
    dataset = recipe.get("dataset", {})
    query_value = recipe.get("query", {}).get("value", "")
    is_chembl_example = (
        "chembl" in config_path.stem
        or dataset.get("primary_data_source") == "chembl"
        or "ic50:" in query_value.lower()
    )

    if is_chembl_example:
        assert recipe.get("execution", {}).get("chembl_pages_to_fetch") == 1


def test_reference_workflow_descriptor_is_excluded_from_executable_examples() -> None:
    executable_names = {path.name for path in iter_valid_example_paths()}
    reference_path = WORKFLOW_DIR / REFERENCE_FILENAME

    assert REFERENCE_FILENAME not in executable_names
    assert reference_path.exists()
    assert validate_workflow_recipe(load_workflow_recipe(reference_path))["schema_version"] == (
        WORKFLOW_SCHEMA_VERSION
    )


@pytest.mark.parametrize("config_path", iter_workflow_yaml_paths(), ids=lambda path: path.name)
def test_workflow_yaml_examples_do_not_contain_credentials_or_local_paths(config_path: Path) -> None:
    text = config_path.read_text(encoding="utf-8")

    for credential_text in CREDENTIAL_LIKE_STRINGS:
        assert credential_text not in text
    for local_path_pattern in LOCAL_PATH_PATTERNS:
        assert local_path_pattern not in text


def test_workflow_yaml_docs_separate_current_preserved_and_future_fields() -> None:
    docs = DOCS_PATH.read_text(encoding="utf-8")

    assert "Current executable fields are the fields that should be used to control" in docs
    assert "Preserved metadata fields are accepted by the schema" in docs
    assert "## Future Workflow YAML Features" in docs
    assert "These features are not part of the current executable workflow behavior." in docs
    assert (
        "They are documented as possible future extensions and must not be used as active fields "
        "in executable examples until implementation and tests exist."
    ) in docs
    assert "`query.value` is the only executable query field." in docs
    assert "`query.builder` and" in docs
    assert "`query.composition` are preserved GUI-oriented metadata" in docs
    assert "If `query.composition` is present, it must match the executable `query.value`." in docs


def test_no_old_top_level_workflow_yaml_examples_remain() -> None:
    top_level_workflow_yaml_files = {
        path.name
        for path in (REPO_ROOT / "examples").glob("*.yml")
        if path.name in REMOVED_LEGACY_WORKFLOW_FILENAMES
    }

    assert not top_level_workflow_yaml_files


def test_canonical_workflow_yaml_examples_live_under_workflows_directory() -> None:
    canonical_files = [path for path in WORKFLOW_DIR.glob("*.yml") if path.name != REFERENCE_FILENAME]

    assert canonical_files
    assert all(path.parent == WORKFLOW_DIR for path in canonical_files)
