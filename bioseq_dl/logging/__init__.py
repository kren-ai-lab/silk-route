"""Logging configuration for BioSeqDownloader."""
# bioseq_dl/logging/__init__.py

from .logger import (
    LOG_LEVELS,
    configure_logging,
    enable_logging,
    get_logger,
    set_level,
    setup_logging,
)

__all__ = [
    "LOG_LEVELS",
    "configure_logging",
    "enable_logging",
    "get_logger",
    "set_level",
    "setup_logging",
]
