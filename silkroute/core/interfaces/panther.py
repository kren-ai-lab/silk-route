"""PANTHER API interface."""

from typing import Any, ClassVar

# Add the import for your database in constants
from silkroute.constants.databases import PANTHER
from silkroute.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("silkroute.interfaces.panther")


class PantherInterface(BaseAPIInterface):
    """PANTHER gene family annotation and ontology API interface."""

    API_NAME = "PANTHER"
    DB_CONFIG = PANTHER
    # Definition of methods for PANTHER API
    # Each parameter is a tuple with (type, default_value, primary_key)
    METHODS: ClassVar[dict[str, Any]] = {
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

    def _unwrap_response(self, data: Any, **kwargs: Any) -> Any:
        """Drill into the per-method nested value PANTHER wraps results in."""
        match kwargs.get("method"):
            case "geneinfo":
                return data.get("search", {}).get("mapped_genes", {}).get("gene", [])
            case "familyortholog":
                return data.get("search", {}).get("ortholog_list", {}).get("ortholog", [])
            case "familymsa":
                return data.get("search", {}).get("MSA_list", {}).get("sequence_info", [])
            case _:
                return data
