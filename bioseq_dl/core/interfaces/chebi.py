"""ChEBI API interface."""

import json
from typing import Any
from urllib.parse import quote

from requests import Request
from requests.exceptions import RequestException
from requests.models import Response

from bioseq_dl.constants.databases import CHEBI
from bioseq_dl.core.utils.base_auxiliary_methods import validate_parameters
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.chebi")

# Definition of methods for ChEBI API
# Each paramether is a tuple with (type, default_value, primary_key)


class ChEBIInterface(BaseAPIInterface):
    """ChEBI chemical entity database API interface."""

    API_NAME = "ChEBI"
    DB_CONFIG = CHEBI
    METHODS = {
        "compound": {
            "http_method": "GET",
            "path_param": "chebi_id",
            "parameters": {
                "chebi_id": (str, None, True),
                "only_ontology_parents": (bool, False, False),
                "only_ontology_children": (bool, False, False),
            },
            "group_queries": [None],
            "separator": None,
        },
        "compounds": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "chebi_ids": (list, None, True),
            },
            "group_queries": [None],
            "separator": ",",
        },
        "es_search": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "term": (str, None, True),
                "page": (int, 1, False),
                "size": (int, 15, False),
            },
            "group_queries": [None],
            "separator": None,
        },
        "ontology-children": {
            "http_method": "GET",
            "path_param": "chebi_id",
            "parameters": {
                "chebi_id": (str, None, True),
            },
            "group_queries": [None],
            "separator": None,
        },
        "ontology-parents": {
            "http_method": "GET",
            "path_param": "chebi_id",
            "parameters": {
                "chebi_id": (str, None, True),
            },
            "group_queries": [None],
            "separator": None,
        },
    }

    def fetch(self, query: str | dict | list, *, method: str = "compound", **kwargs: Any) -> dict | list:
        """Fetch compound or ontology data from ChEBI."""
        if method not in self.METHODS:
            log.error("Method %s is not supported. Available methods: %s", method, list(self.METHODS.keys()))
            return {}

        http_method, path_param, parameters, inputs = self.initialize_method_parameters(
            query, method, self.METHODS, **kwargs
        )

        try:
            validated_params = validate_parameters(inputs, parameters)
        except (ValueError, TypeError):
            log.exception("Parameter validation failed")
            return {}

        # Get ids if available
        chebi_ids = []
        id_key = next((k for k in ("chebi_id", "chebi_ids") if k in validated_params), None)

        if id_key:
            chebi_ids = validated_params.pop(id_key)
            if isinstance(chebi_ids, str):
                chebi_ids = [chebi_ids]
            elif not isinstance(chebi_ids, list):
                log.error("Expected '%s' to be str or list, got %s", id_key, type(chebi_ids))
                return {}

            validated_params[id_key] = ",".join(chebi_id for chebi_id in chebi_ids)

        # Make URL
        url = f"{CHEBI.API_URL}{method.replace('-', '/')}/"
        if path_param and path_param in validated_params:
            path_value = validated_params.pop(path_param)
            if path_param == "chebi_id":
                path_value = quote(path_value, safe="")
            url += f"{path_value}"

        req = Request(http_method, url, params=validated_params)
        prepared = self.session.prepare_request(req)

        log.debug("Prepared url: %s", prepared.url)
        try:
            response = self.session.send(prepared)
            self._delay()
            response.raise_for_status()
            try:
                response = json.loads(response.text)
            except json.JSONDecodeError:
                log.exception(
                    "Failed to decode JSON response for method '%s' with query '%s'. Response text: %s",
                    method,
                    query,
                    response.text,
                )
                return {}

            # If the keys are the same of the query, return the response directly
            if isinstance(response, dict) and set(response.keys()) <= set(chebi_ids):
                # Convert to list of interactions
                response = list(response.values())

            if isinstance(response, dict) and "results" in response:
                response = response["results"]

        except RequestException:
            log.exception("Error fetching %s for method '%s'", query, method)
            return {}
        else:
            return response

    def parse(self, data: list | dict, fields_to_extract: list | dict | None, **_kwargs: Any) -> list | dict:
        """Parse ChEBI response data."""
        if not data:
            log.warning("Tried to parse data but the data is empty or None.")
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

        return self._extract_fields(data, fields_to_extract)
