"""CLI tests for ``silkroute workflow validate-config`` (offline, no execution)."""

from __future__ import annotations

import json
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


def _validate(tmp_path, text):
    """Run ``workflow validate-config --json`` and return (exit code, parsed errors)."""
    result = runner.invoke(app, ["workflow", "validate-config", _write(tmp_path, text), "--json"])
    return result.exit_code, json.loads(result.stdout)


def test_validate_accepts_valid_descriptor(tmp_path):
    result = runner.invoke(app, ["workflow", "validate-config", _write(tmp_path, VALID_DESCRIPTOR)])
    assert result.exit_code == 0
    assert _validate(tmp_path, VALID_DESCRIPTOR) == (0, [])


def test_validate_reports_each_problem_with_its_path(tmp_path):
    bad = VALID_DESCRIPTOR.replace("modality: protein", "modality: rna").replace(
        "execution: {}", "execution:\n  api_key: leaked\n  max_workers: five"
    )
    code, errors = _validate(tmp_path, bad)
    assert code == 2
    assert {error["path"] for error in errors} == {
        "dataset.modality",
        "execution.api_key",
        "execution.max_workers",
    }


def test_validate_collects_several_errors_in_one_section(tmp_path):
    bad = VALID_DESCRIPTOR.replace("value: P12345", "value: P12345\n  fields: [a, 2, c, 4]\n  bogus: 1")
    code, errors = _validate(tmp_path, bad)
    assert code == 2
    assert {error["path"] for error in errors} == {"query.fields[1]", "query.bogus"}


def test_validate_reports_missing_section_and_schema_version(tmp_path):
    bad = VALID_DESCRIPTOR.replace("export:\n  format: csv\n", "").replace(
        'schema_version: "workflow-v1"\n', ""
    )
    code, errors = _validate(tmp_path, bad)
    assert code == 2
    assert {error["path"] for error in errors} == {"export", "schema_version"}


def test_validate_reports_missing_file_at_root(tmp_path):
    result = runner.invoke(app, ["workflow", "validate-config", str(tmp_path / "nope.yml"), "--json"])
    assert result.exit_code == 2
    assert [error["path"] for error in json.loads(result.stdout)] == [""]


def test_validate_plain_mode_prints_path_lines_to_stderr(tmp_path):
    bad = VALID_DESCRIPTOR.replace("format: csv", "format: xlsx")
    result = runner.invoke(app, ["workflow", "validate-config", _write(tmp_path, bad)])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr.startswith("export.format: ")


def test_validate_catches_query_composition_mismatch(tmp_path):
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
    code, errors = _validate(tmp_path, bad)
    assert code == 2
    assert [error["path"] for error in errors] == ["query.composition"]


def test_collect_non_mapping_root():
    assert [error["path"] for error in collect_workflow_recipe_errors(["not", "a", "map"])] == [""]
