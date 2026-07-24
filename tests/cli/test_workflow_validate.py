"""CLI tests for ``silkroute workflow validate`` (offline, no execution)."""

from __future__ import annotations

import textwrap

from typer.testing import CliRunner

from silkroute.cli.main import app
from silkroute.cli.workflows import collect_workflow_recipe_errors

runner = CliRunner()

VALID_DESCRIPTOR = textwrap.dedent(
    """
    schema_version: "workflow-v1"
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


def test_validate_reports_missing_schema_version(tmp_path):
    no_version = VALID_DESCRIPTOR.replace('schema_version: "workflow-v1"\n', "")
    result = runner.invoke(app, ["workflow", "validate", _write(tmp_path, no_version)])
    assert result.exit_code == 1
    assert "missing required top-level key 'schema_version'" in result.output


def test_validate_reports_unsupported_schema_version(tmp_path):
    bad = VALID_DESCRIPTOR.replace('schema_version: "workflow-v1"', 'schema_version: "workflow-v2"')
    result = runner.invoke(app, ["workflow", "validate", _write(tmp_path, bad)])
    assert result.exit_code == 1
    assert "Unsupported workflow schema_version" in result.output


def test_validate_reports_missing_file(tmp_path):
    result = runner.invoke(app, ["workflow", "validate", str(tmp_path / "nope.yml")])
    assert result.exit_code == 1
    assert "does not exist" in result.output


def test_validate_reports_all_errors_at_once(tmp_path):
    # Three independent problems across sections + a credential key.
    bad = textwrap.dedent(
        """
        dataset:
          name: demo
          modality: rna
          mode: not_a_mode
        query:
          value: P12345
        execution:
          api_key: leaked
        export:
          format: xlsx
        """
    )
    result = runner.invoke(app, ["workflow", "validate", _write(tmp_path, bad)])
    assert result.exit_code == 1
    assert "validation error(s):" in result.output
    # dataset modality, export format, and the credential key all reported together.
    assert "Unsupported dataset.modality" in result.output
    assert "Unsupported export format" in result.output
    assert "Credentials must be provided" in result.output


def test_validate_reports_query_composition_mismatch(tmp_path):
    # Cross-section check: collected as an error, not raised as a traceback.
    bad = textwrap.dedent(
        """
        schema_version: "workflow-v1"
        dataset:
          name: demo
          modality: protein
          mode: query_composition
        query:
          value: "gene:TP53=tp53"
          composition:
            - label: brca1
              value: "gene:BRCA1"
        execution: {}
        export:
          format: csv
        """
    )
    result = runner.invoke(app, ["workflow", "validate", _write(tmp_path, bad)])
    assert result.exit_code == 1
    assert "validation error(s):" in result.output
    assert "query.composition does not match executable query.value" in result.output
    assert not isinstance(result.exception, ValueError)


# --- collect_workflow_recipe_errors (unit) ----------------------------------


def test_collect_returns_empty_for_valid():
    recipe = {
        "schema_version": "workflow-v1",
        "dataset": {"name": "d", "modality": "protein", "mode": "query_first"},
        "query": {"value": "P1"},
        "execution": {},
        "export": {"format": "csv"},
    }
    assert collect_workflow_recipe_errors(recipe) == []


def test_collect_accumulates_across_sections():
    recipe = {
        "dataset": {"name": "d", "modality": "rna", "mode": "query_first"},
        "query": {"value": ""},  # blank value
        "execution": {"max_workers": "five"},  # not an int
        "export": {"format": "xlsx"},
    }
    errors = collect_workflow_recipe_errors(recipe)
    assert len(errors) >= 4  # one per broken section


def test_collect_catches_query_composition_mismatch():
    recipe = {
        "schema_version": "workflow-v1",
        "dataset": {"name": "d", "modality": "protein", "mode": "query_composition"},
        "query": {"value": "gene:TP53=tp53", "composition": [{"label": "brca1", "value": "gene:BRCA1"}]},
        "execution": {},
        "export": {"format": "csv"},
    }
    errors = collect_workflow_recipe_errors(recipe)
    assert any("does not match executable query.value" in error for error in errors)


def test_collect_non_mapping_root():
    assert collect_workflow_recipe_errors(["not", "a", "map"]) == ["Workflow YAML root must be a mapping."]
