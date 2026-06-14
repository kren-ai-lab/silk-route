"""PRIDE Archive API interface."""

from typing import Any

import pandas as pd
from requests import Request, Response
from requests.exceptions import RequestException

# Add the import for your database in constants
from bioseq_dl.constants.databases import PRIDE
from bioseq_dl.core.utils.base_auxiliary_methods import validate_parameters
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.pride")


class PrideInterface(BaseAPIInterface):
    """PRIDE proteomics data archive API interface."""

    API_NAME = "PRIDE"
    DB_CONFIG = PRIDE
    METHODS = {
        "search": {
            "projects": {
                "http_method": "GET",
                "path_param": None,
                "parameters": {
                    "keyword": (str, None, True),
                    "filter": (str, None, True),
                    "page": (int, 0, True),
                    "dateGap": (str, None, True),
                    "sortDirection": (str, "DESC", False),
                    "sortFields": (str, "submissionDate", False),
                },
                "group_queries": [None],
                "separator": None,
            },
        },
        "projects": {
            "default": {
                "http_method": "GET",
                "path_param": ["projectAccession"],
                "parameters": {
                    "projectAccession": (str, None, True),
                },
                "group_queries": [None],
                "separator": None,
            },
            "similarProjects": {
                "http_method": "GET",
                "path_param": ["accession"],
                "parameters": {
                    "accession": (str, None, True),
                    "page": (int, 0, True),
                    "pageSize": (int, 10, True),
                },
                "group_queries": [None],
                "separator": None,
            },
        },
    }

    def fetch(self, query: str | dict | list, *, method: str = "search", **kwargs: Any) -> dict | list:
        """Fetch proteomics data from PRIDE Archive."""
        if method not in self.METHODS:
            log.error("Method '%s' is not defined in the interface.", method)
            return {}
        option = kwargs.pop("option", "default")

        http_method, path_param, parameters, inputs = self.initialize_method_parameters(
            query, method, self.METHODS, option=option, **kwargs
        )

        # Validate and clean parameters
        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError:
            log.exception("Invalid parameters for method '%s'", method)
            return {}

        url = f"{PRIDE.API_URL}{method.replace('-', '/')}"

        if path_param:
            if isinstance(path_param, list):
                url += "/" + "/".join(
                    str(validated_params.pop(param)) for param in path_param if param in validated_params
                )
            else:
                url += f"/{validated_params.pop(path_param)}"

        if option and option != "default":
            url += f"/{option}"

        response = Request(
            url=url,
            method=http_method,
            params=validated_params,
        )

        prepared = self.session.prepare_request(response)
        log.debug("Prepared request: %s", prepared.url)

        try:
            response = self.session.send(prepared)
            self._delay()
            response.raise_for_status()

            return response.json()
        except RequestException:
            log.exception("Error fetching data from %s", url)
            return {}

    def parse(self, data: list | dict, fields_to_extract: list | dict | None, **kwargs: Any) -> list | dict:
        """Parse PRIDE Archive response data."""
        if not data:
            return {}

        if isinstance(data, Response):
            data = data.json()
        elif not isinstance(data, dict):
            log.error(
                "Tried to parse data but the type is not supported. Response should be a dict or a "
                "requests.Response "
                "object."
            )
            return {}

        return self._extract_fields(data, fields_to_extract, **kwargs)

    def fetch_single(
        self, query: str | dict, parse: bool = False, *args: Any, **kwargs: Any
    ) -> list | dict | pd.DataFrame:
        """Fetch a single PRIDE record."""
        option = kwargs.pop("option", "default")
        return super().fetch_single(*args, query=query, parse=parse, option=option, **kwargs)
