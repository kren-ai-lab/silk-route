"""Offline structural tests for workflow example notebooks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK_DIR = REPO_ROOT / "examples" / "notebooks"
FUTURE_ONLY_FIELDS = (
    "interaction_retrieval",
    "activity_retrieval",
    "chemical_metadata_integration",
    "protein_target_integration",
    "temperature_enrichment",
    "cross_source_integration",
    "workflow_execution_time_seconds",
    "retrieved_records",
    "unique_sequences",
    "result_files",
)
CREDENTIAL_LIKE_STRINGS = ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "PRIVATE_KEY")
LOCAL_PATH_PATTERNS = ("C:\\", "/Users/", "/home/")


def iter_notebook_paths() -> list[Path]:
    """Return workflow notebook example paths."""
    return sorted(NOTEBOOK_DIR.glob("*.ipynb"))


@pytest.mark.parametrize("notebook_path", iter_notebook_paths(), ids=lambda path: path.name)
def test_workflow_notebooks_are_parseable_and_documented(notebook_path: Path) -> None:
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    cells = notebook.get("cells", [])
    markdown_cells = [cell for cell in cells if cell.get("cell_type") == "markdown"]
    code_cells = [cell for cell in cells if cell.get("cell_type") == "code"]
    markdown_text = "\n".join("".join(cell.get("source", [])) for cell in markdown_cells)

    assert markdown_cells
    assert code_cells
    assert "BioSeqDownloader" in markdown_text or "workflow YAML" in markdown_text


@pytest.mark.parametrize("notebook_path", iter_notebook_paths(), ids=lambda path: path.name)
def test_workflow_notebooks_do_not_contain_credentials_or_local_paths(notebook_path: Path) -> None:
    notebook_text = notebook_path.read_text(encoding="utf-8")

    for credential_text in CREDENTIAL_LIKE_STRINGS:
        assert credential_text not in notebook_text
    for local_path_pattern in LOCAL_PATH_PATTERNS:
        assert local_path_pattern not in notebook_text


@pytest.mark.parametrize("notebook_path", iter_notebook_paths(), ids=lambda path: path.name)
def test_workflow_notebooks_do_not_claim_future_fields_are_executable(notebook_path: Path) -> None:
    notebook_text = notebook_path.read_text(encoding="utf-8").lower()

    assert "future-only yaml fields are executable" not in notebook_text
    for field in FUTURE_ONLY_FIELDS:
        normalized_field = field.lower()
        forbidden_claims = (
            f"{normalized_field} is executable",
            f"`{normalized_field}` is executable",
            f"{normalized_field} controls execution",
            f"`{normalized_field}` controls execution",
            f"{normalized_field} activates",
            f"`{normalized_field}` activates",
        )
        for forbidden_claim in forbidden_claims:
            assert forbidden_claim not in notebook_text
