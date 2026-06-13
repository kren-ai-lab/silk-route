"""Tests for the shared CLI save/print helper.

Regression coverage for the bug where CLI commands called ``result.to_csv(...)``
on the ``(data, metadata)`` tuple returned by ``fetch_single`` / ``fetch_batch``.
"""

from __future__ import annotations

import json

import pandas as pd

from bioseq_dl.cli._shared import save_or_print, unwrap


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


def test_print_preview_does_not_raise(capsys):
    df = pd.DataFrame({"a": range(10)})
    # No output path -> should print a preview without raising.
    save_or_print((df, {}), None)
    assert capsys.readouterr().out  # something was printed
