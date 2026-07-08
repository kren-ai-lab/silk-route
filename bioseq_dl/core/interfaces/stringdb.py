"""STRING protein interaction database API interface."""

from typing import Any, ClassVar

from requests import Request
from requests.exceptions import HTTPError, RequestException

from bioseq_dl.constants.databases import STRING
from bioseq_dl.constants.stringdb import METHOD_FORMATS
from bioseq_dl.core.utils.base_auxiliary_methods import validate_parameters
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.stringdb")

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

    def fetch(
        self, query: str | dict | list, *, method: str = "get_string_ids", **kwargs: Any
    ) -> dict | list:
        """Fetch data from the STRING API.

        Args:
            query (str|dict|list): Query parameters for the API.
            method (str): Method to use for the request.
            **kwargs: Additional keyword arguments passed to the request builder.

        Returns:
            dict: Parsed response from the API.

        """
        if method not in self.METHODS:
            log.error(
                "Method '%s' is not supported. Available methods: %s", method, list(self.METHODS.keys())
            )
            return {}

        http_method, _path_param, parameters, inputs = self.initialize_method_parameters(
            query, method, self.METHODS, **kwargs
        )

        try:
            validated_params = validate_parameters(inputs, parameters)
        except (ValueError, TypeError):
            log.exception("Parameter validation failed")
            return {}

        outfmt = validated_params.pop("format") if "format" in validated_params else "json"

        if outfmt not in METHOD_FORMATS[method]:
            log.error(
                "Output format %s is not supported for method %s. Supported formats are: %s.",
                outfmt,
                method,
                ", ".join(METHOD_FORMATS[method]),
            )
            return {}

        url = f"{STRING.API_URL}{outfmt}/{method}"

        req = Request(method=http_method, url=url, params=validated_params)

        prepared = self.session.prepare_request(req)
        log.debug("Prepared request URL: %s", prepared.url)

        try:
            response = self.session.send(prepared)
            self._delay()
            response.raise_for_status()

            return response.json()
        except HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:  # noqa: PLR2004
                identifier = query.get("identifiers") if isinstance(query, dict) else query
                log.warning("STRING identifier not found for method '%s': %s", method, identifier)
            else:
                log.exception("Error fetching %s for method '%s'", query, method)
            return {}
        except RequestException:
            log.exception("Error fetching %s for method '%s'", query, method)
            return {}

    def parse(self, data: Any, fields_to_extract: list | dict | None, **kwargs: Any) -> Any:
        """Parse the response from the STRING API.

        Args:
            data (Any): Data to parse.
            fields_to_extract (List|Dict): Fields to keep from the original response.
                - If List: Keep those keys.
                - If Dict: Maps {desired_name: real_field_name}
            **kwargs: Supports `fmt` key for response format (default: "json").

        Returns:
            dict: Parsed response.

        """
        fmt = kwargs.get("fmt", "json")
        if not data:
            return {}

        if fmt == "json":
            return self._extract_fields(data, fields_to_extract)

        if fmt == "tsv":
            return data.text
        if fmt == "image":
            log.error(
                "Image format is not supported for parsing. Please use the method save_image() to save the "
                "image."
            )
        else:
            log.error("Format %s is not supported. Supported formats are: json, tsv", fmt)
            return {}
        return None
