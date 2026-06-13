"""Unit tests for the shared transform/engine logic in BaseAPIInterface.

These exercise the format conversion, field extraction, query decomposition,
result splitting, cache-key building, and parameter preparation that every
interface relies on — independent of any single API.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from bioseq_dl.core.dbconfig import DBConfig
from bioseq_dl.core.interfaces.base import BaseAPIInterface


class FakeInterface(BaseAPIInterface):
    API_NAME = "Fake"
    METHODS = {
        "get": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {"id": (str, None, True), "db": (str, None, False)},
            "group_queries": ["id"],
            "separator": ",",
        },
        "single": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {"id": (str, None, True)},
            "group_queries": [None],
            "separator": None,
        },
    }

    def fetch(self, query, *, method="get", **kwargs):
        return query

    def parse(self, data, fields_to_extract, **kwargs):
        return self._extract_fields(data, fields_to_extract, **kwargs)

    def query_usage(self) -> str:
        return "usage"


@pytest.fixture
def iface(tmp_path):
    return FakeInterface(cache_dir=str(tmp_path), use_config=False)


# --- _maybe_parse: format conversion --------------------------------------


def test_maybe_parse_to_dataframe(iface):
    out = iface._maybe_parse([{"a": 1}, {"a": 2}], parse=False, format="dataframe")
    assert isinstance(out, pd.DataFrame)
    assert list(out["a"]) == [1, 2]


def test_maybe_parse_dict_to_dataframe_single_row(iface):
    out = iface._maybe_parse({"a": 1}, parse=False, format="dataframe")
    assert isinstance(out, pd.DataFrame)
    assert out.shape == (1, 1)


def test_maybe_parse_to_xml_bytes(iface):
    out = iface._maybe_parse({"a": "x"}, parse=False, format="xml")
    assert isinstance(out, bytes)
    assert b"<a>x</a>" in out


def test_maybe_parse_with_parse_extracts_fields(iface):
    out = iface._maybe_parse({"a": 1, "b": 2}, parse=True, format="json", fields_to_extract=["a"])
    assert out == {"a": 1}


# --- _extract_fields -------------------------------------------------------


def test_extract_fields_list_of_keys_on_dict(iface):
    assert iface._extract_fields({"a": 1, "b": 2}, ["a"]) == {"a": 1}


def test_extract_fields_mapping_renames(iface):
    out = iface._extract_fields({"x": {"y": 5}}, {"val": "x.y"})
    assert out == {"val": 5}


def test_extract_fields_list_data(iface):
    out = iface._extract_fields([{"a": 1}, {"a": 2}], ["a"])
    assert out == [{"a": 1}, {"a": 2}]


def test_extract_fields_none_returns_whole(iface):
    assert iface._extract_fields({"a": 1}, None) == {"a": 1}


# --- decompose_query / split_results_by_subquery / merge_dicts -------------


def test_decompose_query_expands_list(iface):
    subs = iface.decompose_query({"id": ["a", "b"]}, "get", None)
    identifiers = [identifier for identifier, _ in subs]
    assert identifiers == ["a", "b"]
    assert subs[0][1]["id"] == "a"


def test_decompose_query_no_group_query_returns_empty(iface):
    # 'single' has no group_query key, so there is nothing to decompose.
    assert iface.decompose_query({"id": "a"}, "single", None) == []


def test_split_results_by_subquery_matches_tokens(iface):
    full = [{"id": "a", "v": 1}, {"id": "b", "v": 2}]
    subs = [("a", {"id": "a"}), ("b", {"id": "b"})]
    mapping = iface.split_results_by_subquery(full, subs)
    assert mapping["a"] == [{"id": "a", "v": 1}]
    assert mapping["b"] == [{"id": "b", "v": 2}]


def test_merge_dicts_collects_distinct_values(iface):
    assert iface.merge_dicts([{"id": "a"}, {"id": "b"}]) == {"id": ["a", "b"]}


def test_merge_dicts_keeps_single(iface):
    assert iface.merge_dicts([{"id": "a"}, {"id": "a"}]) == {"id": "a"}


# --- cache key building ----------------------------------------------------


def test_filter_dict_keys_drops_ignored_and_sorts(iface):
    out = iface._filter_dict_keys({"b": 2, "a": 1, "parse": True})
    assert list(out.keys()) == ["a", "b"]
    assert "parse" not in out


def test_filter_dict_keys_sorts_lists(iface):
    out = iface._filter_dict_keys({"ids": ["c", "a", "b"]})
    assert out["ids"] == ["a", "b", "c"]


def test_make_cache_key_dict_is_deterministic(iface):
    k1 = iface._make_cache_key({"b": 2, "a": 1})
    k2 = iface._make_cache_key({"a": 1, "b": 2})
    assert k1 == k2


# --- _prepare_params / _make_identifier ------------------------------------


def test_prepare_params_joins_group_query_list(iface):
    spec = FakeInterface.METHODS["get"]
    params = iface._prepare_params({"id": ["a", "b"], "db": "x"}, spec)
    assert params == {"id": "a,b", "db": "x"}


def test_make_identifier_uses_primary_keys(iface):
    spec = FakeInterface.METHODS["get"]
    assert iface._make_identifier({"id": "a", "db": "x"}, spec) == "a"


# --- _resolve_dirs ---------------------------------------------------------


class FakeWithDB(FakeInterface):
    DB_CONFIG = DBConfig(API_URL="http://example/", CACHE_DIR="/fake/cache", CONFIG_DIR="/fake/config")


def test_resolve_dirs_default_fallback_is_absolute():
    # No DB_CONFIG and no explicit dir -> "./cache", normalized to absolute.
    cache, config = FakeInterface._resolve_dirs(None, None)
    assert cache == str(Path.cwd() / "cache")
    assert Path(cache).is_absolute()
    assert config is None


def test_resolve_dirs_uses_db_config():
    cache, config = FakeWithDB._resolve_dirs(None, None)
    assert cache == "/fake/cache"
    assert config == "/fake/config"


def test_resolve_dirs_explicit_cache_dir_made_absolute():
    # Explicit (relative) cache_dir overrides DB_CONFIG and is made absolute.
    cache, config = FakeWithDB._resolve_dirs("relative/cache", None)
    assert cache == str(Path.cwd() / "relative" / "cache")
    assert Path(cache).is_absolute()
    assert config == "/fake/config"


def test_resolve_dirs_explicit_config_dir_preserved():
    _, config = FakeWithDB._resolve_dirs(None, "my/config")
    assert config == "my/config"


# --- packaged field maps (Phase 5) ----------------------------------------


def test_packaged_fields_loaded_without_user_config_dir(tmp_path):
    # use_config=True + a non-existent config dir must NOT raise: field maps come
    # from packaged resources, not the user directory.
    from bioseq_dl import ChEBIInterface

    iface = ChEBIInterface(cache_dir=str(tmp_path), config_dir=str(tmp_path / "missing"), use_config=True)
    fields = iface.get_config("fields")
    assert fields  # non-empty, loaded from bioseq_dl/config/chebi/fields.yml
    assert "compounds" in fields


def test_load_packaged_fields_empty_without_db_config(iface):
    # FakeInterface has no DB_CONFIG -> no packaged fields, returns {}.
    assert iface._load_packaged_fields() == {}
