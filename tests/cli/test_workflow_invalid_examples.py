"""Offline tests for intentionally invalid workflow YAML examples."""

from __future__ import annotations

from pathlib import Path

import pytest

from bioseq_dl.cli.workflows import load_workflow_recipe, validate_workflow_recipe

REPO_ROOT = Path(__file__).resolve().parents[2]
INVALID_WORKFLOW_DIR = REPO_ROOT / "examples" / "workflows" / "invalid"

EXPECTED_ERRORS = {
    "missing_schema_version.yml": "missing required top-level key 'schema_version'",
    "unsupported_schema_version.yml": "Unsupported workflow schema_version 'workflow-v2'",
    "forbidden_version_key.yml": "Unknown workflow YAML key 'version'",
    "unknown_top_level_section.yml": "Unknown workflow YAML section 'resoures'",
    "invalid_query_composition.yml": r"query\.composition\[0\]\.label",
}


@pytest.mark.parametrize(
    ("filename", "expected_error"),
    sorted(EXPECTED_ERRORS.items()),
)
def test_invalid_workflow_examples_raise_expected_errors(filename: str, expected_error: str) -> None:
    recipe = load_workflow_recipe(INVALID_WORKFLOW_DIR / filename)

    with pytest.raises((TypeError, ValueError), match=expected_error):
        validate_workflow_recipe(recipe)
