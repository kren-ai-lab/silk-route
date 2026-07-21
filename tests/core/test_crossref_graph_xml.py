"""Graph enrichment rows serialize to an XML string for the XML output path.

``_process_dataframe`` feeds each per-row result to ``fromstring``, so graph rows
must render as ``<results><item>...</item></results>`` text.
"""

from __future__ import annotations

from typing import cast
from xml.etree.ElementTree import ElementTree, fromstring, tostring

import polars as pl

from bioseq_dl.core.crossref_enricher import CrossRefEnricher, EndpointSpec
from bioseq_dl.core.metadata import FetchMetadata


def test_graph_row_result_xml_is_parseable():
    row = {"source_accession": "P12345", "graph_json": '{"nodes": [1]}'}
    xml_text = CrossRefEnricher._graph_row_result(row, "xml")
    assert isinstance(xml_text, str)
    parsed = fromstring(xml_text)  # noqa: S314  # test-controlled XML
    items = parsed.findall("item")
    assert len(items) == 1
    assert "P12345" in tostring(items[0], encoding="unicode")


def test_empty_graph_result_xml_is_parseable():
    xml_text = CrossRefEnricher._empty_graph_result("xml")
    assert fromstring(xml_text).findall("item") == []  # noqa: S314  # test-controlled XML


def test_process_dataframe_xml_aggregates_graph_rows(monkeypatch):
    enricher = CrossRefEnricher()

    def fake_search_and_merge(row, instance, spec, params, fmt):
        graph_row = {"source_accession": row["id"], "graph_json": '{"nodes": [1]}'}
        meta = FetchMetadata(data_info={"total_entries": 1})
        return CrossRefEnricher._graph_row_result(graph_row, fmt), meta.to_dict()

    monkeypatch.setattr(enricher, "_search_and_merge", fake_search_and_merge)

    df = pl.DataFrame({"id": ["P1", "P2"]})
    result, _ = enricher._process_dataframe(
        df, instance=None, spec=cast("EndpointSpec", None), params={}, fmt="xml"
    )

    assert isinstance(result, ElementTree)
    root = result.getroot()
    items = root.findall("item")
    assert len(items) == 2
