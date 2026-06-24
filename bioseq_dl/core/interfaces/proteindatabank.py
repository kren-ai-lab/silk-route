"""RCSB Protein Data Bank API interface."""

from collections.abc import Sequence
from pathlib import Path
from typing import Any, ClassVar

import niquests
import pandas as pd
from niquests import Request

from bioseq_dl.constants.databases import PDB
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.pdb")

# Check https://data.rcsb.org/rest/v1/core/entry/4HHB for more attributes
# rcsbapi package usage tutorial at: https://pdb101.rcsb.org/train/training-events/apis-python
# more info: https://data.rcsb.org/rest/v1/schema/entry
# more info: https://data.rcsb.org/redoc/index.html#tag/Entry-Service/operation/getEntryById


class PDBInterface(BaseAPIInterface):
    """RCSB Protein Data Bank API interface."""

    API_NAME = "PDB"
    DB_CONFIG = PDB
    METHODS: ClassVar[dict[str, Any]] = {
        "entry": {
            "http_method": "GET",
            "path_param": "id",
            "parameters": {
                "id": (str, None, True),
            },
            "group_queries": [None],
            "separator": None,
        }
    }

    def __init__(
        self,
        batch_size: int = 5000,
        download_structures: bool = True,
        cache_dir: str | None = None,
        config_dir: str | None = None,
        output_dir: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the PDBInterface.

        Args:
            batch_size (int): Number of entries to process in each batch.
            download_structures (bool): Whether to download structure files. Default is False.
            cache_dir (str): Directory to cache API responses. If None, defaults to the cache directory
                defined in constants.
            config_dir (str): Directory for configuration files. If None, defaults to the config directory
                defined in constants.
            output_dir (str): Directory to save downloaded files. If None, defaults to the cache directory.
            **kwargs: Passed through to the base class.

        """
        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)
        self.output_dir = self._resolve_output_dir(output_dir, init_subdir="pdb")

        self.batch_size = batch_size
        self.download_structures = download_structures

    def _build_request(
        self, *, method: str, http_method: str, path_param: Any, validated_params: dict, **_kwargs: Any
    ) -> Request:
        """Build the PDB request URL (method + path segments, no query params)."""
        url = f"{PDB.API_URL}{method}"
        url = self._append_path_params(url, path_param, validated_params)
        return Request(url=url, method=http_method)

    def fetch_structure(self, pdb_id: str, file_format: str = "pdb") -> str:
        """Download the structure file for a given PDB ID.

        Args:
            pdb_id (str): PDB ID to download.
            file_format (str): Format of the file to download. Default is "pdb".

        Returns:
            str: Path to the downloaded file.

        """
        log.info("Fetching structure for %s in %s format...", pdb_id, file_format)
        existing = Path(self.output_dir) / f"{pdb_id}.{file_format}"
        if existing.exists():
            log.info("Structure for %s already exists in %s format.", pdb_id, file_format)
            return str(existing)

        log.info("Downloading %s in %s format...", pdb_id, file_format)

        if not Path(self.output_dir).exists():
            Path(self.output_dir).mkdir(parents=True)

        url = f"{PDB.STRUCTURE_URL}{pdb_id}.{file_format}"

        try:
            response = self.session.get(url)
            self._delay()
            response.raise_for_status()
            file_path = Path(self.output_dir) / f"{pdb_id}.{file_format}"
            with file_path.open("wb") as f:
                f.write(response.content or b"")
            return str(file_path)
        except niquests.exceptions.RequestException:
            log.exception("Error downloading structure for %s", pdb_id)
            return ""

    def fetch_single(
        self, query: str | dict | list[str], parse: bool = False, *args: Any, **kwargs: Any
    ) -> tuple[list | dict | pd.DataFrame | bytes | str, dict]:
        """Fetch a single PDB entry and optionally download the structure file.

        Downloads the structure file when ``download_structures`` is set and the query is a
        single PDB id, then delegates to the base fetch.

        Args:
            query (str | dict | list[str]): PDB entry identifier to fetch.
            parse (bool): Whether to run ``parse`` on the raw response.
            *args: Forwarded to the base fetch.
            **kwargs: Forwarded to the base fetch.

        Returns:
            tuple[list | dict | pd.DataFrame | bytes | str, dict]: Fetched data and metadata.

        """
        if self.download_structures and query and isinstance(query, str):
            self.fetch_structure(query)
        return super().fetch_single(query, parse, *args, **kwargs)

    def fetch_batch(
        self, queries: Sequence[str | dict], parse: bool = False, *args: Any, **kwargs: Any
    ) -> tuple[list | pd.DataFrame | bytes | str, dict]:
        """Fetch a batch of PDB entries and optionally download structure files.

        Delegates to the base fetch, then downloads the structure file for each string id
        when ``download_structures`` is set.

        Args:
            queries (Sequence[str | dict]): PDB entry identifiers to fetch.
            parse (bool): Whether to run ``parse`` on each raw response.
            *args: Forwarded to the base fetch.
            **kwargs: Forwarded to the base fetch.

        Returns:
            tuple[list | pd.DataFrame | bytes | str, dict]: Fetched data and metadata.

        """
        results = super().fetch_batch(queries, parse, *args, **kwargs)
        if self.download_structures:
            for query in queries:
                if isinstance(query, str):
                    self.fetch_structure(query)
        return results
