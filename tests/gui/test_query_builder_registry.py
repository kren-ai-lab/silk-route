"""Tests for the query builder registry."""

from __future__ import annotations

import subprocess
import sys

import pytest

from bioseq_dl.gui.query_builders.registry import (
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
    } <= set(specs)


def test_query_builder_registry_labels_and_builder_types():
    specs = get_query_builder_specs()

    assert specs["uniprot"].label == "UniProt query builder"
    assert specs["uniprot"].database == "uniprot"
    assert specs["uniprot"].builder_type == "field_boolean"
    assert specs["chembl_target"].label == "ChEMBL target filter builder"
    assert specs["chembl_target"].database == "chembl"
    assert specs["chembl_target"].builder_type == "resource_filter"
    assert specs["chembl_activity"].builder_type == "flat_parameters"


def test_query_builder_registry_rejects_unknown_builder_key():
    with pytest.raises(ValueError, match="Unknown query builder"):
        get_query_builder_spec("unknown")


def test_query_builder_choices_expose_user_facing_labels():
    choices = get_query_builder_choices()

    assert choices["uniprot"] == "UniProt query builder"
    assert choices["chembl_activity"] == "ChEMBL activity parameter builder"


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

