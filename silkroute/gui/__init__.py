"""GUI helpers for SilkRoute workflow YAML generation."""

from __future__ import annotations

from importlib import import_module

__all__ = [
    "build_workflow_descriptor",
    "build_workflow_filename",
    "parse_csv_list",
    "remove_empty_values",
    "render_workflow_yaml",
    "resolve_query_value_from_form",
    "validate_generated_descriptor",
    "workflow_yaml_form_defaults",
]


def __getattr__(name: str) -> object:
    """Lazily expose YAML builder helpers without importing them at package import time."""
    if name in __all__:
        yaml_builder = import_module("silkroute.gui.yaml_builder")
        return getattr(yaml_builder, name)
    raise AttributeError(name)
