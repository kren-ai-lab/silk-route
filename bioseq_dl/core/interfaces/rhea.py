"""Rhea reaction database API interface."""

from typing import Any, ClassVar

from niquests import Request

# Add the import for your database in constants
from bioseq_dl.constants.databases import RHEA
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.rhea")


class RheaInterface(BaseAPIInterface):
    """Rhea reaction database API interface."""

    API_NAME = "Rhea"
    DB_CONFIG = RHEA
    METHODS: ClassVar[dict[str, Any]] = {
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

    def _build_request(
        self, *, method: str, http_method: str, path_param: Any, validated_params: dict, **_kwargs: Any
    ) -> Request:
        """Build the Rhea request URL (`{method}/` + optional path param)."""
        url = f"{RHEA.API_URL}{method}/"
        if path_param:
            url += f"{validated_params.pop(path_param)}"
        return Request(method=http_method, url=url, params=validated_params)

    def _unwrap_response(self, data: Any, **_kwargs: Any) -> Any:
        """Unwrap the ``results`` envelope when present."""
        if isinstance(data, dict) and "results" in data:
            return data["results"]
        return data
