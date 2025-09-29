from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class DBConfig:
    API_URL: str = ""
    STRUCTURE_URL: Optional[str] = None
    CACHE_DIR: Optional[str] = None
    CONFIG_DIR: Optional[str] = None