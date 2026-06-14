from typing import Any

import pandas as pd
import requests
from requests import Request
from requests.exceptions import RequestException

from bioseq_dl.constants.databases import GENONTOLOGY
from bioseq_dl.core.utils.base_auxiliary_methods import validate_parameters
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.genontology")


class GenOntologyInterface(BaseAPIInterface):
    API_NAME = "GenOntology"
    DB_CONFIG = GENONTOLOGY
    METHODS = {
        "ontology-term": {
            "default": {
                "http_method": "GET",
                "path_param": None,
                "parameters": {
                    "goid": (str, None, True),
                },
                "group_queries": [None],
                "separator": None,
            },
            "graph": {
                "http_method": "GET",
                "path_param": None,
                "parameters": {
                    "goid": (str, None, True),
                },
                "group_queries": [None],
                "separator": None,
            },
        },
        "go": {
            "default": {
                "http_method": "GET",
                "path_param": None,
                "parameters": {
                    "goid": (str, None, True),
                },
                "group_queries": [None],
                "separator": None,
            }
        },
        "bioentity-function": {
            "default": {
                "http_method": "GET",
                "path_param": None,
                "parameters": {
                    "goid": (str, None, True),
                },
                "group_queries": [None],
                "separator": None,
            }
        },
    }

    def fetch(self, query: str | dict | list, *, method: str = "ontology-term", **kwargs):
        """Fetch data from the GenOntology API.

        Args:
            query (str): Query string to search for.
            method (str): Method to use for the request. Used methods are 'ontology-term' and 'go'.
            **kwargs: Additional parameters for the request.
            - `option`: Additional options for the request.

        Returns:
            any: response from the API.

        """
        if method not in self.METHODS.keys():
            log.error(f"Method {method} is not supported. Available methods: {list(self.METHODS.keys())}")
            return {}

        option = kwargs.pop("option", "default")

        http_method, _, parameters, inputs = self.initialize_method_parameters(
            query, method, self.METHODS, option=option, **kwargs
        )

        # Validate and clean parameters
        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError:
            log.exception(f"Invalid parameters for method '{method}'")
            return {}

        url = f"{GENONTOLOGY.API_URL}{method.replace('-', '/')}/"
        for param in validated_params:
            if param in validated_params:
                url += f"{validated_params[param].upper().replace(':', '%3A')}"

        if option and option != "default":
            url += f"/{option}"

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
        except RequestException:
            log.exception(f"Error fetching data from {url}")
            return {}

    def parse(self, data: Any, fields_to_extract: list | dict | None, **kwargs) -> dict | list:
        """Parse the response from the GenOntology API.

        Args:
            data (Any): Raw data from the API response.
            fields_to_extract (List|Dict): Fields to keep from the original response.
                - If List: Keep those keys.
                - If Dict: Maps {desired_name: real_field_name}.
            **kwargs: Additional parameters for parsing.
            - `look_for_relationships`: If True, fetch related ontology terms.

        Returns:
            dict: Parsed response.

        """
        look_for_relationships = kwargs.get("look_for_relationships")
        if not data:
            log.warning("Tried to parse data but the data is empty or None.")
            return {}

        if isinstance(data, requests.models.Response):
            data = data.json()
        elif not isinstance(data, dict):
            log.error(
                "Tried to parse data but the type is not supported. Response should be a dict or a requests.Response object."
            )
            return {}

        parsed = self._extract_fields(data, fields_to_extract)

        if look_for_relationships:
            if isinstance(parsed, list):
                parsed = [self.fetch_related_ontology_terms(item) for item in parsed]
            else:
                parsed = self.fetch_related_ontology_terms(parsed)

        return parsed

    def fetch_related_ontology_terms(self, parsed: dict) -> dict:
        """Fetch related ontology terms for a given ontology term.

        Args:
            parsed (dict): Parsed ontology term data.

        Returns:
            dict: Updated parsed data with relationships.

        """
        try:
            rel_response = self.fetch(method="ontology-term", query=parsed.get("goid", ""), option="graph")
            if isinstance(rel_response, requests.models.Response) and rel_response.status_code == 200:
                graph_json = rel_response.json()
                nodes = graph_json.get("topology_graph_json", {}).get("nodes", [])
                relationships = [node.get("id") for node in nodes if "id" in node]
                parsed["relationships"] = relationships
            else:
                parsed["relationships"] = []
        except Exception:
            log.exception(f"Error fetching relationships for GO term {parsed.get('goid', '')}")
        return parsed

    def fetch_single(
        self, query: str | dict, parse: bool = False, *args, **kwargs
    ) -> list | dict | pd.DataFrame:
        option = kwargs.pop("option", "default")
        return super().fetch_single(*args, query=query, parse=parse, option=option, **kwargs)

    def fetch_batch(
        self, queries: list[str | dict], parse: bool = False, *args, **kwargs
    ) -> list | pd.DataFrame:
        option = kwargs.pop("option", "default")
        return super().fetch_batch(*args, queries=queries, parse=parse, option=option, **kwargs)
