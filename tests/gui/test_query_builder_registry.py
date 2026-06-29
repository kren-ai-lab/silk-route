"""Tests for the query builder registry."""

from __future__ import annotations

import subprocess
import sys

import pytest

from bioseq_dl.gui.query_builders.registry import (
    get_compatible_query_builder_choices,
    get_compatible_query_builder_specs,
    get_query_builder_choices,
    get_query_builder_spec,
    get_query_builder_specs,
)


def test_query_builder_registry_contains_uniprot_and_chembl_builders():
    specs = get_query_builder_specs()

    assert {
        "uniprot",
        "chembl_target",
        "chembl_assay",
        "chembl_cell_line",
        "chembl_molecule",
        "chembl_activity",
        "pubchem_compound",
        "pubchem_structure",
        "chebi_entity",
        "chebi_ontology",
        "chebi_structure",
    } <= set(specs)


def test_query_builder_registry_labels_and_builder_types():
    specs = get_query_builder_specs()

    assert specs["uniprot"].label == "UniProt query builder"
    assert specs["uniprot"].database == "uniprot"
    assert specs["uniprot"].builder_type == "field_boolean"
    assert specs["uniprot"].compatible_modalities == ("protein", "interaction")
    assert specs["chembl_target"].label == "ChEMBL target filter builder"
    assert specs["chembl_target"].database == "chembl"
    assert specs["chembl_target"].builder_type == "resource_filter"
    assert specs["chembl_activity"].builder_type == "flat_parameters"
    assert specs["pubchem_compound"].database == "pubchem"
    assert specs["chebi_entity"].database == "chebi"


def test_query_builder_registry_rejects_unknown_builder_key():
    with pytest.raises(ValueError, match="Unknown query builder"):
        get_query_builder_spec("unknown")


def test_query_builder_choices_expose_user_facing_labels():
    choices = get_query_builder_choices()

    assert choices["uniprot"] == "UniProt query builder"
    assert choices["chembl_activity"] == "ChEMBL activity parameter builder"


def test_protein_modality_returns_only_uniprot_builder():
    choices = get_compatible_query_builder_choices("protein", None)

    assert choices == {"uniprot": "UniProt query builder"}


def test_compound_modality_returns_compound_chembl_builders():
    choices = get_compatible_query_builder_choices("compound", None)

    assert choices == {
        "chembl_molecule": "ChEMBL molecule filter builder",
        "chembl_activity": "ChEMBL activity parameter builder",
        "pubchem_compound": "PubChem compound lookup builder",
        "pubchem_structure": "PubChem structure search builder",
        "chebi_entity": "ChEBI entity search builder",
        "chebi_ontology": "ChEBI ontology search builder",
        "chebi_structure": "ChEBI structure search builder",
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


def test_pubchem_and_chebi_builders_are_compound_only():
    protein_choices = get_compatible_query_builder_choices("protein", None)
    pli_choices = get_compatible_query_builder_choices("interaction", "protein-ligand")

    for builder_key in (
        "pubchem_compound",
        "pubchem_structure",
        "chebi_entity",
        "chebi_ontology",
        "chebi_structure",
    ):
        assert builder_key not in protein_choices
        assert builder_key not in pli_choices


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
