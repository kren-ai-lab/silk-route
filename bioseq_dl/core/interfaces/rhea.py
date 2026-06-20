"""Rhea reaction database API interface."""

from typing import Any, ClassVar

# Add the import for your database in constants
from bioseq_dl.constants.databases import RHEA
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.rhea")


class RheaInterface(BaseAPIInterface):
    """Rhea reaction database API interface."""

    API_NAME = "Rhea"
    DB_CONFIG = RHEA
    # Endpoints are ``{method}/{id}``; responses wrap rows in a ``results`` key.
    _METHOD_SUFFIX: ClassVar[str] = "/"
    _RESPONSE_ENVELOPE_KEYS: ClassVar[tuple[str, ...]] = ("results",)
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
