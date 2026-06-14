"""Reactome API interface."""

from typing import Any

import requests

from bioseq_dl.constants.databases import REACTOME
from bioseq_dl.constants.reactome import methods
from bioseq_dl.core.exceptions import ConfigError
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.reactome")

# TODO(diego): Need to review other methods besides data-discover


class ReactomeInterface(BaseAPIInterface):
    """Reactome biological pathway database API interface."""

    API_NAME = "Reactome"
    DB_CONFIG = REACTOME
    METHODS = {
        "data-discover": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "id": (str, None, True),
            },
            "group_queries": [None],
            "separator": None,
        }
    }

    def validate_query(self, query: dict) -> None:
        """Validate the query parameters.

        Args:
            method (str): The method to validate against.
            query (dict): The query parameters to validate.

        Raises:
            ConfigError: If the query parameters are invalid.

        """
        rules = {
            "id": (
                lambda v: isinstance(v, str) and v.strip() != "",
                "Invalid ID: {value}. It should be a non-empty string.",
            ),
            "species": (
                lambda v: isinstance(v, str) and v.strip() != "",
                "Invalid species: {value}. It should be a non-empty string.",
            ),
            "onlyDiagrammed": (
                lambda v: isinstance(v, bool),
                "Invalid onlyDiagrammed: {value}. It should be a boolean value.",
            ),
        }

        for key, (check, message) in rules.items():
            if key in query and not check(query[key]):
                msg = message.format(value=query[key])
                log.error(msg)
                raise ConfigError(msg)

    def fetch(self, query: str | dict | list, *, method: str = "data", **kwargs: Any) -> dict | list:
        """Download pathways from a given Reactome pathway ID.

        Args:
            query (str|dict|list): Reactome pathway ID or query dict.
            method (str): Method to use for fetching data (e.g., 'discover', 'complex', etc.).
            **kwargs: Supports `option` key for additional method options.

        Returns:
            dict: Pathway data.

        """
        option = kwargs.get("option", "")

        if not method:
            log.error("Method must be specified in the query parameters.")
            return {}

        if option and not isinstance(option, str):
            log.error("Option must be a string if provided.")
            return {}

        primary_method = method.split("-", maxsplit=1)[0]
        secondary_method = "/".join(method.split("-")[1:])
        if primary_method not in methods:
            log.error(
                f"Method '{primary_method}' is not supported. Supported methods are: {list(methods.keys())}"
            )
            return {}
        if secondary_method not in methods[primary_method]:
            log.error(
                f"Method '{secondary_method}' is not supported. Supported methods are: {methods[primary_method]}"
            )
            return {}

        q = ""
        if isinstance(query, str):
            q = query.strip()
        if isinstance(query, dict):
            self.validate_query(query)
            q = query.get("id", "").strip()

        url = f"{REACTOME.API_URL}{method.replace('-', '/')}/{q}/{option}"

        if isinstance(query, dict):
            url += "?"
            for key, value in query.items():
                if key != "id":
                    url += f"{key}={value}&"
            url = url.rstrip("&")

        try:
            response = self.session.get(url)
            self._delay()
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException:
            log.exception(f"Error fetching prediction for {query}")
            return {}

    def parse(self, data: list | dict, fields_to_extract: list | dict | None, **kwargs: Any) -> list | dict:
        """Parse the pathway data.

        Args:
            data (Union[List, Dict]): Data to parse.
            fields_to_extract (list|dict): Fields to keep from the original response.
                - If list: Keep those keys.
                - If dict: Maps {desired_name: real_field_name}.
            **kwargs: Additional keyword arguments.

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
