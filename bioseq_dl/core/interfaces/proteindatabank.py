"""RCSB Protein Data Bank API interface."""

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, ClassVar

import niquests
import polars as pl
from niquests import Request

from bioseq_dl.constants.databases import PDB
from bioseq_dl.core.interfacesconfig import load_packaged_config
from bioseq_dl.core.metadata import FetchMetadata
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.pdb")

PDB_ID_PATTERN = re.compile(r"^[A-Za-z0-9]{4}$")
STRUCTURE_FORMAT_PATTERN = re.compile(r"^[A-Za-z0-9]+$")
WINDOWS_RESERVED_FILENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}

# Check https://data.rcsb.org/rest/v1/core/entry/4HHB for more attributes
# rcsbapi package usage tutorial at: https://pdb101.rcsb.org/train/training-events/apis-python
# more info: https://data.rcsb.org/rest/v1/schema/entry
# more info: https://data.rcsb.org/redoc/index.html#tag/Entry-Service/operation/getEntryById


def _configured_output_dir(cache_dir: str, output_dir: str | None, init_subdir: str) -> str:
    """Resolve the configured output path without creating directories."""
    packaged_init = load_packaged_config(init_subdir, "init.yml") or {}
    return output_dir or packaged_init.get("download_folder") or cache_dir


def _is_empty_result(result: object) -> bool:
    """Return whether a fetched result is empty."""
    if result is None:
        return True
    if isinstance(result, pl.DataFrame):
        return result.is_empty()
    if isinstance(result, (list, tuple, set, dict, str, bytes)):
        return len(result) == 0
    return False


def _metadata_values(metadata: dict, bucket: str, key: str) -> list[Any]:
    """Return values from a fetch metadata bucket."""
    block = metadata.get(bucket)
    if not isinstance(block, dict):
        return []
    values = block.get(key, [])
    return list(values) if isinstance(values, list) else []


def _metadata_failed_for_query(metadata: dict, query: str) -> bool:
    """Return whether child metadata marks ``query`` as failed."""
    query_key = query.casefold()
    failed_values = _metadata_values(metadata, "failed", "ids") + _metadata_values(
        metadata, "failed", "subqueries"
    )
    return any(str(value).casefold() == query_key for value in failed_values)


def _is_successful_child_result(query: str, result: object, metadata: dict) -> bool:
    """Return whether a child fetch produced non-empty successful metadata."""
    return not _metadata_failed_for_query(metadata, query) and not _is_empty_result(result)


def _append_unique_pdb_id(pdb_ids: list[str], pdb_id: str) -> None:
    """Append a PDB ID once, preserving first successful occurrence."""
    pdb_id_key = pdb_id.casefold()
    if all(existing.casefold() != pdb_id_key for existing in pdb_ids):
        pdb_ids.append(pdb_id)


