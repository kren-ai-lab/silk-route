"""Lightweight package identity and version helpers."""

from __future__ import annotations

from importlib import metadata

TOOL_NAME = "BioSeqDownloader"
DISTRIBUTION_NAME = "bioseqdownloader"
IMPORT_PACKAGE_NAME = "bioseq_dl"
SOURCE_VERSION = "0.1.0"
UNKNOWN_VERSION = "0+unknown"


def get_runtime_version() -> str:
    """Return the installed distribution version, or an unknown local version."""
    try:
        return metadata.version(DISTRIBUTION_NAME)
    except metadata.PackageNotFoundError:
        return UNKNOWN_VERSION


def build_tool_identity() -> dict[str, str]:
    """Return stable tool identity metadata."""
    return {
        "tool_name": TOOL_NAME,
        "distribution_name": DISTRIBUTION_NAME,
        "import_package_name": IMPORT_PACKAGE_NAME,
        "version": get_runtime_version(),
    }
