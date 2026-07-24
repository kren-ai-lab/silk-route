"""STRING protein interaction database API interface."""

from typing import Any, ClassVar

from niquests import Request

from silkroute.constants.databases import STRING
from silkroute.constants.stringdb import METHOD_FORMATS
from silkroute.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("silkroute.interfaces.stringdb")

## More info about STRING API: https://string-db.org/cgi/help


class StringInterface(BaseAPIInterface):
    """STRING protein-protein interaction database API interface."""

    API_NAME = "STRING"
    DB_CONFIG = STRING
    METHODS: ClassVar[dict[str, Any]] = {
        "get_string_ids": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "identifiers": (str, None, True),
                "species": (int, None, False),
                "echo_query": (int, 0, False),
                "format": (str, "json", False),
            },
            "group_queries": ["identifiers", "species"],
            "separator": "%0d",
        },
        "interaction_partners": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "identifiers": (str, None, True),
                "species": (int, None, False),
                "limit": (int, None, False),
                "required_score": (int, None, False),
                "network_type": (str, "functional", False),
            },
            "group_queries": ["identifiers", "species"],
            "separator": "%0d",
        },
        # Add other methods as needed
    }

    def _build_request(
        self, *, method: str, http_method: str, validated_params: dict, **_kwargs: Any
    ) -> Request:
        """Build the STRING request URL (`{format}/{method}`), validating the format."""
        outfmt = validated_params.pop("format", "json")

        if outfmt not in METHOD_FORMATS[method]:
            msg = (
                f"Output format {outfmt} is not supported for method {method}. "
                f"Supported formats are: {', '.join(METHOD_FORMATS[method])}."
            )
            raise ValueError(msg)

        url = f"{STRING.API_URL}{outfmt}/{method}"
        return Request(method=http_method, url=url, params=validated_params)

    def parse(self, data: Any, fields_to_extract: list | dict | None, **kwargs: Any) -> Any:
        """Parse the response from the STRING API.

        Args:
            data (Any): Data to parse.
            fields_to_extract (list | dict | None): Fields to keep from the original response.
                - If list: keep those keys.
                - If dict: maps ``{desired_name: real_field_name}``.
            **kwargs: Supports ``fmt`` key for response format (default: "json").

        Returns:
            dict | str | None: Parsed response (JSON dict, TSV text, or None for image).

        """
        fmt = kwargs.pop("fmt", "json")
        if not data:
            return {}

        if fmt == "json":
            return super().parse(data, fields_to_extract, **kwargs)

        if fmt == "tsv":
            return data.text
        if fmt == "image":
            log.error(
                "Image format is not supported for parsing. Please use the method save_image() to save the "
                "image."
            )
            return None

        log.error("Format %s is not supported. Supported formats are: json, tsv", fmt)
        return {}
