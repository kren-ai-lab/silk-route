"""End-to-end wiring of the ``fetch --no-metadata`` flag.

Confirms the fetch-app callback flows through the shared click context into
``save_or_print``, gating the provenance sidecar for every fetch subcommand.
"""

from __future__ import annotations

import pandas as pd
import pytest
from typer.testing import CliRunner

from bioseq_dl.cli.main import app

runner = CliRunner()


class _FakeKEGG:
    def __init__(self, *args, **kwargs):
        pass

    def fetch_single(self, *args, **kwargs):
        df = pd.DataFrame({"id": ["hsa:1"], "value": [42]})
        return df, {"api_name": "kegg", "tool": {"name": "bioseq_dl", "version": "0.1.0"}}


@pytest.fixture
def _patch_kegg(monkeypatch):
    monkeypatch.setattr("bioseq_dl.cli.interfaces.kegg.KEGGInterface", _FakeKEGG)


@pytest.mark.usefixtures("_patch_kegg")
def test_fetch_writes_sidecar_by_default(tmp_path):
    out = tmp_path / "out.csv"
    result = runner.invoke(app, ["fetch", "kegg", "get", "hsa:1", "-o", str(out)])

    assert result.exit_code == 0, result.output
    assert out.exists()
    assert (tmp_path / "out.metadata.json").exists()


@pytest.mark.usefixtures("_patch_kegg")
def test_fetch_no_metadata_skips_sidecar(tmp_path):
    out = tmp_path / "out.csv"
    result = runner.invoke(app, ["fetch", "--no-metadata", "kegg", "get", "hsa:1", "-o", str(out)])

    assert result.exit_code == 0, result.output
    assert out.exists()
    assert not (tmp_path / "out.metadata.json").exists()
