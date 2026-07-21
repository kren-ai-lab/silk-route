"""Tests for the query builder registry."""

from __future__ import annotations

import subprocess
import sys

import pytest

from bioseq_dl.gui.query_builders.registry import (
    get_compatible_query_builder_choices,
    get_compatible_query_builder_specs,
    get_query_builder_spec,
)


def test_query_builder_registry_rejects_unknown_builder_key():
    with pytest.raises(ValueError, match="Unknown query builder"):
        get_query_builder_spec("unknown")


def test_protein_modality_returns_only_uniprot_builder():
    choices = get_compatible_query_builder_choices("protein", None)

    assert choices == {"uniprot": "UniProt query builder"}


def test_compound_modality_returns_compound_builders():
    choices = get_compatible_query_builder_choices("compound", None)

    assert set(choices) == {
        "chembl_molecule",
        "chembl_activity",
        "chembl_ic50",
        "pubchem_compound",
        "pubchem_structure",
        "chebi_entity",
    }


def test_protein_ligand_interaction_returns_compatible_chembl_builders():
    choices = get_compatible_query_builder_choices("interaction", "protein-ligand")

    assert choices == {
        "chembl_target": "ChEMBL target filter builder",
        "chembl_assay": "ChEMBL assay filter builder",
        "chembl_activity": "ChEMBL activity parameter builder",
    }


def test_protein_protein_interaction_returns_uniprot_builder():
    choices = get_compatible_query_builder_choices("interaction", "protein-protein")

    assert choices == {"uniprot": "UniProt query builder"}


def test_interaction_without_interaction_type_returns_no_builders():
    choices = get_compatible_query_builder_choices("interaction", None)

    assert choices == {}


def test_unknown_modality_returns_no_builders():
    specs = get_compatible_query_builder_specs("unknown", None)

    assert specs == ()


def test_query_builder_registry_import_is_lightweight():
    import_script = """
import sys
import bioseq_dl.gui.query_builders.registry

blocked_prefixes = (
    "nicegui",
    "bioseq_dl.core.interfaces",
    "bioseq_dl.cli",
)
for blocked_prefix in blocked_prefixes:
    loaded = [
        module_name
        for module_name in sys.modules
        if module_name == blocked_prefix or module_name.startswith(f"{blocked_prefix}.")
    ]
    if loaded:
        raise RuntimeError(f"Unexpected imports for {blocked_prefix}: {loaded}")
"""

    subprocess.run(  # noqa: S603
        [sys.executable, "-c", import_script],
        check=True,
        capture_output=True,
        text=True,
    )
