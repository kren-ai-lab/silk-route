"""Shared cache + HTTP-error contract for the HTTP-based interface clients.

Every client inherits the same caching and error behaviour from
``BaseAPIInterface``, so the two tests that exercise it were copied byte-for-byte
into each per-database test module. The bodies now live here once: a per-database
test class sets the knobs (``INTERFACE_URL``/``QUERY``/``METHOD``/``FIXTURE`` …)
and provides the module-level ``interface`` fixture; pytest collects the
inherited test methods under that class.

Mix in only what a client actually has — most use both, but BioGRID and ChEMBL
have no error test, so they inherit ``CachingContract`` alone.
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest
from niquests_mock import startswith

from silkroute.core.exceptions import RequestError
from tests._helpers import load_fixture


class _Contract:
    # --- per-database knobs (set on the subclass) ---------------------------
    INTERFACE_URL: ClassVar[str]
    QUERY: ClassVar[Any]
    METHOD: ClassVar[str]
    FIXTURE: ClassVar[tuple[str, str]]  # (api, case) passed to load_fixture
    HTTP_METHOD: ClassVar[str] = "get"  # "get" | "post"
    BODY_IS_TEXT: ClassVar[bool] = False  # KEGG / SABIO-RK return raw text
    CALL_KWARGS: ClassVar[dict[str, Any]] = {}  # extra fetch kwargs, e.g. option=

    def _route(self, niquests_mock):
        return getattr(niquests_mock, self.HTTP_METHOD)(url=startswith(self.INTERFACE_URL))


class CachingContract(_Contract):
    """A second identical ``fetch_single`` is served from cache, not the network."""

    def test_fetch_single_round_trips_through_cache(self, interface, niquests_mock):
        body = load_fixture(*self.FIXTURE)
        kw = {"text": body} if self.BODY_IS_TEXT else {"json": body}
        self._route(niquests_mock).respond(status_code=200, **kw)

        first, _ = interface.fetch_single(self.QUERY, method=self.METHOD, **self.CALL_KWARGS)
        second, _ = interface.fetch_single(self.QUERY, method=self.METHOD, **self.CALL_KWARGS)

        assert len(niquests_mock.calls) == 1
        assert first == second


class HttpErrorContract(_Contract):
    """``fetch`` on a 5xx either raises ``RequestError`` or returns an empty value."""

    ERROR_RETURNS_EMPTY: ClassVar[bool] = False  # True => returns ERROR_EMPTY_VALUE, else raises
    ERROR_EMPTY_VALUE: ClassVar[Any] = {}  # the empty value returned on error when ERROR_RETURNS_EMPTY

    def test_fetch_handles_http_error(self, interface, niquests_mock):
        kw = {"text": "boom"} if self.BODY_IS_TEXT else {"json": {"error": "boom"}}
        self._route(niquests_mock).respond(status_code=500, **kw)

        if self.ERROR_RETURNS_EMPTY:
            assert (
                interface.fetch(self.QUERY, method=self.METHOD, **self.CALL_KWARGS) == self.ERROR_EMPTY_VALUE
            )
        else:
            with pytest.raises(RequestError):
                interface.fetch(self.QUERY, method=self.METHOD, **self.CALL_KWARGS)
