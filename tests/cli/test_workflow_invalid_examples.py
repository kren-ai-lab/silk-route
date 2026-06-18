"""Offline tests for intentionally invalid workflow YAML examples."""

from __future__ import annotations

from pathlib import Path

import pytest

from bioseq_dl.cli.workflows import load_workflow_recipe, validate_workflow_recipe

REPO_ROOT = Path(__file__).resolve().parents[2]
INVALID_WORKFLOW_DIR = REPO_ROOT / "examples" / "workflows" / "invalid"
CREDENTIAL_LIKE_STRINGS = ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "PRIVATE_KEY")
LOCAL_PATH_PATTERNS = ("C:\\", "/Users/", "/home/")

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


@pytest.mark.parametrize("filename", sorted(EXPECTED_ERRORS))
def test_invalid_workflow_examples_do_not_contain_credentials_or_local_paths(filename: str) -> None:
    text = (INVALID_WORKFLOW_DIR / filename).read_text(encoding="utf-8")

    for credential_text in CREDENTIAL_LIKE_STRINGS:
        assert credential_text not in text
    for local_path_pattern in LOCAL_PATH_PATTERNS:
        assert local_path_pattern not in text
