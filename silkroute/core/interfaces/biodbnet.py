"""BioDBNet API interface."""

from typing import Any, ClassVar

from niquests import Request

from silkroute.constants.databases import BIODBNET

from .base import BaseAPIInterface


class BioDBNetInterface(BaseAPIInterface):
    """BioDBNet biological database network API interface."""

    API_NAME = "BioDBNet"
    DB_CONFIG = BIODBNET
    METHODS: ClassVar[dict[str, Any]] = {
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

    def _build_request(
        self, *, method: str, http_method: str, validated_params: dict, **_kwargs: Any
    ) -> Request:
        """Build the BioDBNet request.

        BioDBNet exposes a single REST endpoint and selects the operation via the
        ``method`` query parameter (rather than a path segment), so the URL is
        fixed and ``method`` is injected into the params.
        """
        return Request(
            method=http_method,
            url=BIODBNET.API_URL,
            params={**validated_params, "method": method},
        )

    def _unwrap_response(self, data: Any, **kwargs: Any) -> Any:
        """Extract result rows for ``db2db`` (each input id maps to an ``outputs`` dict)."""
        if kwargs.get("method") == "db2db" and isinstance(data, dict):
            return [v["outputs"] for v in data.values() if isinstance(v, dict) and "outputs" in v]
        return data
