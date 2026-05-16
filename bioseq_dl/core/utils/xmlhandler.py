import xml.etree.ElementTree as ET
from typing import Any

import pandas as pd


def dict_to_element(
    data: Any,
    parent: ET.Element,
    *,
    list_item_tag: str = "item"
) -> None:
    """
    Convert a dict, list, or scalar value to XML under `parent`.

    Rules:
    - dict  -> <key>...</key>
    - list  -> repeated <item>...</item> elements by default
    - value -> element text
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
    data: dict,
    root_tag: str = "results",
    list_item_tag: str = "item",
) -> ET.ElementTree:
    root = ET.Element(root_tag)
    dict_to_element(data, root, list_item_tag=list_item_tag)
    return ET.ElementTree(root)


def _xml_is_leaf(element: ET.Element) -> bool:
    """Return whether an XML element has no child elements."""
    return len(list(element)) == 0


def _parse_xml_container(element: ET.Element, list_item_tag: str) -> Any:
    """Parse an XML container as a scalar, dict, or list."""
    items = element.findall(f"./{list_item_tag}")

    if items:
        if all(_xml_is_leaf(item) for item in items):
            return [
                (item.text or "").strip()
                for item in items
                if (item.text or "").strip()
            ]

        output = []
        for item in items:
            parsed_item = {}
            for child in list(item):
                parsed_item[child.tag] = (
                    (child.text or "").strip()
                    if _xml_is_leaf(child)
                    else ET.tostring(child, encoding="unicode")
                )
            output.append(parsed_item)
        return output

    if _xml_is_leaf(element):
        return (element.text or "").strip()

    parsed = {}
    for child in list(element):
        parsed[child.tag] = (
            (child.text or "").strip()
            if _xml_is_leaf(child)
            else ET.tostring(child, encoding="unicode")
        )
    return parsed


def elementtree_to_dataframe(
    tree: ET.ElementTree,
    record_path: str = "./item",
    list_item_tag: str = "item",
) -> pd.DataFrame:
    """
    Convert an ElementTree to a DataFrame.

    Rules:
    - Each element at record_path becomes one row
    - Leaf elements -> scalar values
    - Containers with repeated <item> -> list[str] or list[dict]
    """

    root = tree.getroot()
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
