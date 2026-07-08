"""Shared fixtures for the BioSeqDownloader test suite.

Tests run offline. The library uses `niquests` as its HTTP client, so HTTP is
mocked with `niquests-mock`, which patches `niquests` natively and exposes the
`niquests_mock` fixture (a `MockRouter`). Tests register routes with
`niquests_mock.get(...).respond(...)` and introspect traffic via
`niquests_mock.calls`.
"""

from __future__ import annotations