def _safe_structure_file_path(output_dir: str | Path, pdb_id: str, file_format: str) -> Path | None:
    """Return a deterministic structure path if id and format are safe."""
    if pdb_id != pdb_id.rstrip(" .") or ":" in pdb_id or not PDB_ID_PATTERN.fullmatch(pdb_id):
        log.warning("Skipping unsafe or invalid PDB identifier for structure download: %s", pdb_id)
        return None
    if not STRUCTURE_FORMAT_PATTERN.fullmatch(file_format):
        log.warning("Skipping unsafe PDB structure format: %s", file_format)
        return None

    base_dir = Path(output_dir).resolve()
    safe_pdb_id = pdb_id.upper()
    safe_format = file_format.lower()
    if safe_pdb_id in WINDOWS_RESERVED_FILENAMES:
        log.warning("Skipping Windows-reserved PDB identifier for structure download: %s", pdb_id)
        return None
    file_path = (base_dir / f"{safe_pdb_id}.{safe_format}").resolve()
    try:
        file_path.relative_to(base_dir)
    except ValueError:
        log.warning("Skipping PDB structure path outside output directory: %s", file_path)
        return None
    return file_path


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
        download_structures: bool = False,
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
        if download_structures:
            self.output_dir = self._resolve_output_dir(output_dir, init_subdir="pdb")
        else:
            self.output_dir = _configured_output_dir(self.cache_dir, output_dir, "pdb")

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
        file_path = _safe_structure_file_path(self.output_dir, str(pdb_id), str(file_format))
        if file_path is None:
            return ""

        log.info("Fetching structure for %s in %s format...", pdb_id, file_format)
        if file_path.exists():
            log.info("Structure for %s already exists in %s format.", pdb_id, file_format)
            return str(file_path)

        log.info("Downloading %s in %s format...", pdb_id, file_format)

        file_path.parent.mkdir(parents=True, exist_ok=True)

        safe_pdb_id = str(pdb_id).upper()
        safe_format = str(file_format).lower()
        url = f"{PDB.STRUCTURE_URL}{safe_pdb_id}.{safe_format}"

        try:
            response = self.session.get(url)
            self._delay()
            response.raise_for_status()
            with file_path.open("wb") as f:
                f.write(response.content or b"")
            return str(file_path)
        except niquests.exceptions.RequestException:
            log.exception("Error downloading structure for %s", pdb_id)
            return ""

    def fetch_single(
        self, query: str | dict | list[str], parse: bool = False, *args: Any, **kwargs: Any
    ) -> tuple[list | dict | pl.DataFrame | bytes | str, dict]:
        """Fetch a single PDB entry and optionally download the structure file.

        Downloads the structure file when ``download_structures`` is set and the query is a
        single PDB id, then delegates to the base fetch.

        Args:
            query (str | dict | list[str]): PDB entry identifier to fetch.
            parse (bool): Whether to run ``parse`` on the raw response.
            *args: Forwarded to the base fetch.
            **kwargs: Forwarded to the base fetch.

        Returns:
            tuple[list | dict | pl.DataFrame | bytes | str, dict]: Fetched data and metadata.

        """
        result, metadata = super().fetch_single(query, parse, *args, **kwargs)
        if (
            self.download_structures
            and query
            and isinstance(query, str)
            and _is_successful_child_result(query, result, metadata)
        ):
            self.fetch_structure(query)
        return result, metadata

    def fetch_batch(
        self, queries: Sequence[str | dict], parse: bool = False, *args: Any, **kwargs: Any
    ) -> tuple[list | pl.DataFrame | bytes | str, dict]:
        """Fetch a batch of PDB entries and optionally download structure files.

        Delegates to the base fetch, then downloads the structure file for each string id
        when ``download_structures`` is set.

        Args:
            queries (Sequence[str | dict]): PDB entry identifiers to fetch.
            parse (bool): Whether to run ``parse`` on each raw response.
            *args: Forwarded to the base fetch.
            **kwargs: Forwarded to the base fetch.

        Returns:
            tuple[list | pl.DataFrame | bytes | str, dict]: Fetched data and metadata.

        """
        if not self.download_structures:
            return super().fetch_batch(queries, parse, *args, **kwargs)

        results: list[Any] = []
        eligible_structure_ids: list[str] = []
        merged_metadata = FetchMetadata()

        for query in queries:
            if not isinstance(query, str):
                continue
            try:
                result, metadata = super().fetch_single(query, parse, *args, **kwargs)
            except Exception:
                log.exception("Error fetching PDB query during structure-download batch: %s", query)
                continue

            results.append(result)
            merged_metadata = merged_metadata.merge(FetchMetadata.from_dict(metadata))
            if _is_successful_child_result(query, result, metadata):
                _append_unique_pdb_id(eligible_structure_ids, query)

        for pdb_id in eligible_structure_ids:
            self.fetch_structure(pdb_id)

        if all(isinstance(result, pl.DataFrame) for result in results) and results:
            batch_data: list | pl.DataFrame | bytes | str = pl.concat(results, how="diagonal_relaxed")
        else:
            batch_data = results
        return batch_data, merged_metadata.to_dict()
