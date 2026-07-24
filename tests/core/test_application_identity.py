"""Application identity tests for package paths and platform directories."""

from __future__ import annotations

import importlib


def test_platform_app_name_and_env_overrides(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SILKROUTE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SILKROUTE_CONFIG_DIR", str(tmp_path / "config"))

    from silkroute.constants import databases

    reloaded = importlib.reload(databases)
    try:
        assert reloaded.APP_NAME == "silkroute"
        assert tmp_path / "cache" == reloaded.BASE_CACHE_DIR
        assert tmp_path / "config" == reloaded.BASE_CONFIG_DIR
    finally:
        monkeypatch.delenv("SILKROUTE_CACHE_DIR", raising=False)
        monkeypatch.delenv("SILKROUTE_CONFIG_DIR", raising=False)
        importlib.reload(databases)
