from typing import Any

from requests import Request
from requests.exceptions import RequestException

from bioseq_dl.constants.databases import STRING
from bioseq_dl.constants.stringdb import METHOD_FORMATS, METHODS
from bioseq_dl.core.utils.base_auxiliary_methods import validate_parameters
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.stringdb")

## More info about STRING API: https://string-db.org/cgi/help


class StringInterface(BaseAPIInterface):
    API_NAME = "STRING"
    DB_CONFIG = STRING
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
            "separator": "%0d",
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
            "separator": "%0d",
        },
        # Add other methods as needed
    }

    # def get_subquery_match_keys(self) -> Set[str]:
    #     return super().get_subquery_match_keys().union({"identifiers", "species"})

    def fetch(self, query: str | dict | list, *, method: str = "get_string_ids", **kwargs):
        """Fetch data from the STRING API.

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

        http_method, path_param, parameters, inputs = self.initialize_method_parameters(
            query, method, self.METHODS, **kwargs
        )

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
            log.error(
                f"Output format {outfmt} is not supported for method {method}. Supported formats are: {', '.join(METHOD_FORMATS[method])}."
            )
            return {}

        url = f"{STRING.API_URL}{outfmt}/{method}"

        req = Request(method=http_method, url=url, params=validated_params)

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

    def parse(self, data: Any, fields_to_extract: list | dict | None, **kwargs) -> Any:
        """Parse the response from the STRING API.

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

        if fmt == "tsv":
            return data.text
        if fmt == "image":
            log.error(
                "Image format is not supported for parsing. Please use the method save_image() to save the image."
            )
        else:
            log.error(f"Format {fmt} is not supported. Supported formats are: json, tsv")
            return {}

    def query_usage(self) -> str:
        return (
            "To query STRING, use the method name and parameters as a dictionary. "
            "Example usage:\n"
            "string_instance.fetch(query={'identifiers': ['p53', 'cdk2'], 'species': 9606}, method='get_string_ids', outfmt='json')\n"
            "Supported methods: " + ", ".join(METHODS) + "\n"
            "Supported output formats: " + ", ".join(METHOD_FORMATS["get_string_ids"])
        )
