"""PANTHER API interface."""

from typing import Any

from requests import Request
from requests.exceptions import RequestException
from requests.models import Response

# Add the import for your database in constants
from bioseq_dl.constants.databases import PANTHER
from bioseq_dl.core.utils.base_auxiliary_methods import validate_parameters
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.panther")


class PantherInterface(BaseAPIInterface):
    """PANTHER gene family annotation and ontology API interface."""

    API_NAME = "PANTHER"
    DB_CONFIG = PANTHER
    # Definition of methods for PANTHER API
    # Each parameter is a tuple with (type, default_value, primary_key)
    METHODS = {
        "geneinfo": {
            "http_method": "POST",
            "path_param": None,
            "parameters": {
                "geneInputList": (str, None, True),
                "organism": (str, None, True),
            },
            "group_queries": ["geneInputList"],
            "separator": ",",
        },
        "familyortholog": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {"family": (str, None, True), "taxonFltr": (str, None, False)},
            "group_queries": ["taxonFltr"],
            "separator": ",",
        },
        "familymsa": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {"family": (str, None, True), "taxonFltr": (str, None, False)},
            "group_queries": ["taxonFltr"],
            "separator": ",",
        },
    }

    def fetch(self, query: str | dict | list, *, method: str = "geneinfo", **kwargs: Any) -> dict | list:
        """Fetch gene family or MSA data from PANTHER."""
        http_method, path_param, parameters, inputs = self.initialize_method_parameters(
            query, method, self.METHODS, **kwargs
        )

        # Validate and clean parameters
        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError:
            log.exception(f"Invalid parameters for method '{method}'")
            return {}

        url = f"{PANTHER.API_URL}{method}"

        if path_param:
            path_value = validated_params.pop(path_param)
            url += f"{path_value}"

        req = Request(method=http_method, url=url, params=validated_params)
        prepared = self.session.prepare_request(req)
        log.debug(f"Prepared request: {prepared.url}")

        try:
            response = self.session.send(prepared)
            self._delay()
            response.raise_for_status()

            match method:
                case "geneinfo":
                    response = response.json()
                    response = response.get("search", {}).get("mapped_genes", {}).get("gene", [])
                case "familyortholog":
                    response = response.json()
                    response = response.get("search", {}).get("ortholog_list", {}).get("ortholog", [])
                case "familymsa":
                    response = response.json()
                    response = response.get("search", {}).get("MSA_list", {}).get("sequence_info", [])
                case _:
                    response = response.json()

        except RequestException:
            log.exception(f"Error fetching {query} for method '{method}'")
            return {}
        else:
            return response

    def parse(self, data: list | dict, fields_to_extract: list | dict | None, **kwargs: Any) -> list | dict:
        """Parse PANTHER response data."""
        if not data:
            log.warning("Tried to parse data but the data is empty or None.")
            return {}

        if isinstance(data, Response):
            data = data.json()
        elif not isinstance(data, dict):
            log.error(
                "Tried to parse data but the type is not supported. Response should be a dict or a requests.Response object."
            )
            return {}

        return self._extract_fields(data, fields_to_extract)
