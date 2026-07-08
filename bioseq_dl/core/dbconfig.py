"""Database configuration data class."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DBConfig:
    """Database configuration data class.

    Attributes:
        API_URL (str): Base URL of the database API.
        STRUCTURE_URL (str | None): URL for structure/file downloads, when applicable.
        CACHE_DIR (str | None): Directory where cached responses are stored.
        CONFIG_DIR (str | None): Directory holding the database's config files.

    """

    API_URL: str = ""
    STRUCTURE_URL: str | None = None
    CACHE_DIR: str | None = None
    CONFIG_DIR: str | None = None
