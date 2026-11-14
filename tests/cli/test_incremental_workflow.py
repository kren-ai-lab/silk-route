"""CLI contract for incremental UniProt workflows."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from silkroute.cli.main import app
from silkroute.core.interfaces.uniprot import UniprotInterface


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
