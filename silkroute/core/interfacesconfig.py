"""Interface configuration loading utilities."""

import json
from importlib import resources
from pathlib import Path
from typing import Any

import yaml


def read_config_file(path: str | Path) -> Any:
    """Load a single JSON/YAML config file into a Python object.

    Returns ``None`` for unsupported extensions. Shared by ``load_packaged_config``
    and ``BaseAPIInterface._load_all_configs`` so the parse logic lives in one place.
    """
    ext = Path(path).suffix.lower()
    if ext not in (".json", ".yaml", ".yml"):
        return None
    with Path(path).open(encoding="utf-8") as f:
        if ext == ".json":
            return json.load(f)
        return yaml.safe_load(f)


def load_packaged_config(subdir: str, name: str) -> Any:
    """Load a config file bundled in the package (``silkroute/config/<subdir>/<name>``).

    These are library defaults (e.g. field-extraction maps) shipped with the
    package — the authoritative source, always in sync with the parse code.
    Returns ``None`` when the resource does not exist.
    """
    try:
        resource = resources.files("silkroute") / "config" / subdir / name
        if not resource.is_file():
            return None
        with resources.as_file(resource) as path:
            return read_config_file(str(path))
    except (FileNotFoundError, ModuleNotFoundError):
        return None
