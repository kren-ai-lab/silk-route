"""Smoke tests for the top-level CLI app."""

from __future__ import annotations

from typer.testing import CliRunner

from silkroute import __version__
from silkroute.cli.main import app

runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"silkroute {__version__}"
    assert __version__ in result.stdout


def test_help_flag() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "silkroute" in result.stdout
    assert "workflow" in result.stdout
    assert "search" in result.stdout
    assert "fetch" in result.stdout


def test_workflow_validate_example_descriptor() -> None:
    result = runner.invoke(
        app, ["workflow", "validate", "examples/workflows/protein_query_first_minimal.yml"]
    )

    assert result.exit_code == 0
    assert "is a valid workflow descriptor" in result.stdout
