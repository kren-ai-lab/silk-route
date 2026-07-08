"""Unit tests for the XML conversion helpers."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import polars as pl

from bioseq_dl.core.utils.xmlhandler import (
    dict_to_element,
    dict_to_elementtree,
    elementtree_to_dataframe,
)


def _find(parent: ET.Element, tag: str) -> ET.Element:
    """find() that asserts the element exists (keeps the test type-checkable)."""
    el = parent.find(tag)
    assert el is not None, f"missing element <{tag}>"
    return el


def _root(tree: ET.ElementTree) -> ET.Element:
    root = tree.getroot()
    assert root is not None
    return root


def test_dict_to_elementtree_scalar_fields():
    root = _root(dict_to_elementtree({"a": 1, "b": "x"}, root_tag="results"))
    assert root.tag == "results"
    assert _find(root, "a").text == "1"
    assert _find(root, "b").text == "x"


def test_dict_to_elementtree_list_uses_item_tag():
    root = _root(dict_to_elementtree({"items": [1, 2]}, list_item_tag="entry"))
    items = _find(root, "items").findall("entry")
    assert [e.text for e in items] == ["1", "2"]


def test_dict_to_element_none_becomes_empty_text():
    root = ET.Element("root")
    dict_to_element({"x": None}, root)
    assert _find(root, "x").text == ""


def test_elementtree_to_dataframe_leaf_rows():
    # A top-level list yields one <item> row element per record.
    rows = [{"accession": "P1", "length": "100"}, {"accession": "P2", "length": "200"}]
    df = elementtree_to_dataframe(dict_to_elementtree(rows))

    assert list(df.columns) == ["accession", "length"]
    assert df["accession"][0] == "P1"
    # 'length' is cast to int by the numeric-field heuristic.
    assert df["length"][0] == 100
    assert df["length"].dtype == pl.Int64


def test_elementtree_to_dataframe_nested_list_container():
    rows = [{"accession": "P1", "ec": ["1.1.1.1", "1.1.1.2"]}]
    df = elementtree_to_dataframe(dict_to_elementtree(rows))

    assert df["ec"][0].to_list() == ["1.1.1.1", "1.1.1.2"]
