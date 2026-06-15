"""Unit tests for the cache registry and clear_cache safety logic."""

from __future__ import annotations

from pathlib import Path

from bioseq_dl.core.cache import (
    _is_empty_file,
    clear_cache,
    list_caches,
    register_cache,
)


def test_register_cache_normalizes_to_path(tmp_path):
    register_cache("unit_norm", str(tmp_path))
    assert list_caches()["unit_norm"] == Path(tmp_path)


def test_clear_cache_dry_run_reports_without_deleting(tmp_path):
    f = tmp_path / "cached.json"
    f.write_text("{}")
    register_cache("unit_dry", str(f))

    report = clear_cache(["unit_dry"], dry_run=True, allowed_bases=[tmp_path])

    assert report["unit_dry"] == [str(f)]
    assert f.exists()  # dry run must not delete


def test_clear_cache_deletes_within_allowed_base(tmp_path):
    f = tmp_path / "cached.json"
    f.write_text("data")
    register_cache("unit_del", str(f))

    clear_cache(["unit_del"], allowed_bases=[tmp_path])

    assert not f.exists()


def test_clear_cache_refuses_path_outside_allowed_bases(tmp_path):
    # Target file lives outside the allowed base -> must be skipped.
    outside = tmp_path / "outside.json"
    outside.write_text("keep me")
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    register_cache("unit_outside", str(outside))

    report = clear_cache(["unit_outside"], allowed_bases=[allowed])

    assert report["unit_outside"] == []
    assert outside.exists()


def test_clear_cache_empty_filter_only_removes_empty_files(tmp_path):
    empty = tmp_path / "empty.json"
    empty.write_text("{}")  # counts as empty
    full = tmp_path / "full.json"
    full.write_text('{"a": 1}')
    register_cache("unit_empty", str(tmp_path))

    clear_cache(["unit_empty"], empty=True, allowed_bases=[tmp_path])

    assert not empty.exists()
    assert full.exists()


def test_clear_cache_unknown_name_is_skipped(tmp_path):
    report = clear_cache(["does_not_exist"], allowed_bases=[tmp_path])
    assert report == {}


def test_is_empty_file(tmp_path):
    assert _is_empty_file(_write(tmp_path / "a", "")) is True
    assert _is_empty_file(_write(tmp_path / "b", "  []  ")) is True
    assert _is_empty_file(_write(tmp_path / "c", '{"x": 1}')) is False


def _write(path, text):
    path.write_text(text)
    return path
