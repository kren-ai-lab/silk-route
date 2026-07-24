"""Unit tests for credential resolution helpers."""

from __future__ import annotations

from silkroute.core.credentials import (
    get_env_value,
    is_valid_secret,
    load_environment_files,
    resolve_secret,
)


def test_is_valid_secret():
    assert is_valid_secret("realkey") is True
    assert is_valid_secret(None) is False
    assert is_valid_secret("   ") is False
    # Known placeholder values are treated as missing.
    assert is_valid_secret("your_api_key") is False
    assert is_valid_secret("your_email@example.com") is False


def test_get_env_value_first_non_empty(monkeypatch):
    monkeypatch.delenv("A_KEY", raising=False)
    monkeypatch.setenv("B_KEY", "  value ")
    assert get_env_value(["A_KEY", "B_KEY"]) == "value"


def test_resolve_secret_prefers_explicit(monkeypatch):
    monkeypatch.setenv("MY_KEY", "from-env")
    assert resolve_secret("explicit", ["MY_KEY"]) == "explicit"


def test_resolve_secret_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("MY_KEY", "from-env")
    assert resolve_secret(None, ["MY_KEY"]) == "from-env"


def test_resolve_secret_ignores_placeholder_explicit(monkeypatch):
    monkeypatch.setenv("MY_KEY", "from-env")
    # Placeholder explicit value is rejected, env wins.
    assert resolve_secret("your_api_key", ["MY_KEY"]) == "from-env"


def test_resolve_secret_returns_none_when_nothing(monkeypatch):
    monkeypatch.delenv("MY_KEY", raising=False)
    assert resolve_secret(None, ["MY_KEY"]) is None


def test_load_environment_files_reads_env(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("SILKROUTE_TEST_SECRET=hello\n")
    monkeypatch.setenv("SILKROUTE_ENV_FILE", str(env))
    monkeypatch.delenv("SILKROUTE_TEST_SECRET", raising=False)

    load_environment_files()

    assert get_env_value(["SILKROUTE_TEST_SECRET"]) == "hello"


def test_load_environment_files_does_not_override(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("SILKROUTE_TEST_SECRET=fromfile\n")
    monkeypatch.setenv("SILKROUTE_ENV_FILE", str(env))
    monkeypatch.setenv("SILKROUTE_TEST_SECRET", "preset")

    load_environment_files()

    # Existing env var is not overridden by the .env file.
    assert get_env_value(["SILKROUTE_TEST_SECRET"]) == "preset"
