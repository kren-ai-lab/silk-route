"""Tests for the custom exception hierarchy."""

from __future__ import annotations

import pytest

from silkroute.core.exceptions import (
    APIError,
    ConfigError,
    ParseError,
    RequestError,
    SilkRouteError,
)


@pytest.mark.parametrize("exc", [APIError, RequestError, ParseError, ConfigError])
def test_all_errors_derive_from_silkroute_error(exc):
    assert issubclass(exc, SilkRouteError)


@pytest.mark.parametrize("exc", [RequestError, ParseError, ConfigError])
def test_concrete_errors_derive_from_apierror(exc):
    assert issubclass(exc, APIError)


def test_raisable_and_catchable_as_base():
    with pytest.raises(SilkRouteError):
        raise RequestError("boom")
