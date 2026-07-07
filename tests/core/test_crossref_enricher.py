"""Tests for cross-reference interface construction defaults."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bioseq_dl.core.crossref_enricher import (
    CrossRefEnricher,
    get_crossref_interface_kwargs,
)
from bioseq_dl.core.interfaces.alphafold import AlphafoldInterface
from bioseq_dl.core.utils.query_builders import INTERFACE_CLASSES

if TYPE_CHECKING:
    import pytest


class StubAlphafoldInterface(AlphafoldInterface):
    """Capture AlphaFold constructor values without creating output directories."""

    def __init__(self, structures: list[str] | None = None, **kwargs: object) -> None:
        """Store the constructor values supplied by CrossRefEnricher."""
        self.structures = structures
        self.constructor_kwargs = kwargs


def test_crossref_alphafold_interface_enables_pdb_downloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(INTERFACE_CLASSES, "alphafold", StubAlphafoldInterface)
    enricher = CrossRefEnricher(max_workers=2, total_retries=4)

    interface = enricher._build_interface("alphafold")

    assert isinstance(interface, AlphafoldInterface)
    assert interface.structures == ["pdb"]
    assert interface.constructor_kwargs == {"max_workers": 2, "total_retries": 4}


def test_crossref_interface_kwargs_do_not_change_other_databases() -> None:
    assert get_crossref_interface_kwargs("alphafold") == {"structures": ["pdb"]}
    assert get_crossref_interface_kwargs("uniprot") == {}
