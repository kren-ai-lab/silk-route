"""Shared helpers for ChEMBL activity queries."""

from __future__ import annotations


def normalize_standard_units(value: str) -> str:
    """Normalize a user-provided ChEMBL standard-units value without conversion."""
    normalized = str(value).strip()
    normalized = normalized.replace("Âµ", "u").replace("Î¼", "u")
    normalized = normalized.replace("µ", "u").replace("μ", "u")
    if not normalized:
        msg = "standard_units must be a non-empty value."
        raise ValueError(msg)
    return normalized
