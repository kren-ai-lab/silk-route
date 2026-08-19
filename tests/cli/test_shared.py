"""Tests for the shared CLI save/print helper.

Regression coverage for the bug where CLI commands called ``result.to_csv(...)``
on the ``(data, metadata)`` tuple returned by ``fetch_single`` / ``fetch_batch``.
"""

from __future__ import annotations

import json
import logging

import polars as pl
import pytest

from silkroute.cli._shared import fetch_auto, parse_and_save_uniprot, save_or_print, unwrap
from silkroute.core.interfaces.uniprot import UniprotInterface


class _FakeInterface:
    def __init__(self):
        self.single = None
        self.batch = None

    def fetch_single(self, query, method, **kwargs):
        self.single = (query, method, kwargs)
        return "single"

    def fetch_batch(self, queries, method, **kwargs):
        self.batch = (queries, method, kwargs)
        return "batch"


def test_fetch_auto_single_query_calls_fetch_single():
    fake = _FakeInterface()
    out = fetch_auto(fake, ["X"], method="m", parse=True)
    assert out == "single"
    assert fake.single == ("X", "m", {"parse": True})
    assert fake.batch is None


def test_fetch_auto_multiple_queries_calls_fetch_batch():
    fake = _FakeInterface()
    out = fetch_auto(fake, ["X", "Y"], method="m", parse=True)
    assert out == "batch"
    assert fake.batch == (["X", "Y"], "m", {"parse": True})
    assert fake.single is None


def test_unwrap_data_metadata_tuple():
    df = pl.DataFrame({"a": [1]})
    assert unwrap((df, {"meta": 1})) is df


def test_unwrap_passes_through_non_tuple():
    df = pl.DataFrame({"a": [1]})
    assert unwrap(df) is df


def test_unwrap_keeps_plain_two_tuple_without_metadata():
    # Second element is not a dict -> not a (data, metadata) result.
    value = (1, 2)
    assert unwrap(value) == (1, 2)


def test_save_dataframe_tuple_to_csv(tmp_path):
    df = pl.DataFrame({"id": ["X"], "value": [42]})
    out = tmp_path / "out.csv"

    save_or_print((df, {"api_name": "test"}), str(out))

    assert out.exists()
    loaded = pl.read_csv(out)
    assert loaded.to_dicts() == [{"id": "X", "value": 42}]


def test_save_list_tuple_to_json(tmp_path):
    data = [{"id": "X"}, {"id": "Y"}]
    out = tmp_path / "out.json"

    save_or_print((data, {"api_name": "test"}), str(out))

    assert json.loads(out.read_text()) == data


def test_save_writes_metadata_sidecar(tmp_path):
    df = pl.DataFrame({"id": ["X"]})
    out = tmp_path / "out.csv"

    save_or_print((df, {"api_name": "test", "tool": {"name": "silkroute"}}), str(out))

    sidecar = tmp_path / "out.metadata.json"
    assert sidecar.exists()
    assert json.loads(sidecar.read_text()) == {"api_name": "test", "tool": {"name": "silkroute"}}


def test_sidecar_tracks_actual_saved_file(tmp_path):
    # When the format adds/normalizes the extension, the sidecar sits next to the
    # real output file (noext.json), not the requested path.
    df = pl.DataFrame({"id": ["X"]})
    out = tmp_path / "noext"

    save_or_print((df, {"api_name": "test"}), str(out), output_format="json")

    assert (tmp_path / "noext.metadata.json").exists()


def test_no_sidecar_when_metadata_empty(tmp_path):
    df = pl.DataFrame({"id": ["X"]})
    out = tmp_path / "out.csv"

    save_or_print((df, {}), str(out))

    assert not (tmp_path / "out.metadata.json").exists()


def test_no_sidecar_when_printing_preview(tmp_path, capsys):
    df = pl.DataFrame({"id": ["X"]})

    save_or_print((df, {"api_name": "test"}), None)

    assert list(tmp_path.iterdir()) == []
    assert capsys.readouterr().out


def test_no_sidecar_when_write_metadata_false(tmp_path):
    df = pl.DataFrame({"id": ["X"]})
    out = tmp_path / "out.csv"

    save_or_print((df, {"api_name": "test"}), str(out), write_metadata=False)

    assert out.exists()
    assert not (tmp_path / "out.metadata.json").exists()


def test_metadata_enabled_defaults_true_without_context():
    from silkroute.cli._shared import _metadata_enabled

    # No active click context (direct call) -> sidecars enabled by default.
    assert _metadata_enabled() is True


def test_save_dataframe_infers_format_from_extension(tmp_path):
    df = pl.DataFrame({"id": ["X"], "value": [42]})
    out = tmp_path / "out.json"

    save_or_print((df, {}), str(out))

    assert json.loads(out.read_text()) == [{"id": "X", "value": 42}]


def test_save_dataframe_explicit_format_adds_suffix(tmp_path):
    df = pl.DataFrame({"id": ["X"]})
    out = tmp_path / "noext"

    save_or_print((df, {}), str(out), output_format="json")

    assert (tmp_path / "noext.json").exists()


def test_save_dataframe_defaults_to_csv_without_extension(tmp_path):
    df = pl.DataFrame({"id": ["X"]})
    out = tmp_path / "plain"

    save_or_print((df, {}), str(out))

    assert (tmp_path / "plain.csv").exists()


def test_save_dataframe_unsupported_format_exits_cleanly(tmp_path):
    import typer

    df = pl.DataFrame({"id": ["X"]})
    with pytest.raises(typer.Exit) as exc:
        save_or_print((df, {}), str(tmp_path / "out.txt"))
    assert exc.value.exit_code == 1


def test_print_preview_does_not_raise(capsys):
    df = pl.DataFrame({"a": list(range(10))})
    # No output path -> should print a preview without raising.
    save_or_print((df, {}), None)
    assert capsys.readouterr().out  # something was printed


def test_parse_and_save_uniprot_exports_only_explicit_fields(tmp_path):
    response = {
        "results": [
            {
                "primaryAccession": "P12345",
                "proteinDescription": {
                    "recommendedName": {
                        "fullName": {"value": "Example enzyme"},
                        "ecNumbers": [{"value": "1.2.3.4"}],
                    }
                },
                "sequence": {"value": "MPEPTIDE", "length": 8},
            }
        ]
    }

    parse_and_save_uniprot(
        UniprotInterface(),
        response,
        {},
        fields="accession,protein_name,sequence",
        crossref_fields="",
        output=str(tmp_path),
        export_format="csv",
        logger=logging.getLogger(__name__),
    )

    exported = pl.read_csv(tmp_path / "uniprot_results.csv")
    assert exported.columns == ["accession", "protein_name", "sequence"]
