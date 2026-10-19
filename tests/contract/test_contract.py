"""Shared ecosystem CLI contract: exit codes, record ids, ``validate --json`` and provenance sidecars.

Runs the CLI offline (mocked UniProt endpoint) and validates the documents against the contract schemas.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest
from jsonschema import Draft202012Validator
from niquests_mock import startswith
from typer.testing import CliRunner

from silkroute.cli.main import app
from silkroute.core.interfaces.uniprot import API_URL

SCHEMAS = Path(__file__).parent
runner = CliRunner()


def _schema(name: str):
    """Return a validator for one of the contract schemas."""
    return Draft202012Validator(json.loads((SCHEMAS / name).read_text(encoding="utf-8")))


def _config(tmp_path: Path, out: Path, extra_query: str = "") -> Path:
    path = tmp_path / "workflow.yml"
    path.write_text(
        f"""
schema_version: "workflow-v1"
dataset: {{name: demo, modality: protein, mode: query_first}}
query:
  value: "gene:TP53"
{extra_query}
execution: {{enrich: false, total_retries: 1}}
export: {{output_dir: "{out}", format: csv}}
""",
        encoding="utf-8",
    )
    return path


def _mock_uniprot(niquests_mock, accessions: list[str]) -> None:
    results = [
        {"primaryAccession": accession, "uniProtkbId": f"{accession}_HUMAN"} for accession in accessions
    ]
    niquests_mock.get(url=startswith(f"{API_URL}/uniprotkb/search")).respond(
        status_code=200,
        json={"results": results},
        headers={"x-total-results": str(len(results))},
    )


def test_validate_json_output_conforms_to_schema(tmp_path):
    bad = tmp_path / "bad.yml"
    bad.write_text("schema_version: workflow-v1\nexport: {format: xlsx}\n", encoding="utf-8")

    result = runner.invoke(app, ["workflow", "validate-config", str(bad), "--json"])

    assert result.exit_code == 2
    errors = json.loads(result.stdout)
    assert errors
    _schema("validate-errors.schema.json").validate(errors)


def test_workflow_run_writes_ids_and_provenance(tmp_path, niquests_mock):
    _mock_uniprot(niquests_mock, ["P12345", "Q99999"])
    out = tmp_path / "out"
    config = _config(tmp_path, out, "  fields: [gene_primary]")

    result = runner.invoke(app, ["workflow", "run", "--config", str(config)])

    assert result.exit_code == 0, result.output
    table = pl.read_csv(out / "uniprot_results.csv", infer_schema=False)
    # the id column leads and the native key survives the user's field projection
    assert table.columns[0] == "id"
    assert table["id"].to_list() == table["accession"].to_list() == ["P12345", "Q99999"]
    document = json.loads(out.with_name("out.provenance.json").read_text(encoding="utf-8"))
    _schema("provenance.schema.json").validate(document)
    assert document["command"] == "workflow run"
    assert document["extensions"]["status"] == "success"
    assert "output" not in document["parameters"]
    assert (out / "metadata.json").exists()


def test_workflow_run_duplicate_ids_exit_3(tmp_path, niquests_mock):
    _mock_uniprot(niquests_mock, ["P12345", "P12345"])
    out = tmp_path / "out"

    result = runner.invoke(app, ["workflow", "run", "--config", str(_config(tmp_path, out))])

    assert result.exit_code == 3
    assert not out.with_name("out.provenance.json").exists()


def test_workflow_run_invalid_config_exits_2(tmp_path):
    config = _config(tmp_path, tmp_path / "out", "  bogus: 1")

    result = runner.invoke(app, ["workflow", "run", "--config", str(config)])

    assert result.exit_code == 2


def test_workflow_run_unexpected_error_exits_4(tmp_path, monkeypatch):
    def boom(*_args, **_kwargs):
        raise KeyError("bug")

    monkeypatch.setattr("silkroute.cli.workflows.MainWorkflow.run", boom)

    result = runner.invoke(app, ["workflow", "run", "--config", str(_config(tmp_path, tmp_path / "out"))])

    assert result.exit_code == 4
    assert "KeyError" in result.stderr


@pytest.mark.usefixtures("_patch_kegg")
def test_fetch_sidecar_conforms_to_schema(tmp_path):
    out = tmp_path / "out.csv"

    result = runner.invoke(app, ["fetch", "kegg", "get", "hsa:1", "-o", str(out)])

    assert result.exit_code == 0, result.output
    document = json.loads((tmp_path / "out.csv.provenance.json").read_text(encoding="utf-8"))
    _schema("provenance.schema.json").validate(document)
    assert document["command"] == "fetch kegg get"
    assert document["extensions"]["api_name"] == "kegg"


@pytest.fixture
def _patch_kegg(monkeypatch):
    class FakeKEGG:
        def __init__(self, *args, **kwargs):
            pass

        def fetch_single(self, *args, **kwargs):
            return pl.DataFrame({"id": ["hsa:1"]}), {"api_name": "kegg"}

    monkeypatch.setattr("silkroute.cli.interfaces.kegg.KEGGInterface", FakeKEGG)


def test_workflow_run_failed_request_exits_3(tmp_path, niquests_mock):
    niquests_mock.get(url=startswith(f"{API_URL}/uniprotkb/search")).respond(status_code=500)
    out = tmp_path / "out"

    result = runner.invoke(app, ["workflow", "run", "--config", str(_config(tmp_path, out))])

    assert result.exit_code == 3
    assert not out.with_name("out.provenance.json").exists()


def test_chemical_search_sidecar_sits_next_to_results(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "silkroute.cli.interfaces.chemical_search_query.pubchem_search_query",
        lambda *_args, **_kwargs: (pl.DataFrame({"cid": ["2244"]}), {"api_name": "pubchem"}),
    )
    out = tmp_path / "out"

    result = runner.invoke(app, ["search", "chemical", "aspirin", "--databases", "pubchem", "-o", str(out)])

    assert result.exit_code == 0, result.output
    document = json.loads((out / "pubchem_results.csv.provenance.json").read_text(encoding="utf-8"))
    _schema("provenance.schema.json").validate(document)
    assert document["command"] == "search chemical"
    assert not (out / "pubchem_metadata.json").exists()


def test_search_uniprot_query_writes_ids_and_sidecar(tmp_path, niquests_mock):
    _mock_uniprot(niquests_mock, ["P12345", "Q99999"])
    out = tmp_path / "out"

    result = runner.invoke(app, ["search", "uniprot", "by-query", "-q", "gene:TP53", "-o", str(out)])

    assert result.exit_code == 0, result.output
    table = pl.read_csv(out / "uniprot_results.csv", infer_schema=False)
    assert table.columns[0] == "id"
    assert table["id"].to_list() == ["P12345", "Q99999"]
    document = json.loads((out / "uniprot_results.csv.provenance.json").read_text(encoding="utf-8"))
    _schema("provenance.schema.json").validate(document)


def test_crossref_writes_sidecar(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "silkroute.cli.interfaces.uniprot_crossref.CrossRefEnricher.enrich",
        lambda *_args, **_kwargs: (pl.DataFrame({"accession": ["P12345"]}), {"api_name": "uniprot"}),
    )
    ids = tmp_path / "ids.csv"
    ids.write_text("accession\nP12345\n", encoding="utf-8")
    out = tmp_path / "out"

    result = runner.invoke(
        app, ["search", "uniprot", "crossrefs", "-i", str(ids), "-o", str(out), "-d", "pdb"]
    )

    assert result.exit_code == 0, result.output
    document = json.loads((out / "ids_results.csv.provenance.json").read_text(encoding="utf-8"))
    _schema("provenance.schema.json").validate(document)


def test_crossref_missing_input_exits_3(tmp_path):
    result = runner.invoke(
        app, ["search", "uniprot", "crossrefs", "-i", str(tmp_path / "nope.csv"), "-o", str(tmp_path / "out")]
    )

    assert result.exit_code == 3


def test_search_sequences_missing_column_exits_3(tmp_path):
    ids = tmp_path / "seqs.csv"
    ids.write_text("other\nMKV\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["search", "uniprot", "by-sequences", "-d", "swissprot", "-i", str(ids), "-o", str(tmp_path / "out")],
    )

    assert result.exit_code == 3
