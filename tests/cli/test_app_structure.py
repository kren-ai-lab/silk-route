"""Smoke tests for the top-level CLI app."""

from __future__ import annotations

from typer.testing import CliRunner

from bioseq_dl import __version__
from bioseq_dl.cli.main import app

runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
