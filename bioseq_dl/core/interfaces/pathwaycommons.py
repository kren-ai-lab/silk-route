"""PathwayCommons API interface."""

import json
from typing import Any, ClassVar

from niquests import Request

# Add the import for your database in constants
from bioseq_dl.constants.databases import PATHWAYCOMMONS
from bioseq_dl.constants.pathwaycommons import OUTPUT_FORMATS, PATTERNS
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.pathwaycommons")


class PathwayCommonsInterface(BaseAPIInterface):
    """PathwayCommons biological pathway data API interface."""

    API_NAME = "PathwayCommons"
    DB_CONFIG = PATHWAYCOMMONS
    METHODS: ClassVar[dict[str, Any]] = {
        "fetch": {
            "http_method": "POST",
            "path_param": None,
            "parameters": {
                "uri": (list, None, True),
                "format": (str, "jsonld", True),
                "pattern": (list, ["interacts-with"], True),
                "subpw": (bool, False, True),
            },
            "group_queries": [None],
            "separator": None,
        },
        "top_pathways": {
            "http_method": "POST",
            "path_param": None,
            "parameters": {
                "q": (str, None, True),
                "organism": (list, None, True),
                "datasource": (list, None, True),
            },
            "group_queries": [None],
            "separator": None,
        },
        "neighborhood": {
            "http_method": "POST",
            "path_param": None,
            "parameters": {
                "source": (list, None, True),
                "limit": (int, 1, True),
                "format": (str, "jsonld", True),
                "organism": (list, None, True),
                "datasource": (list, None, True),
                "pattern": (list, ["interacts-with"], True),
                "subpw": (bool, False, True),
                "direction": (str, "undirected", True),
            },
            "group_queries": [None],
            "separator": None,
        },
    }

    # Per-method required parameter (raises ValueError when missing).
    _REQUIRED_PARAM: ClassVar[dict[str, str]] = {
        "fetch": "uri",
        "top_pathways": "q",
        "neighborhood": "source",
    }

    def _build_request(
        self, *, method: str, http_method: str, validated_params: dict, **_kwargs: Any
    ) -> Request:
        """Build the PathwayCommons POST request (JSON body), validating params."""
        required = self._REQUIRED_PARAM.get(method)
        if required and not validated_params.get(required):
            msg = f"The '{required}' parameter is required for the '{method}' method."
            raise ValueError(msg)

        if "format" in validated_params and validated_params["format"] not in OUTPUT_FORMATS:
            msg = f"Invalid format '{validated_params['format']}'. Allowed formats: {OUTPUT_FORMATS}"
            raise ValueError(msg)
        if "pattern" in validated_params and any(p not in PATTERNS for p in validated_params["pattern"]):
            msg = f"Invalid pattern '{validated_params['pattern']}'. Allowed patterns: {PATTERNS}"
            raise ValueError(msg)

        url = f"{PATHWAYCOMMONS.API_URL}{method}"
        headers = {"accept": "*/*", "Content-Type": "application/json"}
        return Request(url=url, headers=headers, method=http_method, data=json.dumps(validated_params))

    def _unwrap_response(self, data: Any, **_kwargs: Any) -> Any:
        """Unwrap the ``searchHit`` / JSON-LD ``@graph`` envelope when present."""
        if isinstance(data, dict):
            if "searchHit" in data:
                return data["searchHit"]
            if "@graph" in data:
                return data["@graph"]
        return data
