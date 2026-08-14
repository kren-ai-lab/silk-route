"""AlphaFold API interface."""

import json
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, ClassVar, Literal, cast
from urllib.parse import unquote, urlparse

import niquests
import polars as pl

from silkroute.constants.databases import ALPHAFOLD
from silkroute.core.export import export_dataframe
from silkroute.core.utils.frames import records_to_frame
from silkroute.core.utils.structure_files import (
    WINDOWS_RESERVED_FILENAMES,
    attach_pdb_file,
    display_structure_path,
    records_to_structure_frame,
)
from silkroute.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("silkroute.interfaces.alphafold")


def _structure_filename_from_url(structure_url: str) -> str | None:
    """Extract a deterministic filename from a structure URL."""
    parsed_path = urlparse(structure_url).path
    file_name = unquote(parsed_path.rsplit("/", 1)[-1])
    return file_name or None


def _safe_structure_file_path(output_dir: str | Path, file_name: str) -> Path | None:
    """Return a resolved file path if ``file_name`` stays below ``output_dir``."""
    if (
        not file_name
        or file_name in {".", ".."}
        or file_name != file_name.rstrip(" .")
        or ":" in file_name
        or "/" in file_name
        or "\\" in file_name
    ):
        log.warning("Skipping unsafe AlphaFold structure filename: %s", file_name)
        return None
    file_stem = file_name.split(".", 1)[0].upper()
    if file_stem in WINDOWS_RESERVED_FILENAMES:
        log.warning("Skipping Windows-reserved AlphaFold structure filename: %s", file_name)
        return None

    base_dir = Path(output_dir).resolve()
    file_path = (base_dir / file_name).resolve()
    try:
        file_path.relative_to(base_dir)
    except ValueError:
        log.warning("Skipping AlphaFold structure path outside output directory: %s", file_path)
        return None
    return file_path


