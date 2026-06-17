"""Tests for the shared CLI save/print helper.

Regression coverage for the bug where CLI commands called ``result.to_csv(...)``
on the ``(data, metadata)`` tuple returned by ``fetch_single`` / ``fetch_batch``.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from bioseq_dl.cli._shared import fetch_auto, save_or_print, unwrap


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
    df = pd.DataFrame({"a": [1]})
    assert unwrap((df, {"meta": 1})) is df


def test_unwrap_passes_through_non_tuple():
    df = pd.DataFrame({"a": [1]})
    assert unwrap(df) is df


def test_unwrap_keeps_plain_two_tuple_without_metadata():
    # Second element is not a dict -> not a (data, metadata) result.
    value = (1, 2)
    assert unwrap(value) == (1, 2)


def test_save_dataframe_tuple_to_csv(tmp_path):
    df = pd.DataFrame({"id": ["X"], "value": [42]})
    out = tmp_path / "out.csv"

    save_or_print((df, {"api_name": "test"}), str(out))

    assert out.exists()
    loaded = pd.read_csv(out)
    assert loaded.to_dict(orient="records") == [{"id": "X", "value": 42}]


def test_save_list_tuple_to_json(tmp_path):
    data = [{"id": "X"}, {"id": "Y"}]
    out = tmp_path / "out.json"

    save_or_print((data, {"api_name": "test"}), str(out))

    assert json.loads(out.read_text()) == data


def test_save_dataframe_infers_format_from_extension(tmp_path):
    df = pd.DataFrame({"id": ["X"], "value": [42]})
    out = tmp_path / "out.json"

    save_or_print((df, {}), str(out))

    assert json.loads(out.read_text()) == [{"id": "X", "value": 42}]


def test_save_dataframe_explicit_format_adds_suffix(tmp_path):
    df = pd.DataFrame({"id": ["X"]})
    out = tmp_path / "noext"

    save_or_print((df, {}), str(out), output_format="json")

    assert (tmp_path / "noext.json").exists()


def test_save_dataframe_defaults_to_csv_without_extension(tmp_path):
    df = pd.DataFrame({"id": ["X"]})
    out = tmp_path / "plain"

    save_or_print((df, {}), str(out))

    assert (tmp_path / "plain.csv").exists()


def test_save_dataframe_unsupported_format_exits_cleanly(tmp_path):
    import typer

    df = pd.DataFrame({"id": ["X"]})
    with pytest.raises(typer.Exit) as exc:
        save_or_print((df, {}), str(tmp_path / "out.txt"))
    assert exc.value.exit_code == 1


def test_print_preview_does_not_raise(capsys):
    df = pd.DataFrame({"a": range(10)})
    # No output path -> should print a preview without raising.
    save_or_print((df, {}), None)
    assert capsys.readouterr().out  # something was printed
