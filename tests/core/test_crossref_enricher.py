"""Tests for cross-reference interface construction defaults."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from bioseq_dl.core.crossref_enricher import (
    CrossRefEnricher,
    EndpointSpec,
    attach_source_context,
    get_crossref_interface_kwargs,
    is_graph_like_enrichment,
    normalize_crossref_format,
)
from bioseq_dl.core.interfaces.alphafold import AlphafoldInterface
from bioseq_dl.core.utils.query_builders import INTERFACE_CLASSES


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
        self.fetch_kwargs: dict[str, object] = {}

    def fetch_single(self, **kwargs: object) -> tuple[object, dict]:
        """Return the configured result with empty metadata."""
        self.fetch_kwargs = kwargs
        return self.result, {}


class StubRegisteredInterProInterface:
    """Return stable tabular InterPro data when constructed from the registry."""

    def __init__(self, **_kwargs: object) -> None:
        """Accept CrossRefEnricher constructor options."""

    def fetch_single(self, **_kwargs: object) -> tuple[pd.DataFrame, dict]:
        """Return one deterministic InterPro annotation row."""
        return pd.DataFrame([{"entry_id": "IPR002117"}]), {}


@pytest.mark.parametrize(
    ("format_value", "expected"),
    [
        ("csv", "dataframe"),
        ("dataframe", "dataframe"),
        ("json", "json"),
        ("xml", "xml"),
    ],
)
def test_normalize_crossref_format(format_value: str, expected: str) -> None:
    assert normalize_crossref_format(format_value) == expected


def test_normalize_crossref_format_rejects_unsupported_values() -> None:
    with pytest.raises(ValueError, match="Unsupported cross-reference format 'parquet'"):
        normalize_crossref_format("parquet")


def test_crossref_enricher_csv_alias_matches_dataframe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(INTERFACE_CLASSES, "interpro", StubRegisteredInterProInterface)
    input_data = pd.DataFrame([{"accession": "P04637", "organism_id": "9606"}])
    spec = EndpointSpec(database="interpro", endpoint="entry")
    enricher = CrossRefEnricher(endpoint_specs=[spec])

    csv_results, csv_metadata = enricher.enrich(input_data, format="csv")
    dataframe_results, dataframe_metadata = enricher.enrich(input_data, format="dataframe")

    pd.testing.assert_frame_equal(csv_results["interpro_entry"], dataframe_results["interpro_entry"])
    assert csv_metadata == dataframe_metadata


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
    assert "graph_json" not in result.columns


def test_pathwaycommons_neighborhood_preserves_one_raw_graph_row() -> None:
    enricher = CrossRefEnricher()
    input_data = pd.DataFrame(
        [
            {
                "accession": "P02776",
                "protein_name": "Platelet factor 4",
                "organism_id": "9606",
            }
        ]
    )
    spec = EndpointSpec(database="pathwaycommons", endpoint="neighborhood")
    raw_graph = {
        "@context": {"bp": "http://www.biopax.org/release/biopax-level3.owl#"},
        "@graph": [
            {"@id": "uniprot:P02776", "displayName": "PF4"},
            {"@id": "reactome:R-HSA-114608", "@type": "bp:Pathway"},
        ],
    }
    interface = StubCrossRefInterface(raw_graph)

    result, metadata = enricher._process_dataframe(
        input_data,
        interface,
        spec,
        {},
        "dataframe",
    )

    assert len(result) == 1
    assert result.loc[0, "source_accession"] == "P02776"
    assert result.loc[0, "source_protein_name"] == "Platelet factor 4"
    assert result.loc[0, "source_organism_id"] == "9606"
    assert result.loc[0, "source_database"] == "pathwaycommons"
    assert result.loc[0, "source_endpoint"] == "neighborhood"
    assert result.loc[0, "graph_format"] == "jsonld"
    assert result.loc[0, "graph_record_count"] == 2
    assert json.loads(result.loc[0, "graph_json"]) == raw_graph
    assert "@id" not in result.columns
    assert "displayName" not in result.columns
    assert interface.fetch_kwargs["parse"] is False
    assert interface.fetch_kwargs["format"] == "json"
    assert metadata["output_kind"] == "raw_graph"
    assert metadata["graph_serialization"] == "json"
    assert metadata["graph_tabularization"] == "one_row_per_source"
    assert "not interpreted" in metadata["note"]


def test_pathwaycommons_empty_graph_preserves_one_provenance_row() -> None:
    enricher = CrossRefEnricher()
    input_data = pd.DataFrame([{"accession": "P02776", "organism_id": "9606"}])
    spec = EndpointSpec(database="pathwaycommons", endpoint="neighborhood")
    interface = StubCrossRefInterface({})

    result, _ = enricher._process_dataframe(input_data, interface, spec, {}, "dataframe")

    assert len(result) == 1
    assert result.loc[0, "source_accession"] == "P02776"
    assert result.loc[0, "source_organism_id"] == "9606"
    assert result.loc[0, "graph_record_count"] == 0
    assert json.loads(result.loc[0, "graph_json"]) == []


def test_pathwaycommons_fetch_preserves_graph_payload_in_one_row() -> None:
    enricher = CrossRefEnricher()
    input_data = pd.DataFrame(
        [{"accession": "P04637", "pathwaycommons_ids": ["uniprot:P04637"]}]
    )
    spec = EndpointSpec(database="pathwaycommons", endpoint="fetch")
    raw_graph = [
        {"@id": "uniprot:P04637", "@type": "bp:Protein"},
        {"@id": "reactome:R-HSA-69541", "@type": "bp:Pathway"},
    ]
    interface = StubCrossRefInterface(raw_graph)

    result, metadata = enricher._process_dataframe(
        input_data,
        interface,
        spec,
        {},
        "dataframe",
    )

    assert len(result) == 1
    assert result.loc[0, "source_endpoint"] == "fetch"
    assert result.loc[0, "graph_record_count"] == 2
    assert json.loads(result.loc[0, "graph_json"]) == raw_graph
    assert metadata["output_kind"] == "raw_graph"


def test_pathwaycommons_fetch_and_neighborhood_are_registered_as_graph_like() -> None:
    assert is_graph_like_enrichment("pathwaycommons", "fetch") is True
    assert is_graph_like_enrichment("pathwaycommons", "neighborhood") is True
    assert is_graph_like_enrichment("interpro", "entry") is False


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