class AlphafoldInterface(BaseAPIInterface):
    """AlphaFold structure prediction API interface."""

    API_NAME = "Alphafold"
    DB_CONFIG = ALPHAFOLD
    # Endpoints are ``{method}/{qualifier}``; responses wrap rows in ``results``.
    _METHOD_SUFFIX: ClassVar[str] = "/"
    _RESPONSE_ENVELOPE_KEYS: ClassVar[tuple[str, ...]] = ("results",)
    METHODS: ClassVar[dict[str, Any]] = {
        "prediction": {
            "http_method": "GET",
            "path_param": "qualifier",
            "parameters": {
                "qualifier": (str, None, True),
            },
            "group_queries": [None],
            "separator": None,
        }
    }

    def __init__(
        self,
        structures: list[Literal["pdb", "cif", "bcif"]] | None = None,
        cache_dir: str | None = None,
        config_dir: str | None = None,
        output_dir: str | None = None,
        path_base: str | Path | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the AlphafoldInterface.

        Args:
            structures (list[str] | None): Structure file extensions to download. Available options are pdb,
                cif, bcif.
            cache_dir (str): Directory to cache API responses. If None, defaults to the cache directory
                defined in constants.
            config_dir (str): Directory for configuration files. If None, defaults to the config directory
                defined in constants.
            output_dir (str): Directory to save downloaded files. If None, defaults to the cache directory.
            path_base (str | Path | None): Optional base directory used to make downloaded structure paths
                relative in workflow output.
            **kwargs: Passed through to the base class.

        """
        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)
        if structures:
            self.output_dir = self._resolve_output_dir(output_dir, init_subdir="alphafold")
        else:
            self.output_dir = self._resolve_output_dir(output_dir, init_subdir="alphafold", create=False)

        self.structures = structures
        self.path_base = path_base

    @staticmethod
    def _iter_records(result: Any) -> Iterator[dict]:
        """Yield the individual record dicts contained in a fetch result."""
        if isinstance(result, list):
            for item in result:
                yield from AlphafoldInterface._iter_records(item)
        elif isinstance(result, pl.DataFrame):
            yield from result.iter_rows(named=True)
        elif isinstance(result, dict):
            yield result

    def fetch_single(
        self, query: str | dict, parse: bool = False, *args: Any, **kwargs: Any
    ) -> tuple[list | dict | pl.DataFrame | bytes | str, dict]:
        """Fetch a single prediction and optionally download structure files.

        Delegates to the base fetch, then downloads configured structure files for each
        record when ``structures`` is set. Returns empty data if ``query`` is not a string.

        Args:
            query (str | dict): AlphaFold/UniProt identifier to fetch.
            parse (bool): Whether to run ``parse`` on the raw response.
            *args: Forwarded to the base fetch.
            **kwargs: Forwarded to the base fetch.

        Returns:
            tuple[list | dict | pl.DataFrame | bytes | str, dict]: Fetched data and metadata.

        """
        if not isinstance(query, str):
            log.error("Query must be a string representing a AlphaFold ID.")
            return {}, {}

        result, metadata = super().fetch_single(query, parse, *args, **kwargs)

        if self.structures:
            result = self._download_structures_for_result(result)

        return result, metadata

    def fetch_batch(
        self, queries: Sequence[str | dict], parse: bool = False, *args: Any, **kwargs: Any
    ) -> tuple[list | pl.DataFrame | bytes | str, dict]:
        """Fetch a batch of predictions and optionally download structure files.

        Delegates to the base fetch, then downloads configured structure files for each
        record when ``structures`` is set. Returns empty data if ``queries`` is not a list
        of strings.

        Args:
            queries (Sequence[str | dict]): AlphaFold/UniProt identifiers to fetch.
            parse (bool): Whether to run ``parse`` on each raw response.
            *args: Forwarded to the base fetch.
            **kwargs: Forwarded to the base fetch.

        Returns:
            tuple[list | pl.DataFrame | bytes | str, dict]: Fetched data and metadata.

        """
        if not isinstance(queries, list) or not queries or not isinstance(queries[0], str):
            log.error("Queries must be a list of strings representing AlphaFold IDs.")
            return [], {}

        results, metadata = super().fetch_batch(queries, parse, *args, **kwargs)

        if not self.structures:
            return results, metadata

        return self._download_structures_for_result(results), metadata

    def _download_structures_for_result(self, result: Any) -> Any:
        """Return ``result`` with downloaded structure paths attached to records."""
        if isinstance(result, pl.DataFrame):
            return records_to_structure_frame(
                [self.download_structures(record) for record in result.iter_rows(named=True)]
            )
        if isinstance(result, list):
            return [self._download_structures_for_result(item) for item in result]
        if isinstance(result, dict):
            return self.download_structures(result)
        return result

    def download_structures(self, parsed: dict) -> dict:
        """Download structure files based on parsed prediction info.

        Args:
            parsed (dict): Parsed data containing URLs for structures.

        Returns:
            dict: Parsed data without the structure URLs.

        """
        if not self.structures:
            return parsed if parsed is not None else {}

        for ext in self.structures:
            url_key = f"{ext}Url"
            file_key = f"{ext}_file"
            if url_key not in parsed:
                log.warning("%s not found in parsed data. %s", url_key, parsed)
                if ext == "pdb":
                    attach_pdb_file(parsed, None)
                continue

            structure_url = parsed[url_key]
            if not structure_url:
                log.warning("%s is empty; skipping download. %s", url_key, parsed)
                if ext == "pdb":
                    attach_pdb_file(parsed, None)
                continue
            file_name = _structure_filename_from_url(str(structure_url))
            if file_name is None:
                log.warning("Could not determine AlphaFold structure filename from URL: %s", structure_url)
                if ext == "pdb":
                    attach_pdb_file(parsed, None)
                continue
            file_path = _safe_structure_file_path(self.output_dir, file_name)
            if file_path is None:
                if ext == "pdb":
                    attach_pdb_file(parsed, None)
                continue

            # Check if the file already exists
            if file_path.exists():
                parsed.pop(url_key, None)
                if file_key == "pdb_file":
                    attach_pdb_file(parsed, display_structure_path(file_path, self.path_base))
                log.info("Structure %s already exists. Skipping download.", file_name)
                continue

            try:
                response = self.session.get(structure_url)
                response.raise_for_status()
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with file_path.open("wb") as f:
                    log.info("Downloading structure %s...", file_name)
                    f.write(cast("bytes", response.content))

            except (OSError, niquests.exceptions.RequestException):
                log.exception("Error downloading structure %s", file_name)
                if file_key == "pdb_file":
                    attach_pdb_file(parsed, None)
            else:
                parsed.pop(url_key, None)
                if file_key == "pdb_file":
                    attach_pdb_file(parsed, display_structure_path(file_path, self.path_base))

        return parsed if parsed is not None else {}

    def parse(self, data: list | dict, fields_to_extract: list | dict | None, **_kwargs: Any) -> list | dict:
        """Parse data by extracting specified fields or returning the entire structure.

        Args:
            data (list | dict): Data to parse.
            fields_to_extract (list | dict | None): Fields to keep from the original response.
                - If list: Keep those keys.
                - If dict: Maps {desired_name: real_field_name}.
            **_kwargs: Additional keyword arguments.

        Returns:
            list | dict: Parsed data with specified fields or the entire structure.

        """
        # Check input data type
        if not isinstance(data, (list, dict)):
            log.error(
                "Tried to parse data but the type is not supported. Response should be a dict or a list."
            )
            return {}

        # Check if structures are requested
        if self.structures:
            # Add new key in fields_to_extract for each structure type
            for ext in self.structures:
                if isinstance(fields_to_extract, list):
                    fields_to_extract.append(f"{ext}Url")
                elif isinstance(fields_to_extract, dict):
                    fields_to_extract[f"{ext}Url"] = f"{ext}Url"

        return self._extract_fields(data, fields_to_extract)

    def save(self, data: list | dict, filename: str, extension: str = "csv") -> str | None:
        """Save the parsed data to a file.

        Args:
            data (list | dict): Data to save.
            filename (str): Name of the file to save the data to.
            extension (str): File format. One of csv, tsv, json, parquet.

        Returns:
            str | None: Path to the saved file, or None if the extension is unsupported.

        """
        if not Path(self.output_dir).exists():
            Path(self.output_dir).mkdir(parents=True)

        if extension not in ["csv", "tsv", "json", "parquet"]:
            log.error("Unsupported file extension: %s. Use 'csv', 'tsv', 'json', or 'parquet'.", extension)
            return None

        if extension == "json":
            with (Path(self.output_dir) / f"{filename}.{extension}").open("w") as f:
                json.dump(data, f, indent=4)
            return str(Path(self.output_dir) / f"{filename}.{extension}")

        df = records_to_frame(data)
        output_path = str(Path(self.output_dir) / f"{filename}.{extension}")
        export_dataframe(df, output_path, output_format=extension)
        return output_path
