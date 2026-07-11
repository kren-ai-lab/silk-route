"""NiceGUI-free helpers for the workflow YAML builder GUI.

Pure label<->value conversion, builder-field lookups, and mutable UI-row
factories used by the NiceGUI app. Kept free of ``nicegui`` so they can be
imported and tested without the GUI dependency installed.
"""

from __future__ import annotations

from typing import Any

from bioseq_dl.core.workflow.chembl_query_catalog import get_chembl_query_builder_field_catalog
from bioseq_dl.core.workflow.query_field_catalog import get_uniprot_query_builder_field_catalog
from bioseq_dl.gui.query_builders.registry import get_query_builder_choices
from bioseq_dl.gui.query_builders.uniprot import get_uniprot_query_builder_field_metadata
from bioseq_dl.gui.yaml_builder import (
    CHEMBL_BUILDER_RESOURCE_BY_KEY,
    INTERACTION_TYPE_LABEL_TO_VALUE,
    MODALITY_LABEL_TO_VALUE,
    UNIPROT_MATCH_MODE_LABEL_TO_VALUE,
    get_labeled_option_default,
    normalize_labeled_value,
    normalize_query_input_mode,
)

UNIPROT_QUERY_FIELD_CATALOG = get_uniprot_query_builder_field_catalog()
UNIPROT_BUILDER_FIELD_LABEL_TO_VALUE = {
    f"{entry.label} ({entry.key})": entry.key for entry in UNIPROT_QUERY_FIELD_CATALOG.values()
}
UNIPROT_BUILDER_FIELD_VALUE_TO_LABEL = {
    value: label for label, value in UNIPROT_BUILDER_FIELD_LABEL_TO_VALUE.items()
}
DEFAULT_UNIPROT_BUILDER_FIELD = "organism"
QUERY_BUILDER_KEY_TO_LABEL = get_query_builder_choices()
QUERY_BUILDER_LABEL_TO_KEY = {label: key for key, label in QUERY_BUILDER_KEY_TO_LABEL.items()}
DEFAULT_CHEMBL_FIELDS_BY_RESOURCE = {
    "target": "gene_symbol",
    "assay": "label_type",
    "cell_line": "organism",
    "molecule": "name",
    "activity": "target_chembl_id",
}
SUPPORTED_WORKFLOW_YAML_SUFFIXES = (".yml", ".yaml")
NO_INTERACTION_LABEL = get_labeled_option_default(None, INTERACTION_TYPE_LABEL_TO_VALUE)


def is_supported_workflow_yaml_filename(filename: object) -> bool:
    """Return whether an uploaded filename looks like YAML."""
    return str(filename or "").lower().endswith(SUPPORTED_WORKFLOW_YAML_SUFFIXES)


async def read_upload_event_text(event: Any) -> str:
    """Read uploaded NiceGUI file content as UTF-8 text."""
    upload_file = getattr(event, "file", None)
    if upload_file is None:
        msg = "Uploaded file content was not available."
        raise ValueError(msg)
    return await upload_file.text("utf-8")


def is_manual_query_mode(value: object) -> bool:
    """Return whether a GUI query mode value means manual query entry."""
    return normalize_query_input_mode(value) == "manual"


def is_advanced_builder_query_mode(value: object) -> bool:
    """Return whether a GUI query mode value means advanced builder entry."""
    return normalize_query_input_mode(value) == "advanced_builder"


def is_uniprot_builder_key(value: object) -> bool:
    """Return whether a GUI builder key or label selects the UniProt builder."""
    return get_query_builder_key(value) == "uniprot"


def is_chembl_builder_key(value: object) -> bool:
    """Return whether a GUI builder key or label selects a ChEMBL builder."""
    return get_query_builder_key(value) in CHEMBL_BUILDER_RESOURCE_BY_KEY


def get_query_builder_label(builder_key: object) -> str:
    """Return a query-builder label for an internal builder key."""
    return QUERY_BUILDER_KEY_TO_LABEL.get(str(builder_key), str(builder_key))


def get_query_builder_key(label_or_key: object) -> str:
    """Return an internal query-builder key for a label or key."""
    text = str(label_or_key)
    return QUERY_BUILDER_LABEL_TO_KEY.get(text, text)


def get_uniprot_builder_field_label(field: object) -> str:
    """Return a visible builder field label for an internal field key."""
    return UNIPROT_BUILDER_FIELD_VALUE_TO_LABEL.get(str(field), str(field))


def get_uniprot_builder_field_value(label_or_value: object) -> str:
    """Return an internal builder field key for a visible field label or field key."""
    text = str(label_or_value)
    return UNIPROT_BUILDER_FIELD_LABEL_TO_VALUE.get(text, text)


def get_uniprot_builder_field_entry(label_or_value: object) -> object:
    """Return catalog metadata for a visible field label or field key."""
    field = get_uniprot_builder_field_value(label_or_value)
    return get_uniprot_query_builder_field_metadata(field)


def get_uniprot_builder_field_placeholder(label_or_value: object) -> str:
    """Return the values placeholder for a visible field label or field key."""
    entry = get_uniprot_builder_field_entry(label_or_value)
    return str(entry.placeholder)


def get_uniprot_builder_field_help(label_or_value: object) -> str:
    """Return compact field help for a visible field label or field key."""
    entry = get_uniprot_builder_field_entry(label_or_value)
    examples = ", ".join(entry.examples)
    return f"{entry.description} Examples: {examples}"


def get_uniprot_match_mode_label(value: object) -> str:
    """Return a visible match-mode label for an internal match-mode value."""
    return get_labeled_option_default(value, UNIPROT_MATCH_MODE_LABEL_TO_VALUE)


