"""Tests for pure PubChem query builder utilities."""

from __future__ import annotations

import subprocess
import sys

from bioseq_dl.gui.query_builders.pubchem import (
    PubChemQueryBuilderRow,
    build_pubchem_interpreted_query,
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
