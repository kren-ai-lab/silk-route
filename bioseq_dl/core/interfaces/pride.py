"""PRIDE Archive API interface."""

from typing import Any, ClassVar

from niquests import Request

# Add the import for your database in constants
from bioseq_dl.constants.databases import PRIDE
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.pride")


class PrideInterface(BaseAPIInterface):
    """PRIDE proteomics data archive API interface."""

    API_NAME = "PRIDE"
    DB_CONFIG = PRIDE
    DEFAULT_OPTION: ClassVar[str | None] = "default"
    METHODS: ClassVar[dict[str, Any]] = {
        "search": {
            "projects": {
                "http_method": "GET",
                "path_param": None,
                "parameters": {
                    "keyword": (str, None, True),
                    "filter": (str, None, True),
                    "page": (int, 0, True),
                    "dateGap": (str, None, True),
                    "sortDirection": (str, "DESC", False),
                    "sortFields": (str, "submissionDate", False),
                },
                "group_queries": [None],
                "separator": None,
            },
        },
        "projects": {
            "default": {
                "http_method": "GET",
                "path_param": ["projectAccession"],
                "parameters": {
                    "projectAccession": (str, None, True),
                },
                "group_queries": [None],
                "separator": None,
            },
            "similarProjects": {
                "http_method": "GET",
                "path_param": ["accession"],
                "parameters": {
                    "accession": (str, None, True),
                    "page": (int, 0, True),
                    "pageSize": (int, 10, True),
                },
                "group_queries": [None],
                "separator": None,
            },
        },
    }

    def _build_request(
        self, *, method: str, http_method: str, path_param: Any, validated_params: dict, **kwargs: Any
    ) -> Request:
        """Build the PRIDE request URL (path segments + optional option suffix)."""
        url = f"{PRIDE.API_URL}{method.replace('-', '/')}"

        if path_param:
            if isinstance(path_param, list):
                url += "/" + "/".join(
                    str(validated_params.pop(param)) for param in path_param if param in validated_params
                )
            else:
                url += f"/{validated_params.pop(path_param)}"

        option = kwargs.get("option")
        if option and option != "default":
            url += f"/{option}"

        return Request(url=url, method=http_method, params=validated_params)
