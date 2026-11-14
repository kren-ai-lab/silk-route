"""CLI contract for incremental UniProt workflows."""

from __future__ import annotations

import json

import polars as pl
import pytest
from typer.testing import CliRunner

from silkroute.cli.main import app
from silkroute.core.interfaces.uniprot import UniprotInterface


def _base_args(output):
    return [
        "workflow",
        "run",
        "--modality",
        "protein",
        "--mode",
        "query_first",
        "--query",
        "kinase",
        "--output",
        str(output),
        "--fields",
        "accession",
        "--export-format",
        "parquet",
        "--no-enrich",
    ]


def test_incremental_cli_writes_parts_metadata_and_provenance(tmp_path, monkeypatch):
    def pages(self, *args, **kwargs):
        yield {
            "payload": {
                "results": [
                    {"primaryAccession": "P00001", "sequence": {"value": "AAA"}},
                    {"primaryAccession": "P00002", "sequence": {"value": "BBB"}},
                ]
            },
            "page_number": 1,
            "attempts": 1,
            "next_url": None,
            "total_results": "2",
        }

    monkeypatch.setattr(UniprotInterface, "iter_search_pages", pages)
    output = tmp_path / "output"
    result = CliRunner().invoke(
        app,
        [
            "workflow",
            "run",
            "--modality",
            "protein",
            "--mode",
            "query_first",
            "--query",
            "kinase",
            "--output",
            str(output),
            "--fields",
            "accession,sequence",
            "--export-format",
            "parquet",
            "--no-enrich",
            "--incremental",
            "--chunk-size",
            "1",
        ],
    )
    assert result.exit_code == 0, result.output
    checkpoint = json.loads((output / "uniprot_incremental_checkpoint.json").read_text())
    metadata = json.loads((output / "metadata.json").read_text())
    assert checkpoint["status"] == "completed"
    assert checkpoint["page_size"] == 1
    assert checkpoint["batch_size"] == 1
    assert "deprecated" in result.output.lower()
    assert len(checkpoint["files"]) == 2
    assert metadata["execution"]["status"] == "success"
    assert metadata["normalized_descriptor"]["harmonization"]["id_column"] == "record_id"
    assert len(metadata["output_files"]) == 2
    assert (output / "run_summary.yml").exists()
    assert output.with_name(output.name + ".provenance.json").exists()


def test_incremental_cli_rejects_enrichment_before_request(tmp_path):
    result = CliRunner().invoke(
        app,
        [
            "workflow",
            "run",
            "--modality",
            "protein",
            "--mode",
            "query_first",
            "--query",
            "kinase",
            "--output",
            str(tmp_path),
            "--export-format",
            "parquet",
            "--incremental",
        ],
    )
    assert result.exit_code == 2
    assert "--no-enrich" in result.output


def test_incremental_cli_partial_failure_reports_failed_parts(tmp_path, monkeypatch):
    def pages(self, *args, **kwargs):
        yield {
            "payload": {"results": [{"primaryAccession": "P00001"}]},
            "page_number": 1,
            "attempts": 1,
            "next_url": "cursor",
            "total_results": "2",
        }
        raise RuntimeError("second page unavailable")

    monkeypatch.setattr(UniprotInterface, "iter_search_pages", pages)
    output = tmp_path / "partial"
    result = CliRunner().invoke(
        app,
        [
            "workflow",
            "run",
            "--modality",
            "protein",
            "--mode",
            "query_first",
            "--query",
            "kinase",
            "--output",
            str(output),
            "--fields",
            "accession",
            "--export-format",
            "parquet",
            "--no-enrich",
            "--incremental",
            "--chunk-size",
            "1",
        ],
    )
    assert result.exit_code == 3
    checkpoint = json.loads((output / "uniprot_incremental_checkpoint.json").read_text())
    metadata = json.loads((output / "metadata.json").read_text())
    assert checkpoint["status"] == metadata["execution"]["status"] == "failed"
    assert len(checkpoint["files"]) == len(metadata["output_files"]) == 1
    assert (output / checkpoint["files"][0]["path"]).exists()
    provenance = json.loads(output.with_name(output.name + ".provenance.json").read_text())
    assert provenance["extensions"]["status"] == "failed"


def test_explicit_single_write_mode_keeps_one_legacy_result_file(tmp_path, monkeypatch):
    def submit(self, *args, **kwargs):
        return {"results": [{"primaryAccession": "P00001"}]}, {}

    monkeypatch.setattr(UniprotInterface, "submit_search", submit)
    output = tmp_path / "single"
    result = CliRunner().invoke(app, [*_base_args(output), "--write-mode", "single"])
    assert result.exit_code == 0, result.output
    assert (output / "uniprot_results.parquet").exists()
    assert pl.read_parquet(output / "uniprot_results.parquet")["accession"].to_list() == ["P00001"]
    assert not list(output.glob("uniprot_results_part-*.parquet"))


def test_partitioned_cli_batch_size_is_file_rows_not_http_page_size(tmp_path, monkeypatch):
    requested_pages = []

    def pages(self, *args, **kwargs):
        requested_pages.append(kwargs["page_size"])
        yield {
            "payload": {
                "results": [
                    {"primaryAccession": "P00001"},
                    {"primaryAccession": "P00002"},
                ]
            },
            "attempts": 1,
            "total_results": "2",
        }

    monkeypatch.setattr(UniprotInterface, "iter_search_pages", pages)
    output = tmp_path / "partitioned"
    result = CliRunner().invoke(
        app, [*_base_args(output), "--write-mode", "partitioned", "--batch-size", "1"]
    )
    assert result.exit_code == 0, result.output
    checkpoint = json.loads((output / "uniprot_incremental_checkpoint.json").read_text())
    assert requested_pages == [500]
    assert checkpoint["batch_size"] == 1
    assert checkpoint["processing_buffer_size"] == 2000
    assert [part["rows"] for part in checkpoint["files"]] == [1, 1]
    metadata = json.loads((output / "metadata.json").read_text())
    assert metadata["workflow_metadata"]["uniprot"]["partitioned"]["status"] == "completed"


@pytest.mark.parametrize(
    "extra",
    [
        ["--write-mode", "unknown"],
        ["--write-mode", "single", "--batch-size", "1"],
        ["--write-mode", "partitioned", "--chunk-size", "1"],
        ["--incremental", "--write-mode", "single"],
        ["--incremental", "--batch-size", "1"],
        ["--write-mode", "partitioned", "--batch-size", "0"],
    ],
)
def test_write_mode_validation_rejects_ambiguous_arguments(tmp_path, extra):
    result = CliRunner().invoke(app, [*_base_args(tmp_path / "invalid"), *extra])
    assert result.exit_code == 2


def test_partitioned_cli_refuses_any_existing_output(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    previous = output / "run_summary.yml"
    previous.write_text("previous")
    result = CliRunner().invoke(app, [*_base_args(output), "--write-mode", "partitioned"])
    assert result.exit_code == 2
    assert previous.read_text() == "previous"
    assert not (output / "uniprot_incremental_checkpoint.json").exists()
