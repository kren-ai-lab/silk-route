"""Credential resolution utilities for API authentication."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import load_dotenv

from bioseq_dl.constants.databases import BASE_CONFIG_DIR

if TYPE_CHECKING:
    from collections.abc import Sequence

ENV_FILE_NAME = ".env"
PLACEHOLDER_VALUES = {
    "your_api_key_here",
    "your_api_key",
    "your_email@example.com",
    "your_email",
    "your_password",
    "your_password_here",
}


def load_environment_files(config_dir: str | None = None) -> None:
    """Load environment variables from supported .env locations.

    This function never overrides already-set system environment variables.
    """
    env_paths = []

    env_file = os.getenv("BIOSEQ_DL_ENV_FILE")
    if env_file:
        env_paths.append(Path(env_file).expanduser())

    env_paths.append(Path.cwd() / ENV_FILE_NAME)

    config_path = Path(config_dir).expanduser() if config_dir else Path(BASE_CONFIG_DIR)

    env_paths.append(config_path / ENV_FILE_NAME)

    seen = set()
    for path in env_paths:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        resolved_key = str(resolved)
        if resolved_key in seen:
            continue
        seen.add(resolved_key)
        if resolved.is_file():
            load_dotenv(dotenv_path=resolved, override=False)


def get_env_value(names: Sequence[str]) -> str | None:
    """Return the first non-empty environment value from a list of variable names."""
    for name in names:
        value = _normalize_value(os.getenv(name))
        if value is not None:
            return value
    return None


def is_valid_secret(value: str | None) -> bool:
    """Check whether a secret value is present and not a placeholder."""
    normalized = _normalize_value(value)
    if normalized is None:
        return False
    return normalized.lower() not in PLACEHOLDER_VALUES


def resolve_secret(
    explicit_value: str | None,
    env_names: Sequence[str],
) -> str | None:
    """Resolve a secret value with priority: explicit > environment."""
    explicit_normalized = _normalize_value(explicit_value)
    if is_valid_secret(explicit_normalized):
        return explicit_normalized

    env_value = get_env_value(env_names)
    if is_valid_secret(env_value):
        return env_value

    return None


def _normalize_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
