"""Gene Ontology API interface."""

from http import HTTPStatus
from typing import Any, ClassVar

import niquests
from niquests import Request

from bioseq_dl.constants.databases import GENONTOLOGY
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

    def _build_request(
        self, *, method: str, http_method: str, validated_params: dict, **kwargs: Any
    ) -> Request:
        """Build the GenOntology request URL (uppercased GO ids in the path + option suffix)."""
        url = f"{GENONTOLOGY.API_URL}{method.replace('-', '/')}/"
        for value in validated_params.values():
            url += f"{value.upper().replace(':', '%3A')}"

        option = kwargs.get("option")
        if option and option != "default":
            url += f"/{option}"

        return Request(url=url, method=http_method)

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
