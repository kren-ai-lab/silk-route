"""Shared helpers for the source-specific query builders."""

from __future__ import annotations

from bioseq_dl.core.workflow.query_interpreter import strip_surrounding_quotes


def quote_builder_value(value: str) -> str:
    """Quote a builder query value, escaping embedded double quotes."""
    cleaned = strip_surrounding_quotes(str(value))
    escaped = cleaned.replace('"', '\\"')
    return f'"{escaped}"'


def format_builder_row_error(row_index: int, message: str) -> str:
    """Return a user-facing validation error with one-based row context."""
    return f"Row {row_index + 1}: {message}"
