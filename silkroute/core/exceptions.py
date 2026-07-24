"""Custom exception hierarchy for SilkRoute.

A small, roxy-style hierarchy so callers can distinguish *why* a fetch failed
instead of relying on silent ``return {}``:

    SilkRouteError
    └── APIError
        ├── RequestError   (network / HTTP failure)
        ├── ParseError     (response could not be parsed / unexpected shape)
        └── ConfigError    (invalid query / configuration)
"""

from __future__ import annotations


class SilkRouteError(Exception):
    """Base class for all SilkRoute-specific errors."""


class APIError(SilkRouteError):
    """Base class for errors raised while talking to an external API."""


class RequestError(APIError):
    """A network or HTTP request to an API failed."""


class ParseError(APIError):
    """An API response could not be parsed or had an unexpected shape."""


class ConfigError(APIError):
    """A query or configuration was invalid."""


__all__ = [
    "APIError",
    "ConfigError",
    "ParseError",
    "RequestError",
    "SilkRouteError",
]
