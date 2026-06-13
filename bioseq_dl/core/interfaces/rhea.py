from requests import Request
from requests.exceptions import RequestException
from requests.models import Response

# Add the import for your database in constants
from bioseq_dl.constants.databases import RHEA
from bioseq_dl.core.utils.base_auxiliary_methods import validate_parameters
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.rhea")


class RheaInterface(BaseAPIInterface):
    API_NAME = "Rhea"
    DB_CONFIG = RHEA
    METHODS = {
        "rhea": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "query": (str, None, True),
                "columns": (str, "rhea-id,equation,chebi,chebi-id,ec,uniprot,go", False),
                "format": (str, "json", False),
                "limit": (int, 100, False),
            },
            "group_queries": [None],
            "separator": None,
        }
    }

    def fetch(self, query: str | dict | list, *, method: str = "rhea", **kwargs):
        if method not in self.METHODS.keys():
            log.error(f"Method '{method}' is not supported. Available methods: {list(self.METHODS.keys())}")
            return {}

        http_method, path_param, parameters, inputs = self.initialize_method_parameters(
            query, method, self.METHODS, **kwargs
        )

        # Validate and clean parameters
        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError as e:
            log.error(f"Invalid parameters for method '{method}': {e}")
            return {}

        url = f"{RHEA.API_URL}{method}/"
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
            response = response.json()

            if "results" in response:
                response = response["results"]

            return response
        except RequestException as e:
            log.error(f"Error fetching prediction for {query}: {e}")
            return {}

    def parse(self, data: list | dict, fields_to_extract: list | dict | None, **kwargs) -> list | dict:
        if not data:
            return {}

        if isinstance(data, Response):
            data = data.json()
        elif isinstance(data, (dict, list)):
            data = data
        else:
            log.error(
                "Tried to parse data but the type is not supported. Data should be a list or a dictionary."
            )
            return {}

        return self._extract_fields(data, fields_to_extract, **kwargs)
