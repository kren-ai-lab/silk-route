"""InterPro API interface."""

from http import HTTPStatus
from typing import Any

import requests

from bioseq_dl.constants.databases import INTERPRO
from bioseq_dl.constants.interpro import db_types, entry_integration_types, filter_types
from bioseq_dl.core.exceptions import ConfigError
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.interpro")

# TODO(diego): add modifiers definitions
# TODO(diego): Because this API uses an unique type of query
# I did not updated the METHODS with fetch()


class InterproInterface(BaseAPIInterface):
    """InterPro protein family database API interface."""

    API_NAME = "InterPro"
    DB_CONFIG = INTERPRO
    METHODS = {
        "entry": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "id": (str, None, True),
                "db": (str, None, True),
                "modifiers": (dict, None, True),
                "filters": (list, None, True),
                "entry_integration": (str, None, True),
                "filter_type": (str, None, True),
                "filter_db": (str, None, True),
                "filter_value": (str, None, True),
            },
            "group_queries": [None],
            "separator": None,
        }
    }

    def validate_query(self, method: str, query: dict) -> None:
        """Validate the query parameters.

        Args:
            method (str): The method to validate against.
            query (dict): The query parameters to validate.

        Raises:
            ConfigError: If the query parameters are invalid.

        """
        rules = {
            "id": lambda v: isinstance(v, str) and v.strip() != "",
            "db": lambda v: v in db_types[method],
            "entry_integration": lambda v: v in entry_integration_types,
            "modifiers": lambda v: isinstance(v, dict),
            # Example of a valid filters:
            # "filters" : [
            #     {  # noqa: ERA001
            #         "type": "protein",  # noqa: ERA001
            #         "db": "reviewed",  # noqa: ERA001
            #         "value": "Q29537"
            #     }  # noqa: ERA001
            # ]  # noqa: ERA001
            "filters": lambda filters: (
                isinstance(filters, list)
                and all(
                    isinstance(f, dict)
                    and all(k in f for k in ("type", "db", "value"))
                    and f["type"] in filter_types
                    and f["type"] != method
                    for f in filters
                )
            ),
        }

        for key, check in rules.items():
            if key in query and not check(query[key]):
                if key == "id":
                    msg = f"Invalid ID: {query['id']}. It should be a non-empty string."
                elif key == "filters":
                    valid = [ftype for ftype in filter_types if ftype != method]
                    msg = f"Invalid filter type: {query[key]}. Valid types are: {valid}"
                elif key == "db":
                    msg = (
                        f"Invalid database type: {query['db']} for method {method}. "
                        f"Valid types are: {db_types[method]}"
                    )
                elif key == "entry_integration":
                    msg = (
                        f"Invalid entry integration type: {query['entry_integration']}. "
                        f"Valid types are: {entry_integration_types}"
                    )
                elif key == "modifiers":
                    msg = (
                        f"Invalid modifiers type: {type(query['modifiers'])}. "
                        "Modifiers should be a dictionary."
                    )
                else:
                    msg = f"Invalid value for '{key}': {query[key]}."
                log.error(msg)
                raise ConfigError(msg)

    def fetch_pages(self, next_url: str, method: str, pages_to_fetch: int = 1) -> dict | list:
        """Fetch the next page of results from the InterPro API.

        Args:
            next_url (str): The URL for the next page of results.
            method (str): The method used for the initial request.
            pages_to_fetch (int): Maximum number of pages to fetch recursively. Default is 1.

        Returns:
            dict: The fetched data from the next page.

        """
        responses = []
        try:
            response = self.session.get(next_url, headers={"Content-Type": "application/json"})
            self._delay()
            response.raise_for_status()

            if response.status_code == HTTPStatus.NO_CONTENT:
                log.warning(f"No content returned for URL {next_url}.")
                return {}

            data = response.json()

            if (
                not isinstance(data, dict)
                and "detail" in data
                and data["detail"].startswith("There is no data associated with the requested URL")
            ):
                return {}

            if "results" in data and isinstance(data["results"], list):
                responses.extend(data["results"])
            else:
                responses.append(data)

            next_page = None
            if data.get("next"):
                next_page = (
                    self.fetch_pages(data["next"], method, pages_to_fetch - 1) if pages_to_fetch > 1 else None
                )
                if next_page:
                    responses.extend(next_page)

        except requests.exceptions.RequestException:
            log.exception(f"Error fetching next page for method {method}")
            return {}
        else:
            return responses

    def fetch(self, query: str | dict | list, *, method: str = "entry", **kwargs: Any) -> dict | list:
        """Fetch data from InterPro API.

        Args:
            query (str|dict|list): The query parameters to fetch data.
            method (str): The method to use for the request.
            **kwargs: Supports `pages_to_fetch` key for pagination depth.

        Returns:
            dict: The fetched data.

        """
        pages_to_fetch = kwargs.get("pages_to_fetch", 1)

        if method not in self.METHODS:
            log.error(f"Method {method} is not supported. Available methods: {list(self.METHODS.keys())}")
            return {}

        if not isinstance(query, dict):
            log.error(
                "Query must be a dictionary containing 'db', 'entry_integration', 'modifiers', "
                "'filter_type', "
                "'filter_db', and 'filter_value' "
                "keys."
            )
            return {}

        # Validate the query parameters
        self.validate_query(method, query)

        # Construct the base URL
        url = f"{INTERPRO.API_URL}{method}/"

        if query.get("db"):
            url += f"{query['db']}/"
        if query.get("id"):
            url += f"{query['id']}/"
        if query.get("entry_integration"):
            url += f"{query['entry_integration']}/"
        if "filters" in query and isinstance(query["filters"], list):
            for f in query["filters"]:
                if f["type"] in filter_types and f["db"] in db_types[f["type"]] and f["value"]:
                    url += f"{f['type']}/{f['db']}/{f['value']}/"
                else:
                    log.error(
                        f"Invalid filter: {f}. Valid filters are of type {filter_types} with databases "
                        f"{db_types[f['type']]}."
                    )
                    return {}

        if query.get("modifiers"):
            url += "?"
            for key, value in query["modifiers"].items():
                if value is not None and value != "":
                    url += f"{key}={value}&"
            # remove the last '&'
            url = url[:-1]

        log.debug(f"Prepared url: {url}")
        return self.fetch_pages(url, method, pages_to_fetch)

    def parse(self, data: Any, fields_to_extract: list | dict | None, **kwargs: Any) -> dict | list:
        """Parse the fetched data.

        Args:
            data (dict): The fetched data.
            fields_to_extract (List|Dict): Fields to keep from the original response.
                - If List: Keep those keys.
                - If Dict: Maps {desired_name: real_field_name}.
            **kwargs: Additional keyword arguments.

        Returns:
            dict: The parsed data.

        """
        if not isinstance(data, (list, dict)):
            log.error(
                "Tried to parse data but the type is not supported. Response should be a dict or a list."
            )
            return {}
        if (isinstance(data, dict) and not data) or (isinstance(data, list) and not data):
            return {}

        return self._extract_fields(data, fields_to_extract)
