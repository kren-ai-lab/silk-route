"""Template for adding a new database interface to BioSeqDownloader.

Copy this file into ``bioseq_dl/core/interfaces/<your_db>.py`` and:

1. Add a ``DBConfig`` for your database in ``bioseq_dl/constants/databases.py``.
2. Replace ``YOUR_DATABASE`` below with that config.
3. Fill in ``METHODS``, ``fetch`` and ``parse``.
4. Register the public class in ``bioseq_dl/__init__.py`` (``_LAZY_EXPORTS`` + ``__all__``).
5. Add tests under ``tests/core/interfaces/``.

This file lives in ``examples/`` on purpose; it is a reference, not part of the package.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import requests

from bioseq_dl.core.interfaces.base import BaseAPIInterface
from bioseq_dl.logging import get_logger

# Replace with the real DBConfig once added to constants/databases.py, e.g.:
# from bioseq_dl.constants.databases import YOUR_DATABASE  # noqa: ERA001
YOUR_DATABASE = None  # placeholder

log = get_logger("bioseq_dl.interfaces.your_database")


class YourDatabaseInterface(BaseAPIInterface):
    """Minimal interface skeleton. Rename to match your database."""

    API_NAME = "YourDatabase"
    METHODS: ClassVar[dict[str, Any]] = {}

    def __init__(
        self,
        cache_dir: str | None = None,
        config_dir: str | None = None,
        output_dir: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the template interface."""
        if cache_dir:
            cache_dir = str(Path(cache_dir).resolve())
        else:
            cache_dir = YOUR_DATABASE.CACHE_DIR if YOUR_DATABASE and YOUR_DATABASE.CACHE_DIR else ""

        if config_dir is None:
            config_dir = YOUR_DATABASE.CONFIG_DIR if YOUR_DATABASE and YOUR_DATABASE.CONFIG_DIR else ""

        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)
        self.output_dir = output_dir or cache_dir
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    def fetch(self, query: str | dict | list, *, method: str = "SOME_DEFAULT", **kwargs: Any) -> Any:
        """Fetch data from the example API."""
        url = f"{YOUR_DATABASE.API_URL}{method}/{query}"
        try:
            response = self.session.get(url)
            self._delay()
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException:
            log.exception("Error fetching %s for method '%s'", query, method)
            return {}

    def parse(self, data: dict | list, fields_to_extract: list | dict | None, **kwargs: Any) -> dict | list:
        """Parse the API response."""
        return self._extract_fields(data, fields_to_extract)

    def query_usage(self) -> str:
        """Return a usage example string."""
        return "Describe how to query YourDatabase here."
