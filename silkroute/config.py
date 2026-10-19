"""Public config validation: check a workflow descriptor without running it."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from silkroute.core.workflow.schema import collect_workflow_v1_descriptor_errors

if TYPE_CHECKING:
    import os


@dataclass(frozen=True)
class ConfigIssue:
    """One config problem: a dotted ``path`` (``""`` for the root) and a ``message``."""

    path: str
    message: str


def load_workflow_recipe(config_path: str | Path) -> dict:
    """Load a workflow descriptor from a YAML file.

    Args:
        config_path (str | Path): Path to the YAML descriptor file.

    Returns:
        dict: The parsed descriptor, or an empty dict if the file is empty.

    Raises:
        ValueError: If the file does not exist or cannot be read or parsed.
        TypeError: If the YAML root is not a mapping.

    """
    path = Path(config_path)
    if not path.exists():
        msg = f"Workflow YAML file does not exist: {path}"
        raise ValueError(msg)

    try:
        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        msg = f"Invalid workflow YAML in {path}: {exc}"
        raise ValueError(msg) from exc
    except OSError as exc:
        msg = f"Could not read workflow YAML {path}: {exc}"
        raise ValueError(msg) from exc

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        msg = "Workflow YAML root must be a mapping."
        raise TypeError(msg)
    return loaded


def validate_config(config: Mapping | str | os.PathLike) -> list[ConfigIssue]:
    """Validate a workflow descriptor, given as a mapping or a path to a YAML/JSON file.

    Never raises for config problems and never touches the network.

    Args:
        config (Mapping | str | os.PathLike): The descriptor, or the path to its file.

    Returns:
        list[ConfigIssue]: Every problem found; empty when the descriptor is valid. A missing or
        unparsable file is one issue with path ``""``.

    """
    if not isinstance(config, Mapping):
        try:
            config = load_workflow_recipe(Path(config))
        except (ValueError, TypeError) as exc:
            return [ConfigIssue("", str(exc))]
    return [ConfigIssue(path, message) for path, message in collect_workflow_v1_descriptor_errors(config)]
