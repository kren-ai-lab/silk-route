"""CLI tests for ``bioseq-dl workflow validate`` (offline, no execution)."""

from __future__ import annotations

import textwrap

from typer.testing import CliRunner

from bioseq_dl.cli.main import app

runner = CliRunner()

VALID_DESCRIPTOR = textwrap.dedent(
    """
    dataset:
      name: demo
      modality: protein
      mode: query_first
    query:
      value: P12345
    execution: {}
    export:
      format: csv
    """
)


def _write(tmp_path, text):
    path = tmp_path / "workflow.yml"
    path.write_text(text)
    return str(path)


def test_validate_accepts_valid_descriptor(tmp_path):
    result = runner.invoke(app, ["workflow", "validate", _write(tmp_path, VALID_DESCRIPTOR)])
    assert result.exit_code == 0
    assert "valid workflow descriptor" in result.stdout
    assert "modality: protein" in result.stdout
    assert "mode: query_first" in result.stdout


def test_validate_rejects_unknown_modality(tmp_path):
    bad = VALID_DESCRIPTOR.replace("modality: protein", "modality: rna")
    result = runner.invoke(app, ["workflow", "validate", _write(tmp_path, bad)])
    assert result.exit_code == 1
    assert "Unsupported dataset.modality" in result.output


def test_validate_rejects_missing_required_section(tmp_path):
    no_export = VALID_DESCRIPTOR.replace("export:\n  format: csv\n", "")
    result = runner.invoke(app, ["workflow", "validate", _write(tmp_path, no_export)])
    assert result.exit_code == 1
    assert "missing required top-level section" in result.output


def test_validate_rejects_credential_key(tmp_path):
    with_secret = VALID_DESCRIPTOR.replace("execution: {}", "execution:\n  api_key: leaked")
    result = runner.invoke(app, ["workflow", "validate", _write(tmp_path, with_secret)])
    assert result.exit_code == 1
    assert "Credentials must be provided" in result.output


def test_validate_reports_missing_file(tmp_path):
    result = runner.invoke(app, ["workflow", "validate", str(tmp_path / "nope.yml")])
    assert result.exit_code == 1
    assert "does not exist" in result.output
