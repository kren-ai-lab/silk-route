"""Tests for the custom exception hierarchy."""

from __future__ import annotations

import pytest

from bioseq_dl.core.exceptions import (
    APIError,
    BioSeqDlError,
    ConfigError,
    ParseError,
    RequestError,
)


@pytest.mark.parametrize("exc", [APIError, RequestError, ParseError, ConfigError])
def test_all_errors_derive_from_bioseqerror(exc):
    assert issubclass(exc, BioSeqDlError)


@pytest.mark.parametrize("exc", [RequestError, ParseError, ConfigError])
def test_concrete_errors_derive_from_apierror(exc):
    assert issubclass(exc, APIError)


def test_raisable_and_catchable_as_base():
    with pytest.raises(BioSeqDlError):
        raise RequestError("boom")
