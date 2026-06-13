from dataclasses import dataclass


@dataclass(frozen=True)
class DBConfig:
    API_URL: str = ""
    STRUCTURE_URL: str | None = None
    CACHE_DIR: str | None = None
    CONFIG_DIR: str | None = None
