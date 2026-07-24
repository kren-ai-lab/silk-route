"""Offline structural tests for workflow example notebooks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK_DIR = REPO_ROOT / "examples" / "notebooks"


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
    assert "SilkRoute" in markdown_text or "workflow YAML" in markdown_text
