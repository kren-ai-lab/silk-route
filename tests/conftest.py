"""Shared fixtures for the BioSeqDownloader test suite.

Tests run offline. HTTP is mocked behind these fixtures so the rest of the suite
never touches the network. Keeping the mock isolated here means a future migration
of the HTTP client (requests -> niquests) only has to touch this file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import responses

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def mocked_responses() -> Iterator[responses.RequestsMock]:
    """Activate `responses` for a test, asserting all registered mocks are used."""
    with responses.RequestsMock() as rsps:
        yield rsps
