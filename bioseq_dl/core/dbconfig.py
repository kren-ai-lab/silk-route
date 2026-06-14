"""Database configuration data class."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DBConfig:
    """Database configuration data class."""

    API_URL: str = ""
    STRUCTURE_URL: str | None = None
    CACHE_DIR: str | None = None
    CONFIG_DIR: str | None = None