def make_uniprot_builder_ui_row(connector: str | None = None) -> dict[str, object]:
    """Return one mutable UI row for the advanced UniProt builder."""
    return {
        "connector": connector or "",
        "field": get_uniprot_builder_field_label(DEFAULT_UNIPROT_BUILDER_FIELD),
        "values": "",
        "match_mode": get_uniprot_match_mode_label("any"),
    }


def build_uniprot_builder_form_rows(ui_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Convert visible NiceGUI builder rows to pure builder form rows."""
    form_rows = []
    for index, row in enumerate(ui_rows):
        connector = row.get("connector") if index > 0 else None
        form_rows.append(
            {
                "connector": connector,
                "field": get_uniprot_builder_field_value(row.get("field", "")),
                "values": row.get("values", ""),
                "match_mode": normalize_labeled_value(
                    row.get("match_mode", "Any"),
                    UNIPROT_MATCH_MODE_LABEL_TO_VALUE,
                ),
            }
        )
    return form_rows


def get_chembl_builder_resource(builder_label_or_key: object) -> str:
    """Return the ChEMBL resource for a selected builder key or label."""
    builder_key = get_query_builder_key(builder_label_or_key)
    return CHEMBL_BUILDER_RESOURCE_BY_KEY[builder_key]


def get_active_chembl_builder_label(builder_label_or_key: object) -> str:
    """Return a ChEMBL builder label, falling back to target when another builder is active."""
    if is_chembl_builder_key(builder_label_or_key):
        return str(builder_label_or_key)
    return get_query_builder_label("chembl_target")


def get_chembl_field_catalog_for_builder(builder_label_or_key: object) -> dict[str, object]:
    """Return the ChEMBL field catalog for the selected builder."""
    return get_chembl_query_builder_field_catalog(get_chembl_builder_resource(builder_label_or_key))


def get_chembl_builder_field_label(builder_label_or_key: object, field: object) -> str:
    """Return a visible ChEMBL field label."""
    catalog = get_chembl_field_catalog_for_builder(builder_label_or_key)
    field_text = str(field)
    if field_text in catalog:
        return f"{catalog[field_text].label} ({field_text})"
    return field_text


def get_chembl_builder_field_value(builder_label_or_key: object, label_or_value: object) -> str:
    """Return an internal ChEMBL field key for a visible field label or field key."""
    catalog = get_chembl_field_catalog_for_builder(builder_label_or_key)
    text = str(label_or_value)
    for key, entry in catalog.items():
        if text == f"{entry.label} ({key})":
            return key
    return text


def get_chembl_field_entry(builder_label_or_key: object, label_or_value: object) -> object:
    """Return ChEMBL catalog metadata for a visible field label or field key."""
    catalog = get_chembl_field_catalog_for_builder(builder_label_or_key)
    field = get_chembl_builder_field_value(builder_label_or_key, label_or_value)
    return catalog[field]


def get_chembl_field_options(builder_label_or_key: object) -> list[str]:
    """Return visible ChEMBL field options for the selected builder."""
    catalog = get_chembl_field_catalog_for_builder(builder_label_or_key)
    return [get_chembl_builder_field_label(builder_label_or_key, key) for key in catalog]


def get_chembl_filter_type_options(builder_label_or_key: object, label_or_value: object) -> list[str]:
    """Return filter type options for one selected ChEMBL field."""
    entry = get_chembl_field_entry(builder_label_or_key, label_or_value)
    return list(entry.allowed_operators)


def get_chembl_field_help(builder_label_or_key: object, label_or_value: object) -> str:
    """Return compact ChEMBL field help."""
    entry = get_chembl_field_entry(builder_label_or_key, label_or_value)
    examples = ", ".join(entry.examples)
    operators = ", ".join(entry.allowed_operators)
    return f"{entry.description} Examples: {examples}. Operators: {operators}"


def make_chembl_builder_ui_row(builder_label_or_key: object) -> dict[str, object]:
    """Return one mutable UI row for the selected ChEMBL builder."""
    resource = get_chembl_builder_resource(builder_label_or_key)
    field = DEFAULT_CHEMBL_FIELDS_BY_RESOURCE[resource]
    entry = get_chembl_field_entry(builder_label_or_key, field)
    return {
        "field": get_chembl_builder_field_label(builder_label_or_key, field),
        "filter_type": entry.allowed_operators[0],
        "value": "",
    }


def build_chembl_builder_form_rows(
    builder_label_or_key: object,
    ui_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Convert visible ChEMBL builder rows to pure builder form rows."""
    return [
        {
            "field": get_chembl_builder_field_value(builder_label_or_key, row.get("field", "")),
            "filter_type": row.get("filter_type", ""),
            "value": row.get("value", ""),
        }
        for row in ui_rows
    ]


def get_dataset_modality_value(form_values: dict[str, object]) -> str:
    """Return the selected dataset modality as a workflow-v1 value."""
    return str(
        normalize_labeled_value(
            form_values.get("dataset.modality", "protein"),
            MODALITY_LABEL_TO_VALUE,
        )
    )


def get_dataset_interaction_type_value(form_values: dict[str, object]) -> str | None:
    """Return the selected interaction type as a workflow-v1 value."""
    value = normalize_labeled_value(
        form_values.get("dataset.interaction_type"),
        INTERACTION_TYPE_LABEL_TO_VALUE,
    )
    return str(value) if value else None


def should_show_interaction_type_selector(form_values: dict[str, object]) -> bool:
    """Return whether the dataset interaction type selector should be visible."""
    return get_dataset_modality_value(form_values) == "interaction"
