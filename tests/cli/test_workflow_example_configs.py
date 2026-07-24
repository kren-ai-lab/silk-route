"""Offline validation tests for workflow example YAML descriptors."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from silkroute.cli.workflows import WORKFLOW_SCHEMA_VERSION, load_workflow_recipe, validate_workflow_recipe

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO_ROOT / "examples" / "workflows"
REFERENCE_FILENAME = "full_options_reference.yml"
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


def iter_valid_example_paths() -> list[Path]:
    """Return runnable workflow example descriptors."""
    return [path for path in sorted(WORKFLOW_DIR.glob("*.yml")) if path.name != REFERENCE_FILENAME]


def iter_example_asset_paths() -> list[Path]:
    """Return shipped workflow example assets (workflow YAML + workflow notebooks)."""
    notebook_dir = REPO_ROOT / "examples" / "notebooks"
    return sorted([*WORKFLOW_DIR.rglob("*.yml"), *notebook_dir.glob("*.ipynb")])


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


@pytest.mark.parametrize("asset_path", iter_example_asset_paths(), ids=lambda path: path.name)
def test_example_assets_do_not_contain_credentials_or_local_paths(asset_path: Path) -> None:
    text = asset_path.read_text(encoding="utf-8")

    for credential_text in CREDENTIAL_LIKE_STRINGS:
        assert credential_text not in text
    for local_path_pattern in LOCAL_PATH_PATTERNS:
        assert local_path_pattern not in text


def test_canonical_workflow_yaml_examples_live_under_workflows_directory() -> None:
    canonical_files = [path for path in WORKFLOW_DIR.glob("*.yml") if path.name != REFERENCE_FILENAME]

    assert canonical_files
    assert all(path.parent == WORKFLOW_DIR for path in canonical_files)
