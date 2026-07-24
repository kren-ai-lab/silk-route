"""Tests for NiceGUI-free workflow-builder form helpers.

These helpers live outside the NiceGUI module so they can be exercised without
the GUI dependency installed; this suite imports them directly.
"""

from __future__ import annotations

import asyncio
import sys

import pytest

from silkroute.gui import form_helpers as fh


class _FakeUploadFile:
    def __init__(self, content: str) -> None:
        self.content = content
        self.requested_encoding = ""

    async def text(self, encoding: str) -> str:
        self.requested_encoding = encoding
        return self.content


class _FakeUploadEvent:
    def __init__(self, content: str) -> None:
        self.file = _FakeUploadFile(content)


def test_form_helpers_import_does_not_load_nicegui() -> None:
    assert "nicegui" not in sys.modules


@pytest.mark.parametrize(
    ("filename", "expected"),
    [("workflow.yml", True), ("workflow.YAML", True), ("workflow.txt", False), (None, False)],
)
def test_is_supported_workflow_yaml_filename(filename: object, expected: bool) -> None:
    assert fh.is_supported_workflow_yaml_filename(filename) is expected


def test_query_builder_label_and_key_round_trip() -> None:
    label = fh.get_query_builder_label("uniprot")
    assert fh.get_query_builder_key(label) == "uniprot"
    assert fh.is_uniprot_builder_key(label)


def test_chembl_builder_key_detection() -> None:
    chembl_key = next(iter(fh.CHEMBL_BUILDER_RESOURCE_BY_KEY))
    assert fh.is_chembl_builder_key(chembl_key)
    assert not fh.is_uniprot_builder_key(chembl_key)


def test_query_input_mode_predicates() -> None:
    assert fh.is_manual_query_mode("manual")
    assert fh.is_advanced_builder_query_mode("advanced_builder")
    assert not fh.is_manual_query_mode("advanced_builder")


def test_uniprot_builder_field_label_value_round_trip() -> None:
    label = fh.get_uniprot_builder_field_label(fh.DEFAULT_UNIPROT_BUILDER_FIELD)
    assert fh.get_uniprot_builder_field_value(label) == fh.DEFAULT_UNIPROT_BUILDER_FIELD


def test_build_uniprot_builder_form_rows_first_row_has_no_connector() -> None:
    ui_rows = [
        {"connector": "AND", "field": fh.get_uniprot_builder_field_label("organism"), "values": "human"},
        {"connector": "AND", "field": fh.get_uniprot_builder_field_label("gene"), "values": "TP53"},
    ]

    form_rows = fh.build_uniprot_builder_form_rows(ui_rows)

    assert form_rows[0]["connector"] is None
    assert form_rows[1]["connector"] == "AND"
    assert form_rows[0]["field"] == "organism"


def test_chembl_field_options_and_filter_types_come_from_catalog() -> None:
    builder = fh.get_active_chembl_builder_label("chembl_target")
    options = fh.get_chembl_field_options(builder)
    assert options
    first_filter_types = fh.get_chembl_filter_type_options(builder, options[0])
    assert first_filter_types


def test_make_chembl_builder_ui_row_uses_first_allowed_operator() -> None:
    builder = fh.get_active_chembl_builder_label("chembl_target")
    row = fh.make_chembl_builder_ui_row(builder)
    assert set(row) == {"field", "filter_type", "value"}
    assert row["value"] == ""
    first_allowed_operator = fh.get_chembl_filter_type_options(builder, row["field"])[0]
    assert row["filter_type"] == first_allowed_operator


def test_build_chembl_builder_form_rows_converts_labels_to_field_keys() -> None:
    builder = fh.get_active_chembl_builder_label("chembl_target")
    label = fh.get_chembl_builder_field_label(builder, "gene_symbol")
    ui_rows = [{"field": label, "filter_type": "icontains", "value": "EGFR"}]

    form_rows = fh.build_chembl_builder_form_rows(builder, ui_rows)

    assert form_rows[0]["field"] == "gene_symbol"


def test_dataset_modality_and_interaction_helpers() -> None:
    assert fh.get_dataset_modality_value({"dataset.modality": "Interaction"}) == "interaction"
    assert fh.should_show_interaction_type_selector({"dataset.modality": "Interaction"})
    assert not fh.should_show_interaction_type_selector({"dataset.modality": "Protein"})
    assert fh.get_dataset_interaction_type_value({"dataset.interaction_type": "No interaction"}) is None


def test_read_upload_event_text_reads_utf8() -> None:
    event = _FakeUploadEvent("dataset: {}\n")

    text = asyncio.run(fh.read_upload_event_text(event))

    assert text == "dataset: {}\n"
    assert event.file.requested_encoding == "utf-8"


def test_read_upload_event_text_raises_without_file() -> None:
    with pytest.raises(ValueError, match="Uploaded file content was not available"):
        asyncio.run(fh.read_upload_event_text(object()))


# --- PubChem / ChEBI getter families (characterization; guards a future collapse) ---


def test_pubchem_field_options_and_help_use_modes_wording() -> None:
    label = fh.get_query_builder_label("pubchem_compound")
    assert fh.get_pubchem_field_options(label) == [
        "CID (cid)",
        "Name (name)",
        "InChIKey (inchikey)",
        "InChI (inchi)",
    ]
    # PubChem help ends with the mode list ("Modes:"), not operators.
    assert fh.get_pubchem_field_help(label, "name").endswith("Modes: lookup")


def test_pubchem_field_value_round_trips_label_to_key() -> None:
    label = fh.get_query_builder_label("pubchem_compound")
    assert fh.get_pubchem_builder_field_value(label, "Name (name)") == "name"


def test_chebi_field_options_and_help_use_operators_wording() -> None:
    label = fh.get_query_builder_label("chebi_entity")
    assert fh.get_chebi_field_options(label) == [
        "ChEBI ID (chebi_id)",
        "Name (name)",
        "Name contains (name_contains)",
    ]
    # ChEBI help ends with the operator list ("Operators:"), not modes.
    assert fh.get_chebi_field_help(label, "name").endswith("Operators: exact")
