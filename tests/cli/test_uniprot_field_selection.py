"""CLI regression tests for explicit UniProt output-field selection."""

from __future__ import annotations

import polars as pl

from silkroute.cli.interfaces import uniprot_search_ids, uniprot_search_query


class RecordingUniprot:
    def __init__(self):
        self.submit_kwargs = None
        self.submit_method = None
        self.download_args = None

    def submit_search(self, **kwargs):
        self.submit_method = "search"
        self.submit_kwargs = kwargs
        return {"results": []}, {}

    def submit_stream(self, **kwargs):
        self.submit_method = "stream"
        self.submit_kwargs = kwargs
        return {"results": []}, {}

    def download_batch(self, *args):
        self.download_args = args
        return [{"results": []}], {}


def test_by_query_forwards_explicit_fields_to_fetch_and_export(monkeypatch, tmp_path):
    interface = RecordingUniprot()
    saved = {}
    monkeypatch.setattr(uniprot_search_query, "UniprotInterface", lambda: interface)
    monkeypatch.setattr(
        uniprot_search_query,
        "parse_and_save_uniprot",
        lambda *args, **kwargs: saved.update(kwargs),
    )

    uniprot_search_query.run(
        output=str(tmp_path),
        query="reviewed:true",
        fields="accession,protein_name,sequence",
        crossref_fields="",
        sort="accession asc",
        include_isoform=False,
        concat_results=False,
        export_format="csv",
    )

    assert interface.submit_method == "search"
    assert interface.submit_kwargs["fields"] == "accession,protein_name,sequence"
    assert interface.submit_kwargs["sort"] == "accession asc"
    assert interface.submit_kwargs["include_isoform"] is False
    assert saved["fields"] == "accession,protein_name,sequence"


def test_by_ids_forwards_explicit_fields_to_export(monkeypatch, tmp_path):
    interface = RecordingUniprot()
    saved = {}
    input_path = tmp_path / "ids.csv"
    pl.DataFrame({"accession": ["P12345"]}).write_csv(input_path)
    monkeypatch.setattr(uniprot_search_ids, "UniprotInterface", lambda: interface)
    monkeypatch.setattr(
        uniprot_search_ids,
        "parse_and_save_uniprot",
        lambda *args, **kwargs: saved.update(kwargs),
    )

    uniprot_search_ids.run(
        input_file=str(input_path),
        column="accession",
        output=str(tmp_path),
        from_db="UniProtKB_AC-ID",
        to_db="UniProtKB",
        fields="sequence,accession",
        crossref_fields="",
        batch_size=5000,
        auto_db=False,
        min_identity=None,
        export_format="csv",
    )

    assert interface.download_args is not None
    assert saved["fields"] == "sequence,accession"
