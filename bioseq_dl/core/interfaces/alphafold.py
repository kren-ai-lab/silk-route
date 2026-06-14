import json
from pathlib import Path
from typing import Literal

import pandas as pd
from requests import Request
from requests.exceptions import RequestException

from bioseq_dl.constants.databases import ALPHAFOLD
from bioseq_dl.core.export import export_dataframe
from bioseq_dl.core.interfacesconfig import load_packaged_config
from bioseq_dl.core.utils.base_auxiliary_methods import validate_parameters
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.alphafold")


class AlphafoldInterface(BaseAPIInterface):
    API_NAME = "Alphafold"
    DB_CONFIG = ALPHAFOLD
    METHODS = {
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
        structures: list[Literal["pdb", "cif", "bcif"]] | None = ["pdb"],
        cache_dir: str | None = None,
        config_dir: str | None = None,
        output_dir: str | None = None,
        **kwargs,
    ) -> None:
        """Initialize the AlphafoldInterface.

        Args:
            structures (List[str]): List of structures extensions to download. Available options are pdb, cif, bcif, none.
            cache_dir (str): Directory to cache API responses. If None, defaults to the cache directory defined in constants.
            config_dir (str): Directory for configuration files. If None, defaults to the config directory defined in constants.
            output_dir (str): Directory to save downloaded files. If None, defaults to the cache directory.

        """
        cache_dir, config_dir = self._resolve_dirs(cache_dir, config_dir)
        packaged_init = load_packaged_config("alphafold", "init.yml") or {}
        download_folder_fallback = packaged_init.get("download_folder") or cache_dir

        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)
        self.output_dir = output_dir or download_folder_fallback
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

        self.structures = structures

    def fetch_single(
        self, query: str | dict, parse: bool = False, *args, **kwargs
    ) -> tuple[list | dict | pd.DataFrame, dict]:
        if not isinstance(query, str):
            log.error("Query must be a string representing a AlphaFold ID.")
            return {}

        result, metadata = super().fetch_single(query, parse, *args, **kwargs)

        if self.structures:
            if isinstance(result, list):
                for res in result:
                    self.download_structures(res)
            elif isinstance(result, pd.DataFrame):
                for _, row in result.iterrows():
                    row_dict = row.to_dict()
                    self.download_structures(row_dict)
            elif isinstance(result, dict):
                self.download_structures(result)

        return result, metadata

    def fetch_batch(
        self, queries: list[str | dict], parse: bool = False, *args, **kwargs
    ) -> tuple[list | pd.DataFrame, dict]:
        if not isinstance(queries, list) or not isinstance(queries[0], str):
            log.error("Queries must be a list of strings representing AlphaFold IDs.")
            return [], {}

        results, metadata = super().fetch_batch(queries, parse, *args, **kwargs)

        new_results = []
        if self.structures:
            for result in results:
                if isinstance(result, list):
                    for res in result:
                        new_results.append(self.download_structures(res))
                elif isinstance(result, pd.DataFrame):
                    for _, row in result.iterrows():
                        row_dict = row.to_dict()
                        new_results.append(self.download_structures(row_dict))
                elif isinstance(result, dict):
                    new_results = [self.download_structures(result)]

        if new_results:
            return new_results, metadata
        return results, metadata

    def fetch(self, query: str | dict | list, *, method: str = "prediction", **kwargs):
        """Get prediction for a given UniProt ID.

        Args:
            query (str): UniProt ID to fetch prediction for.
            method (str): Method to use for fetching data. Currently only "prediction" is supported.

        Returns:
            Dict: Prediction data.

        """
        if method not in self.METHODS.keys():
            log.error(
                f"Method {method} is not supported. Supported methods are: {', '.join(self.METHODS.keys())}."
            )
            return {}

        http_method, path_param, parameters, inputs = self.initialize_method_parameters(
            query, method, self.METHODS, **kwargs
        )

        # Validate and clean parameters
        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError:
            log.exception(f"Invalid parameters for method '{method}'")
            return {}

        url = f"{ALPHAFOLD.API_URL}{method}/"

        if path_param:
            path_value = validated_params.pop(path_param)
            url += f"{path_value}"

        req = Request(method=http_method, url=url, params=validated_params)
        prepared = self.session.prepare_request(req)
        log.debug(f"Fetching prediction for {query} using URL: {prepared.url}")

        try:
            response = self.session.send(prepared)
            self._delay()
            response.raise_for_status()
        except RequestException:
            log.exception(f"Error fetching prediction for {query}")
            return {}
        else:
            response = response.json()

            if "results" in response:
                response = response["results"]

            return response

    def download_structures(self, parsed: dict) -> dict:
        """Download structure files based on parsed prediction info.

        Args:
            parsed (Dict): Parsed data containing URLs for structures.

        Returns:
            Dict: Parsed data without the structure URLs.

        """
        if not self.structures:
            return parsed if parsed is not None else {}

        for ext in self.structures:
            url_key = f"{ext}Url"
            if url_key not in parsed:
                log.warning(f"{url_key} not found in parsed data. {parsed}")
                continue

            structure_url = parsed[url_key]
            if not structure_url:
                log.warning(f"{url_key} is empty; skipping download. {parsed}")
                continue
            file_name = structure_url.split("/")[-1]
            file_path = Path(self.output_dir) / file_name

            # Delete the URL from parsed data
            del parsed[url_key]

            # Check if the file already exists
            if file_path.exists():
                log.info(f"Structure {file_name} already exists. Skipping download.")
                continue

            try:
                response = self.session.get(structure_url)
                with file_path.open("wb") as f:
                    log.info(f"Downloading structure {file_name}...")
                    f.write(response.content)

            except Exception:
                log.exception(f"Error downloading structure {file_name}")

        return parsed if parsed is not None else {}

    def parse(self, data: list | dict, fields_to_extract: list | dict | None, **kwargs) -> list | dict:
        """Parse data by extracting specified fields or returning the entire structure.

        Args:
            data (Union[List, Dict]): Data to parse.
            fields_to_extract (List|Dict): Fields to keep from the original response.
                - If List: Keep those keys.
                - If Dict: Maps {desired_name: real_field_name}.
            for more information, see: https://alphafold.ebi.ac.uk/#/public-api/get_predictions_api_prediction__qualifier__get
        Returns:
            Union[List, Dict]: Parsed data with specified fields or the entire structure.

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

    def save(self, data: list | dict, filename: str, extension: str = "csv"):
        """Save the parsed data to a file.

        Args:
            data (Union[List, Dict]): Data to save.
            file_name (str): Name of the file to save the data to.

        """
        if not Path(self.output_dir).exists():
            Path(self.output_dir).mkdir(parents=True)

        if extension not in ["csv", "tsv", "json", "parquet"]:
            log.error(f"Unsupported file extension: {extension}. Use 'csv', 'tsv', 'json', or 'parquet'.")
            return None

        if extension == "json":
            with (Path(self.output_dir) / f"{filename}.{extension}").open("w") as f:
                json.dump(data, f, indent=4)
            return str(Path(self.output_dir) / f"{filename}.{extension}")

        df = pd.DataFrame(data)
        output_path = str(Path(self.output_dir) / f"{filename}.{extension}")
        export_dataframe(df, output_path, output_format=extension)
        return output_path
