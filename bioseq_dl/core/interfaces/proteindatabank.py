import os
from typing import Any

import pandas as pd
import requests
import yaml
from requests import Request
from requests.exceptions import RequestException

from bioseq_dl.constants.databases import PDB
from bioseq_dl.core.utils.base_auxiliary_methods import validate_parameters
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.pdb")

# Check https://data.rcsb.org/rest/v1/core/entry/4HHB for more attributes
# rcsbapi package usage tutorial at: https://pdb101.rcsb.org/train/training-events/apis-python
# more info: https://data.rcsb.org/rest/v1/schema/entry
# more info: https://data.rcsb.org/redoc/index.html#tag/Entry-Service/operation/getEntryById


class PDBInterface(BaseAPIInterface):
    API_NAME = "PDB"
    METHODS = {
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
        **kwargs,
    ):
        """Initialize the PDBInterface.
        Args:.
            batch_size (int): Number of entries to process in each batch.
            download_structures (bool): Whether to download structure files. Default is False.
            cache_dir (str): Directory to cache API responses. If None, defaults to the cache directory defined in constants.
            config_dir (str): Directory for configuration files. If None, defaults to the config directory defined in constants.
            output_dir (str): Directory to save downloaded files. If None, defaults to the cache directory.
        """
        if cache_dir:
            cache_dir = os.path.abspath(cache_dir)
        else:
            cache_dir = PDB.CACHE_DIR if PDB.CACHE_DIR is not None else ""

        if config_dir is None:
            config_dir = PDB.CONFIG_DIR if PDB.CONFIG_DIR is not None else ""

        download_folder_fallback = cache_dir
        if os.path.exists(config_dir + "/init.yml"):
            with open(config_dir + "/init.yml") as f:
                config = yaml.safe_load(f)
            download_folder_fallback = config.get("download_folder", cache_dir)

        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)
        self.output_dir = output_dir or download_folder_fallback
        os.makedirs(self.output_dir, exist_ok=True)

        self.batch_size = batch_size
        self.download_structures = download_structures

    def fetch(self, query: str | dict | list, *, method: str = "entry", **kwargs):
        """Run a query to fetch data from the PDB database.

        Args:
            query (str): PDB ID to fetch data for.
            method (str): API method to use. Default is "entry".

        Returns:
            dict: Fetched data for the given PDB ID.

        """
        if method not in self.METHODS.keys():
            log.error(f"Method {method} is not supported. Available methods: {list(self.METHODS.keys())}")
            return {}

        http_method, path_param, parameters, inputs = self.initialize_method_parameters(
            query, method, self.METHODS, **kwargs
        )

        # Validate and clean parameters
        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError as e:
            log.error(f"Invalid parameters for method '{method}': {e}")
            return {}

        url = f"{PDB.API_URL}{method}"

        if path_param:
            if isinstance(path_param, list):
                url += "/" + "/".join(
                    str(validated_params.pop(param)) for param in path_param if param in validated_params
                )
            else:
                url += f"/{validated_params.pop(path_param)}"

        response = Request(
            url=url,
            method=http_method,
        )

        prepared = self.session.prepare_request(response)
        log.debug(f"Prepared request: {prepared.url}")

        try:
            response = self.session.send(prepared)
            self._delay()
            response.raise_for_status()

            return response.json()
        except RequestException as e:
            log.error(f"Error fetching data from {url}: {e}")
            return {}

    def fetch_structure(self, pdb_id: str, file_format: str = "pdb") -> str:
        """Download the structure file for a given PDB ID.

        Args:
            pdb_id (str): PDB ID to download.
            file_format (str): Format of the file to download. Default is "pdb".

        Returns:
            str: Path to the downloaded file.

        """
        log.info(f"Fetching structure for {pdb_id} in {file_format} format...")
        if os.path.exists(self.output_dir + f"/{pdb_id}.{file_format}"):
            log.info(f"Structure for {pdb_id} already exists in {file_format} format.")
            return self.output_dir + f"/{pdb_id}.{file_format}"

        log.info(f"Downloading {pdb_id} in {file_format} format...")

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        url = f"{PDB.STRUCTURE_URL}{pdb_id}.{file_format}"

        try:
            response = self.session.get(url)
            self._delay()
            response.raise_for_status()
            file_path = os.path.join(self.output_dir, f"{pdb_id}.{file_format}")
            with open(file_path, "wb") as f:
                f.write(response.content)
            return file_path
        except requests.exceptions.RequestException as e:
            log.error(f"Error downloading structure for {pdb_id}: {e}")
            return ""

    def fetch_single(
        self, query: str | dict | list[str], parse: bool = False, *args, **kwargs
    ) -> list | dict | pd.DataFrame:

        if self.download_structures and query and isinstance(query, str):
            self.fetch_structure(query)
        return super().fetch_single(query, parse, *args, **kwargs)

    def fetch_batch(
        self, queries: list[str | dict], parse: bool = False, *args, **kwargs
    ) -> list | pd.DataFrame:
        results = super().fetch_batch(queries, parse, *args, **kwargs)
        if self.download_structures:
            for query in queries:
                if isinstance(query, str):
                    self.fetch_structure(query)
        return results

    def parse(self, data: Any, fields_to_extract: list | dict | None, **kwargs):
        """Parse data by extracting specified fields or returning the entire structure.

        Args:
            data (Union[List, Dict]): Data to parse.
            fields_to_extract (list|dict): Fields to keep from the original response.
                - If list: Keep those keys.
                - If dict: Maps {desired_name: real_field_name}.

        Returns:
            Union[List, Dict]: Parsed data with specified fields or the entire structure.

        """
        # Check input data type
        if not isinstance(data, (list, dict)):
            log.error(
                "Tried to parse data but the type is not supported. Data should be a list or a dictionary."
            )
            return {}

        return self._extract_fields(data, fields_to_extract)

    def query_usage(self) -> str:
        return """Usage: To fetch PDB entries, use the PDB ID as the query.
        Example:
            - fetch_single("4HHB")
            - fetch_batch(["4HHB", "1A2B"])
        Also you can download structures by setting the `download_structures` parameter in the constructor.
        Example:
            - pdb_interface = PDBInterface(download_structures=True)
            - entry = pdb_interface.fetch_single("4HHB")
        """
