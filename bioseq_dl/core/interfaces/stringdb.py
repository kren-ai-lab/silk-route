import os, requests, logging
from typing import Optional, Set, Union, Any, List, Dict
import pandas as pd
from requests import Request
from requests.exceptions import RequestException

from .base import BaseAPIInterface
from ..utils.base_auxiliary_methods import get_nested, validate_parameters
from ...constants.databases import STRING
from ...constants.stringdb import METHOD_FORMATS, METHODS, METHOD_PARAMS

# ----- Optional logging (fallback to stdlib) -----
try:
    from bioseq_dl.logging import get_logger
except Exception:
    def get_logger(name: str) -> logging.Logger:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        return logging.getLogger(name)

log = get_logger("bioseq_dl.interfaces.stringdb")
# -------------------------------------------------

## More info about STRING API: https://string-db.org/cgi/help

class StringInterface(BaseAPIInterface):
    API_NAME = "STRING"
    METHODS = {
        "get_string_ids": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "identifiers": (str, None, True),
                "species": (int, None, False),
                "echo_query": (int, 0, False),
                "format": (str, "json", False),
            },
            "group_queries": ["identifiers", "species"],
            "separator": "%0d"
        },
        "interaction_partners": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "identifiers": (str, None, True),
                "species": (int, None, False),
                "limit": (int, None, False),
                "required_score": (int, None, False),
                "network_type": (str, "functional", False),
            },
            "group_queries": ["identifiers", "species"],
            "separator": "%0d"
        },
        # Add other methods as needed
    }
    def __init__(
            self,
            cache_dir: Optional[str] = None,
            config_dir: Optional[str] = None,
            **kwargs
    ):
        """
        Initialize the StringInterface class.
        Args:
            cache_dir (str): Directory to cache API responses. If None, defaults to the cache directory defined in constants.
            config_dir (str): Directory for configuration files. If None, defaults to the config directory defined in constants.
            output_dir (str): Directory to save downloaded files. If None, defaults to the cache directory.
        """
        if cache_dir:
            cache_dir = os.path.abspath(cache_dir)
        else:
            cache_dir = STRING.CACHE_DIR if STRING.CACHE_DIR is not None else ""

        if config_dir is None:
            config_dir = STRING.CONFIG_DIR if STRING.CONFIG_DIR is not None else ""

        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)
    
    # def get_subquery_match_keys(self) -> Set[str]:
    #     return super().get_subquery_match_keys().union({"identifiers", "species"})

    def fetch(self, query: Union[str, dict, list], *, method: str = "get_string_ids", **kwargs):
        """
        Fetch data from the STRING API.
        Args:
            query (str|dict|list): Query parameters for the API.
            method (str): Method to use for the request.
            outfmt (str): Output format for the response.
        Returns:
            dict: Parsed response from the API.
        """
        if method not in self.METHODS.keys():
            log.error(f"Method '{method}' is not supported. Available methods: {list(self.METHODS.keys())}")
            return {}

        http_method, path_param, parameters, inputs = self.initialize_method_parameters(query, method, self.METHODS, **kwargs)

        try:
            validated_params = validate_parameters(inputs, parameters)
        except (ValueError, TypeError) as e:
            log.error(f"Parameter validation failed: {e}")
            return {}

        if "format" in validated_params:
            outfmt = validated_params.pop("format")
        else:
            outfmt = "json"

        if outfmt not in METHOD_FORMATS[method]:
            log.error(f"Output format {outfmt} is not supported for method {method}. Supported formats are: {', '.join(METHOD_FORMATS[method])}.")
            return {}

        url = f"{STRING.API_URL}{outfmt}/{method}"


        req = Request(
            method=http_method,
            url=url,
            params=validated_params
        )

        prepared = self.session.prepare_request(req)
        log.debug(f"Prepared request URL: {prepared.url}")

        try:
            response = self.session.send(prepared)
            self._delay()
            response.raise_for_status()

            return response.json()
        except RequestException as e:
            log.error(f"Error fetching {query} for method '{method}': {e}")
            return {}
        
        
    def parse(
            self, 
            data: Any,
            fields_to_extract: Optional[Union[list, dict]],
            **kwargs
        ) -> Any:
        """
        Parse the response from the STRING API.
        Args:
            data (Any): Data to parse.
            fields_to_extract (List|Dict): Fields to keep from the original response.
                - If List: Keep those keys.
                - If Dict: Maps {desired_name: real_field_name}
            fmt (str): Format of the response.
        Returns:
            dict: Parsed response.
        """
        fmt = kwargs.get("fmt", "json")
        if not data:
            return {}
        
        if fmt == "json":
            return self._extract_fields(data, fields_to_extract)

        elif fmt == "tsv":
            return data.text
        elif fmt == "image":
            log.error("Image format is not supported for parsing. Please use the method save_image() to save the image.")
        else:
            log.error(f"Format {fmt} is not supported. Supported formats are: json, tsv")
            return {}

    def query_usage(self) -> str:
        return (
            "To query STRING, use the method name and parameters as a dictionary. "
            "Example usage:\n"
            "string_instance.fetch(query={'identifiers': ['p53', 'cdk2'], 'species': 9606}, method='get_string_ids', outfmt='json')\n"
            "Supported methods: " + ", ".join(METHODS) + "\n"
            "Supported output formats: " + ", ".join(METHOD_FORMATS['get_string_ids'])
        )
        
    # def save_image(self, response: Any, filename: str):
    #     """
    #     Save the image response from the STRING API.
    #     Args:
    #         response (any): Response from the API.
    #         filename (str): Name of the file to save the image.
    #     """
    #     if not filename.endswith(".png"):
    #         filename += ".png"
    #
    #     with open(filename, "wb") as f:
    #         f.write(response.content)
    #     print(f"Image saved as {filename}")

    # def fetch_to_dataframe(
    #         self, 
    #         method: str = "get_string_ids", 
    #         outfmt: str = "json",
    #         params: dict = None,
    # ):
    #     """
    #     Fetch data from the STRING API and return it as a DataFrame.
    #     Args:
    #         identifiers (list): List of identifiers to fetch.
    #         method (str): Method to use for the request.
    #         outfmt (str): Output format for the response.
    #         params (dict): Parameters for the request.
    #     Returns:
    #         pd.DataFrame: DataFrame containing the fetched data.
    #     """
    #     response = self.fetch(outfmt=outfmt, method=method, params=params)
    #     parsed_response = self.parse(response, fmt=outfmt)
    #     return pd.DataFrame(parsed_response) if parsed_response else None
