"""AlphaFold API interface."""

import json
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, ClassVar, Literal

import pandas as pd

from bioseq_dl.constants.databases import ALPHAFOLD
from bioseq_dl.core.export import export_dataframe
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.alphafold")


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
            **kwargs: Passed through to the base class.

        """
        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)
        self.output_dir = self._resolve_output_dir(output_dir, init_subdir="alphafold")

        self.structures = structures

    @staticmethod
    def _iter_records(result: Any) -> Iterator[dict]:
        """Yield the individual record dicts contained in a fetch result."""
        if isinstance(result, list):
            yield from result
        elif isinstance(result, pd.DataFrame):
            for _, row in result.iterrows():
                yield row.to_dict()
        elif isinstance(result, dict):
            yield result

    def fetch_single(
        self, query: str | dict, parse: bool = False, *args: Any, **kwargs: Any
    ) -> tuple[list | dict | pd.DataFrame | bytes | str, dict]:
        """Fetch a single prediction and optionally download structure files.

        Delegates to the base fetch, then downloads configured structure files for each
        record when ``structures`` is set. Returns empty data if ``query`` is not a string.

        Args:
            query (str | dict): AlphaFold/UniProt identifier to fetch.
            parse (bool): Whether to run ``parse`` on the raw response.
            *args: Forwarded to the base fetch.
            **kwargs: Forwarded to the base fetch.

        Returns:
            tuple[list | dict | pd.DataFrame | bytes | str, dict]: Fetched data and metadata.

        """
        if not isinstance(query, str):
            log.error("Query must be a string representing a AlphaFold ID.")
            return {}, {}

        result, metadata = super().fetch_single(query, parse, *args, **kwargs)

        if self.structures:
            for record in self._iter_records(result):
                self.download_structures(record)

        return result, metadata

    def fetch_batch(
        self, queries: Sequence[str | dict], parse: bool = False, *args: Any, **kwargs: Any
    ) -> tuple[list | pd.DataFrame | bytes | str, dict]:
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
            tuple[list | pd.DataFrame | bytes | str, dict]: Fetched data and metadata.

        """
        if not isinstance(queries, list) or not isinstance(queries[0], str):
            log.error("Queries must be a list of strings representing AlphaFold IDs.")
            return [], {}

        results, metadata = super().fetch_batch(queries, parse, *args, **kwargs)

        if not self.structures:
            return results, metadata

        new_results = [
            self.download_structures(record) for result in results for record in self._iter_records(result)
        ]
        return (new_results or results), metadata

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
            if url_key not in parsed:
                log.warning("%s not found in parsed data. %s", url_key, parsed)
                continue

            structure_url = parsed[url_key]
            if not structure_url:
                log.warning("%s is empty; skipping download. %s", url_key, parsed)
                continue
            file_name = structure_url.split("/")[-1]
            file_path = Path(self.output_dir) / file_name

            # Delete the URL from parsed data
            del parsed[url_key]

            # Check if the file already exists
            if file_path.exists():
                log.info("Structure %s already exists. Skipping download.", file_name)
                continue

            try:
                response = self.session.get(structure_url)
                with file_path.open("wb") as f:
                    log.info("Downloading structure %s...", file_name)
                    f.write(response.content)

            except Exception:
                log.exception("Error downloading structure %s", file_name)

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

        df = pd.DataFrame(data)
        output_path = str(Path(self.output_dir) / f"{filename}.{extension}")
        export_dataframe(df, output_path, output_format=extension)
        return output_path
