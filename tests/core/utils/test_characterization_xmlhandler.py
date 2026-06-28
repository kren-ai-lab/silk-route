"""Characterization tests for elementtree_to_dataframe (pre-Polars migration).

This converter is a Polars-migration hot spot: a single column can hold a
scalar string in one row and a ``list``/``list[dict]`` in another (a pandas
object column). These golden tests pin the row content the converter produces
today so the migration can prove the per-row shapes survive.
"""

from __future__ import annotations

from xml.etree.ElementTree import Element, ElementTree, SubElement

from bioseq_dl.core.utils.xmlhandler import dict_to_elementtree, elementtree_to_dataframe
from tests._helpers import frame_row_count, frame_to_records


def _tree_from_items(items: list[dict]) -> ElementTree:
    """Build a ``<results><item>...</item></results>`` tree from row dicts."""
    root = Element("results")
    for item in items:
        rec = SubElement(root, "item")
        for key, value in item.items():
            child = SubElement(rec, key)
            if isinstance(value, list):
                for elem in value:
                    leaf = SubElement(child, "item")
                    leaf.text = str(elem)
            else:
                child.text = str(value)
    return ElementTree(root)


def test_leaf_fields_become_scalar_strings():
    tree = _tree_from_items([{"id": "P1", "name": "alpha"}])
    records = frame_to_records(elementtree_to_dataframe(tree))
    assert records == [{"id": "P1", "name": "alpha"}]


def test_numeric_fields_cast_to_int():
    # length / organism_id / tax_id are coerced to int when they look numeric.
    tree = _tree_from_items([{"id": "P1", "length": "120", "organism_id": "9606"}])
    records = frame_to_records(elementtree_to_dataframe(tree))
    assert records[0]["length"] == 120
    assert records[0]["organism_id"] == 9606


def test_repeated_leaf_children_become_list_of_str():
    tree = _tree_from_items([{"id": "P1", "xrefs": ["a", "b", "c"]}])
    records = frame_to_records(elementtree_to_dataframe(tree))
    assert records[0]["xrefs"] == ["a", "b", "c"]


def test_repeated_dict_children_become_list_of_dict():
    root = Element("results")
    rec = SubElement(root, "item")
    rec_id = SubElement(rec, "id")
    rec_id.text = "P1"
    refs = SubElement(rec, "refs")
    for db, acc in [("KEGG", "K1"), ("PDB", "1ABC")]:
        ref = SubElement(refs, "item")
        SubElement(ref, "db").text = db
        SubElement(ref, "acc").text = acc
    records = frame_to_records(elementtree_to_dataframe(ElementTree(root)))
    assert records[0]["refs"] == [
        {"db": "KEGG", "acc": "K1"},
        {"db": "PDB", "acc": "1ABC"},
    ]


def test_empty_tree_returns_empty_frame():
    tree = dict_to_elementtree({}, root_tag="results")
    out = elementtree_to_dataframe(tree)
    assert frame_row_count(out) == 0
