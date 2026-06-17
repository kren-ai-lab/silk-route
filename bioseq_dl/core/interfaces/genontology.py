"""Gene Ontology API interface."""

from http import HTTPStatus
from typing import Any, ClassVar

import niquests
from niquests import Request
from niquests.exceptions import RequestException

from bioseq_dl.constants.databases import GENONTOLOGY
from bioseq_dl.core.utils.base_auxiliary_methods import validate_parameters
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.genontology")


class GenOntologyInterface(BaseAPIInterface):
    """Gene Ontology API interface."""

    API_NAME = "GenOntology"
    DB_CONFIG = GENONTOLOGY
    DEFAULT_OPTION: ClassVar[str | None] = "default"
    METHODS: ClassVar[dict[str, Any]] = {
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

    def fetch(self, query: str | dict | list, *, method: str = "ontology-term", **kwargs: Any) -> dict | list:
        """Fetch data from the GenOntology API.

        Args:
            query (str): Query string to search for.
            method (str): Method to use for the request. Used methods are 'ontology-term' and 'go'.
            **kwargs: Additional parameters for the request.
            - `option`: Additional options for the request.

        Returns:
            any: response from the API.

        """
        if method not in self.METHODS:
            log.error("Method %s is not supported. Available methods: %s", method, list(self.METHODS.keys()))
            return {}

        option = kwargs.pop("option", "default")

        http_method, _, parameters, inputs = self.initialize_method_parameters(
            query, method, self.METHODS, option=option, **kwargs
        )

        # Validate and clean parameters
        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError:
            log.exception("Invalid parameters for method '%s'", method)
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
        log.debug("Prepared request: %s", prepared.url)

        try:
            response = self.session.send(prepared)
            self._delay()
            response.raise_for_status()

            return response.json()
        except RequestException:
            log.exception("Error fetching data from %s", url)
            return {}

    def parse(self, data: Any, fields_to_extract: list | dict | None, **kwargs: Any) -> dict | list:
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
        look_for_relationships = kwargs.pop("look_for_relationships", None)

        parsed = super().parse(data, fields_to_extract, **kwargs)

        if look_for_relationships and parsed:
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
            if (
                isinstance(rel_response, niquests.models.Response)
                and rel_response.status_code == HTTPStatus.OK
            ):
                graph_json = rel_response.json()
                nodes = graph_json.get("topology_graph_json", {}).get("nodes", [])
                relationships = [node.get("id") for node in nodes if "id" in node]
                parsed["relationships"] = relationships
            else:
                parsed["relationships"] = []
        except Exception:
            log.exception("Error fetching relationships for GO term %s", parsed.get("goid", ""))
        return parsed
