"""Tests for pure PubChem query builder utilities."""

from __future__ import annotations

import subprocess
import sys

import pytest

from bioseq_dl.core.workflow.pubchem_query_catalog import get_pubchem_query_builder_field_catalog
from bioseq_dl.core.workflow.pubchem_query_parser import parse_pubchem_query_builder_string
from bioseq_dl.gui.query_builders.pubchem import (
    PubChemQueryBuilderRow,
    build_pubchem_interpreted_query,
    get_pubchem_executable_parameter_name,
)

PUBCHEM_CONSISTENCY_CASES = (
    ("compound", "cid", "2244", None, "pubchem.compound:cid=2244", {"cid": "2244"}),
    (
        "compound",
        "name",
        "glucose",
        None,
        'pubchem.compound:name="glucose"',
        {"name": "glucose"},
    ),
    (
        "compound",
        "inchikey",
        "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
        None,
        'pubchem.compound:inchikey="BSYNRYMUTXBXSQ-UHFFFAOYSA-N"',
        {"inchikey": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"},
    ),
    (
        "compound",
        "inchi",
        "InChI=1S/H2O/h1H2",
        None,
        'pubchem.compound:inchi="InChI=1S/H2O/h1H2"',
        {"inchi": "InChI=1S/H2O/h1H2"},
    ),
    (
        "structure",
        "smiles_identity",
        "CC(=O)Oc1ccccc1C(=O)O",
        None,
        'pubchem.structure:smiles_identity="CC(=O)Oc1ccccc1C(=O)O"',
        {"smiles_identity": "CC(=O)Oc1ccccc1C(=O)O"},
    ),
    (
        "structure",
        "smiles_substructure",
        "c1ccccc1",
        None,
        'pubchem.structure:smiles_substructure="c1ccccc1"',
        {"smiles_substructure": "c1ccccc1"},
    ),
    (
        "structure",
        "similarity_2d",
        "446157",
        80,
        "pubchem.structure:similarity_2d_cid=446157 AND threshold=80",
        {"similarity_2d_cid": "446157", "threshold": 80},
    ),
)


def test_pubchem_compound_builder_produces_query_value() -> None:
    row = PubChemQueryBuilderRow("compound", "name", "glucose")

    assert build_pubchem_interpreted_query(row) == 'pubchem.compound:name="glucose"'


def test_pubchem_structure_builder_produces_query_value() -> None:
    row = PubChemQueryBuilderRow("structure", "smiles_substructure", "c1ccccc1")

    assert build_pubchem_interpreted_query(row) == 'pubchem.structure:smiles_substructure="c1ccccc1"'


def test_pubchem_similarity_builder_produces_query_value() -> None:
    row = PubChemQueryBuilderRow("structure", "similarity_2d", "446157", threshold=80)

    assert (
        build_pubchem_interpreted_query(row) == "pubchem.structure:similarity_2d_cid=446157 AND threshold=80"
    )


@pytest.mark.parametrize(
    ("resource", "field", "value", "threshold", "expected_query", "expected_parameters"),
    PUBCHEM_CONSISTENCY_CASES,
)
def test_pubchem_catalog_builder_parser_consistency(
    resource: str,
    field: str,
    value: str,
    threshold: int | None,
    expected_query: str,
    expected_parameters: dict[str, object],
) -> None:
    catalog = get_pubchem_query_builder_field_catalog(resource)
    assert field in catalog

    query = build_pubchem_interpreted_query(
        PubChemQueryBuilderRow(resource, field, value, threshold=threshold)
    )
    plan = parse_pubchem_query_builder_string(query)

    assert query == expected_query
    assert plan["parameters"] == expected_parameters


def test_all_visible_pubchem_fields_have_consistency_cases() -> None:
    visible_fields = {
        (resource, field)
        for resource in ("compound", "structure")
        for field in get_pubchem_query_builder_field_catalog(resource)
    }
    tested_fields = {(resource, field) for resource, field, *_rest in PUBCHEM_CONSISTENCY_CASES}

    assert tested_fields == visible_fields


def test_pubchem_similarity_mapping_is_explicit() -> None:
    assert get_pubchem_executable_parameter_name("structure", "similarity_2d") == "similarity_2d_cid"


def test_pubchem_builder_import_does_not_import_nicegui() -> None:
    import_script = """
import sys
import bioseq_dl.gui.query_builders.pubchem

if "nicegui" in sys.modules:
    raise RuntimeError("Importing pure PubChem query builder utilities loaded NiceGUI.")
"""

    subprocess.run(  # noqa: S603
        [sys.executable, "-c", import_script],
        check=True,
        capture_output=True,
        text=True,
    )
