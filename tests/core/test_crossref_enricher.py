"""Tests for cross-reference interface construction defaults."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from bioseq_dl.core.crossref_enricher import (
    CrossRefEnricher,
    EndpointSpec,
    attach_source_context,
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


class StubCrossRefInterface:
    """Return a configured result from a cross-reference fetch call."""

    def __init__(self, result: object) -> None:
        """Store the result returned by fetch_single."""
        self.result = result

    def fetch_single(self, **_kwargs: object) -> tuple[object, dict]:
        """Return the configured result with empty metadata."""
        return self.result, {}


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


def test_crossref_enricher_attaches_source_context_to_dataframe_results() -> None:
    enricher = CrossRefEnricher()
    input_data = pd.DataFrame(
        [{"accession": "P04637", "protein_name": "p53", "organism_id": "9606"}]
    )
    spec = EndpointSpec(database="interpro", endpoint="entry")
    interface = StubCrossRefInterface(pd.DataFrame([{"entry_id": "IPR002117"}]))

    result, _ = enricher._process_dataframe(input_data, interface, spec, {}, "dataframe")

    assert result.loc[0, "entry_id"] == "IPR002117"
    assert result.loc[0, "source_accession"] == "P04637"
    assert result.loc[0, "source_protein_name"] == "p53"
    assert result.loc[0, "source_organism_id"] == "9606"
    assert result.loc[0, "source_database"] == "interpro"
    assert result.loc[0, "source_endpoint"] == "entry"


def test_crossref_enricher_attaches_source_context_to_list_results() -> None:
    enricher = CrossRefEnricher()
    row = pd.Series({"accession": "P04637", "organism_id": "9606"})
    query = {"source": ["P04637"], "organism": ["9606"]}
    spec = EndpointSpec(database="pathwaycommons", endpoint="neighborhood")
    interface = StubCrossRefInterface(
        [{"uri": "http://identifiers.org/uniprot/P04637"}]
    )

    result, metadata = enricher._search_and_merge(row, interface, spec, {}, "json")

    assert result == [
        {
            "uri": "http://identifiers.org/uniprot/P04637",
            "source_accession": "P04637",
            "source_organism_id": "9606",
            "source_query": query,
            "source_database": "pathwaycommons",
            "source_endpoint": "neighborhood",
        }
    ]
    assert metadata["result_kind"] == "graph_neighborhood"
    assert "not compact pathway annotations" in metadata["result_description"]


def test_attach_source_context_adds_provenance_to_dict_results() -> None:
    result = attach_source_context(
        {"entry_id": "IPR002117"},
        pd.Series({"accession": "P04637", "organism_id": pd.NA}),
        {"id": "IPR002117"},
        source_database="interpro",
        source_endpoint="entry",
    )

    assert result["source_accession"] == "P04637"
    assert "source_organism_id" not in result
    assert result["source_query"] == {"id": "IPR002117"}
