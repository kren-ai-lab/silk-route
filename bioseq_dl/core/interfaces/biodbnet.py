"""BioDBNet API interface."""

from typing import Any

from requests import Request
from requests.exceptions import RequestException

from bioseq_dl.constants.databases import BIODBNET
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.biodbnet")


class BioDBNetInterface(BaseAPIInterface):
    """BioDBNet biological database network API interface."""

    API_NAME = "BioDBNet"
    DB_CONFIG = BIODBNET
    METHODS = {
        "getpathways": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {"pathways": (str, "1", True), "taxonId": (str, None, True)},
            "group_queries": [None],
            "separator": None,
        },
        "db2db": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "input": (str, None, True),
                "inputValues": (str, None, True),
                "outputs": (
                    str,
                    "genesymbol,affyid,go-biologicalprocess,go-cellularcomponent,go-molecularfunction,goid",
                    True,
                ),
                "taxonId": (str, None, True),
            },
            "group_queries": ["inputValues"],
            "separator": ",",
        },
    }

    def fetch(self, query: str | dict | list, *, method: str = "getpathways", **kwargs: Any) -> dict | list:
        """Fetch data from BioDBNet for the given query."""
        if method not in self.METHODS:
            log.error(f"Method {method} is not supported. Available methods: {list(self.METHODS.keys())}")
            return {}

        http_method, _, _parameters, inputs = self.initialize_method_parameters(
            query, method, self.METHODS, **kwargs
        )

        inputs.update({"method": method})

        inputs["outputs"] = (
            ",".join(inputs.get("outputs", []))
            if isinstance(inputs.get("outputs"), list)
            else inputs.get("outputs", "")
        )

        req = Request(method=http_method, url=BIODBNET.API_URL, params=inputs)
        prepared = self.session.prepare_request(req)
        log.debug(f"Prepared request: {prepared.url}")

        try:
            response = self.session.send(prepared)
            self._delay()
            response.raise_for_status()

            match method:
                case "db2db":
                    response = response.json()
                    return [
                        v["outputs"] for k, v in response.items() if isinstance(v, dict) and k not in inputs
                    ]
                case _:
                    return response.json()
        except RequestException:
            log.exception(f"Error fetching {query} for method '{method}'")
            return {}

    def parse(self, data: list | dict, fields_to_extract: list | dict | None, **kwargs: Any) -> list | dict:
        """Parse BioDBNet response data."""
        if not data:
            log.warning("Tried to parse data but the data is empty or None.")
            return {}

        if not isinstance(data, (dict, list)):
            log.error(
                "Tried to parse data but the type is not supported. Response should be a dict or a "
                "requests.Response "
                "object."
            )
            return {}

        return self._extract_fields(data, fields_to_extract)
