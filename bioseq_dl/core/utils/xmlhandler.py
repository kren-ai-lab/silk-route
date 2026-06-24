"""XML parsing and DataFrame conversion utilities."""

import xml.etree.ElementTree as ET
from typing import Any

import pandas as pd


def dict_to_element(data: Any, parent: ET.Element, *, list_item_tag: str = "item") -> None:
    """Convert a dict, list, or scalar value to XML under ``parent``.

    Dicts become ``<key>...</key>`` elements, lists become repeated
    ``<item>...</item>`` elements, and scalars become element text.

    Args:
        data (Any): Value to serialize into XML.
        parent (ET.Element): Element to append the serialized value to.
        list_item_tag (str): Tag name used for list items. Default is "item".

    """
    if isinstance(data, dict):
        for key, value in data.items():
            child = ET.SubElement(parent, key)
            dict_to_element(value, child, list_item_tag=list_item_tag)

    elif isinstance(data, list):
        for item in data:
            child = ET.SubElement(parent, list_item_tag)
            dict_to_element(item, child, list_item_tag=list_item_tag)

    else:
        parent.text = "" if data is None else str(data)


def dict_to_elementtree(
    data: Any,
    root_tag: str = "results",
    list_item_tag: str = "item",
) -> ET.ElementTree:
    """Convert a dict/list/scalar value into an ``ElementTree`` rooted at ``root_tag``.

    Args:
        data (Any): Value to serialize into XML.
        root_tag (str): Tag name for the root element. Default is "results".
        list_item_tag (str): Tag name used for list items. Default is "item".

    Returns:
        ET.ElementTree: Tree containing the serialized value.

    """
    root = ET.Element(root_tag)
    dict_to_element(data, root, list_item_tag=list_item_tag)
    return ET.ElementTree(root)


def _xml_is_leaf(element: ET.Element) -> bool:
    """Return whether an XML element has no child elements."""
    return len(element) == 0


def _children_map(element: ET.Element) -> dict[str, str]:
    """Map each child tag to its leaf text, or serialized XML for non-leaf children."""
    return {
        child.tag: (child.text or "").strip()
        if _xml_is_leaf(child)
        else ET.tostring(child, encoding="unicode")
        for child in element
    }


def _parse_xml_container(element: ET.Element, list_item_tag: str) -> Any:
    """Parse an XML container as a scalar, dict, or list.

    Repeated ``list_item_tag`` children yield a list (of strings if all leaves,
    otherwise of dicts); a leaf element yields its text; any other element yields
    a tag-to-text mapping.

    Args:
        element (ET.Element): Container element to parse.
        list_item_tag (str): Tag name identifying repeated list items.

    Returns:
        Any: A string, list, or dict depending on the element's structure.

    """
    items = element.findall(f"./{list_item_tag}")

    if items:
        if all(_xml_is_leaf(item) for item in items):
            return [(item.text or "").strip() for item in items if (item.text or "").strip()]

        return [_children_map(item) for item in items]

    if _xml_is_leaf(element):
        return (element.text or "").strip()

    return _children_map(element)


def elementtree_to_dataframe(
    tree: ET.ElementTree,
    record_path: str = "./item",
    list_item_tag: str = "item",
) -> pd.DataFrame:
    """Convert an ElementTree to a DataFrame.

    Each element at ``record_path`` becomes one row: leaf children become scalar
    values and container children become ``list[str]`` or ``list[dict]``. Common
    numeric fields (``length``, ``organism_id``, ``tax_id``) are cast to int.

    Args:
        tree (ET.ElementTree): Source tree to convert.
        record_path (str): Path selecting the elements that become rows. Default is "./item".
        list_item_tag (str): Tag name used for list items within containers. Default is "item".

    Returns:
        pd.DataFrame: One row per matched record; empty if the tree has no root.

    """
    root = tree.getroot()
    if root is None:
        return pd.DataFrame()
    records = root.findall(record_path)

    rows = []
    for rec in records:
        row: dict[str, Any] = {}
        for child in list(rec):
            if _xml_is_leaf(child):
                row[child.tag] = (child.text or "").strip()
            else:
                row[child.tag] = _parse_xml_container(child, list_item_tag)

        # Cast common numeric fields.
        for k in ("length", "organism_id", "tax_id"):
            if k in row and isinstance(row[k], str) and row[k].isdigit():
                row[k] = int(row[k])

        rows.append(row)

    return pd.DataFrame(rows)
