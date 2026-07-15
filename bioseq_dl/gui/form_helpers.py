"""NiceGUI-free helpers for the workflow YAML builder GUI.

Pure label<->value conversion, builder-field lookups, and mutable UI-row
factories used by the NiceGUI app. Kept free of ``nicegui`` so they can be
imported and tested without the GUI dependency installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

from bioseq_dl.core.workflow.chebi_query_catalog import get_chebi_query_builder_field_catalog
from bioseq_dl.core.workflow.chembl_query_catalog import get_chembl_query_builder_field_catalog
from bioseq_dl.core.workflow.pubchem_query_catalog import get_pubchem_query_builder_field_catalog
from bioseq_dl.core.workflow.query_field_catalog import get_uniprot_query_builder_field_catalog
from bioseq_dl.gui.query_builders.pubchem import (
    SIMILARITY_2D_CID_FIELD,
    normalize_pubchem_builder_threshold_state,
)
from bioseq_dl.gui.query_builders.registry import get_query_builder_choices
from bioseq_dl.gui.query_builders.uniprot import get_uniprot_query_builder_field_metadata
from bioseq_dl.gui.yaml_builder import (
    CHEBI_BUILDER_RESOURCE_BY_KEY,
    CHEMBL_BUILDER_RESOURCE_BY_KEY,
    INTERACTION_TYPE_LABEL_TO_VALUE,
    MODALITY_LABEL_TO_VALUE,
    PUBCHEM_BUILDER_RESOURCE_BY_KEY,
    QUERY_INPUT_MODE_LABEL_TO_VALUE,
    UNIPROT_MATCH_MODE_LABEL_TO_VALUE,
    get_labeled_option_default,
    normalize_labeled_value,
    normalize_query_builder_key,
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
DEFAULT_PUBCHEM_FIELDS_BY_RESOURCE = {
    "compound": "name",
    "structure": "smiles_substructure",
}
DEFAULT_CHEBI_FIELDS_BY_RESOURCE = {
    "entity": "name_contains",
}
PUBCHEM_SIMILARITY_FIELD = SIMILARITY_2D_CID_FIELD
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


def is_pubchem_builder_key(value: object) -> bool:
    """Return whether a GUI builder key or label selects a PubChem builder."""
    return get_query_builder_key(value) in PUBCHEM_BUILDER_RESOURCE_BY_KEY


def is_chebi_builder_key(value: object) -> bool:
    """Return whether a GUI builder key or label selects a ChEBI builder."""
    return get_query_builder_key(value) in CHEBI_BUILDER_RESOURCE_BY_KEY


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


def build_uniprot_builder_ui_rows(form_rows: object) -> list[dict[str, object]]:
    """Convert restored UniProt form rows to visible GUI row values."""
    if not isinstance(form_rows, list):
        return [make_uniprot_builder_ui_row()]
    return [
        {
            "connector": str(row.get("connector") or "") if index > 0 else "",
            "field": get_uniprot_builder_field_label(row.get("field", "")),
            "values": str(row.get("values") or ""),
            "match_mode": get_uniprot_match_mode_label(row.get("match_mode", "any")),
        }
        for index, row in enumerate(form_rows)
        if isinstance(row, dict)
    ] or [make_uniprot_builder_ui_row()]


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


def build_chembl_builder_ui_rows(
    builder_label_or_key: object,
    form_rows: object,
) -> list[dict[str, object]]:
    """Convert restored ChEMBL form rows to visible GUI row values."""
    if not isinstance(form_rows, list):
        return [make_chembl_builder_ui_row(builder_label_or_key)]
    return [
        {
            "field": get_chembl_builder_field_label(builder_label_or_key, row.get("field", "")),
            "filter_type": str(row.get("filter_type") or ""),
            "value": str(row.get("value") or ""),
        }
        for row in form_rows
        if isinstance(row, dict)
    ] or [make_chembl_builder_ui_row(builder_label_or_key)]


def get_pubchem_builder_resource(builder_label_or_key: object) -> str:
    """Return the PubChem resource for a selected builder key or label."""
    builder_key = get_query_builder_key(builder_label_or_key)
    return PUBCHEM_BUILDER_RESOURCE_BY_KEY[builder_key]


def get_active_pubchem_builder_label(builder_label_or_key: object) -> str:
    """Return a PubChem builder label, falling back to compound when another builder is active."""
    if is_pubchem_builder_key(builder_label_or_key):
        return str(builder_label_or_key)
    return get_query_builder_label("pubchem_compound")


def get_pubchem_field_catalog_for_builder(builder_label_or_key: object) -> dict[str, object]:
    """Return the PubChem field catalog for the selected builder."""
    return get_pubchem_query_builder_field_catalog(get_pubchem_builder_resource(builder_label_or_key))


def get_pubchem_builder_field_label(builder_label_or_key: object, field: object) -> str:
    """Return a visible PubChem field label."""
    catalog = get_pubchem_field_catalog_for_builder(builder_label_or_key)
    field_text = str(field)
    if field_text in catalog:
        return f"{catalog[field_text].label} ({field_text})"
    return field_text


def get_pubchem_builder_field_value(builder_label_or_key: object, label_or_value: object) -> str:
    """Return an internal PubChem field key for a visible field label or field key."""
    catalog = get_pubchem_field_catalog_for_builder(builder_label_or_key)
    text = str(label_or_value)
    for key, entry in catalog.items():
        if text == f"{entry.label} ({key})":
            return key
    return text


def get_pubchem_field_entry(builder_label_or_key: object, label_or_value: object) -> object:
    """Return PubChem catalog metadata for a visible field label or field key."""
    catalog = get_pubchem_field_catalog_for_builder(builder_label_or_key)
    field = get_pubchem_builder_field_value(builder_label_or_key, label_or_value)
    return catalog[field]


def get_pubchem_field_options(builder_label_or_key: object) -> list[str]:
    """Return visible PubChem field options for the selected builder."""
    catalog = get_pubchem_field_catalog_for_builder(builder_label_or_key)
    return [get_pubchem_builder_field_label(builder_label_or_key, key) for key in catalog]


def get_pubchem_field_help(builder_label_or_key: object, label_or_value: object) -> str:
    """Return compact PubChem field help."""
    entry = get_pubchem_field_entry(builder_label_or_key, label_or_value)
    examples = ", ".join(entry.examples)
    modes = ", ".join(entry.supported_modes)
    return f"{entry.description} Examples: {examples}. Modes: {modes}"


def is_pubchem_similarity_field(builder_label_or_key: object, label_or_value: object) -> bool:
    """Return whether a PubChem field selection needs the threshold control."""
    return get_pubchem_builder_field_value(builder_label_or_key, label_or_value) == PUBCHEM_SIMILARITY_FIELD


def make_pubchem_builder_ui_row(builder_label_or_key: object) -> dict[str, object]:
    """Return one mutable UI row for the selected PubChem builder."""
    resource = get_pubchem_builder_resource(builder_label_or_key)
    field = DEFAULT_PUBCHEM_FIELDS_BY_RESOURCE[resource]
    return {
        "field": get_pubchem_builder_field_label(builder_label_or_key, field),
        "value": "",
        "threshold": normalize_pubchem_builder_threshold_state(field, None),
    }


def build_pubchem_builder_form_row(
    builder_label_or_key: object,
    ui_row: dict[str, object],
) -> dict[str, object]:
    """Convert a visible PubChem builder row to pure builder form data."""
    field = get_pubchem_builder_field_value(builder_label_or_key, ui_row.get("field", ""))
    return {
        "field": field,
        "value": ui_row.get("value", ""),
        "threshold": normalize_pubchem_builder_threshold_state(field, ui_row.get("threshold")),
    }


def build_pubchem_builder_ui_row(
    builder_label_or_key: object,
    form_row: object,
) -> dict[str, object]:
    """Convert a restored PubChem form row to visible GUI row values."""
    if not isinstance(form_row, dict):
        return make_pubchem_builder_ui_row(builder_label_or_key)
    field = form_row.get("field", "")
    field_value = get_pubchem_builder_field_value(builder_label_or_key, field)
    return {
        "field": get_pubchem_builder_field_label(builder_label_or_key, field_value),
        "value": str(form_row.get("value") or ""),
        "threshold": normalize_pubchem_builder_threshold_state(
            field_value,
            form_row.get("threshold"),
        ),
    }


def get_chebi_builder_resource(builder_label_or_key: object) -> str:
    """Return the ChEBI resource for a selected builder key or label."""
    builder_key = get_query_builder_key(builder_label_or_key)
    return CHEBI_BUILDER_RESOURCE_BY_KEY[builder_key]


def get_active_chebi_builder_label(builder_label_or_key: object) -> str:
    """Return a ChEBI builder label, falling back to entity when another builder is active."""
    if is_chebi_builder_key(builder_label_or_key):
        return str(builder_label_or_key)
    return get_query_builder_label("chebi_entity")


def get_chebi_field_catalog_for_builder(builder_label_or_key: object) -> dict[str, object]:
    """Return the ChEBI field catalog for the selected builder."""
    return get_chebi_query_builder_field_catalog(get_chebi_builder_resource(builder_label_or_key))


def get_chebi_builder_field_label(builder_label_or_key: object, field: object) -> str:
    """Return a visible ChEBI field label."""
    catalog = get_chebi_field_catalog_for_builder(builder_label_or_key)
    field_text = str(field)
    if field_text in catalog:
        return f"{catalog[field_text].label} ({field_text})"
    return field_text


def get_chebi_builder_field_value(builder_label_or_key: object, label_or_value: object) -> str:
    """Return an internal ChEBI field key for a visible field label or field key."""
    catalog = get_chebi_field_catalog_for_builder(builder_label_or_key)
    text = str(label_or_value)
    for key, entry in catalog.items():
        if text == f"{entry.label} ({key})":
            return key
    return text


def get_chebi_field_entry(builder_label_or_key: object, label_or_value: object) -> object:
    """Return ChEBI catalog metadata for a visible field label or field key."""
    catalog = get_chebi_field_catalog_for_builder(builder_label_or_key)
    field = get_chebi_builder_field_value(builder_label_or_key, label_or_value)
    return catalog[field]


def get_chebi_field_options(builder_label_or_key: object) -> list[str]:
    """Return visible ChEBI field options for the selected builder."""
    catalog = get_chebi_field_catalog_for_builder(builder_label_or_key)
    return [get_chebi_builder_field_label(builder_label_or_key, key) for key in catalog]


def get_chebi_field_help(builder_label_or_key: object, label_or_value: object) -> str:
    """Return compact ChEBI field help."""
    entry = get_chebi_field_entry(builder_label_or_key, label_or_value)
    examples = ", ".join(entry.examples)
    operators = ", ".join(entry.supported_operators)
    return f"{entry.description} Examples: {examples}. Operators: {operators}"


def make_chebi_builder_ui_row(builder_label_or_key: object) -> dict[str, object]:
    """Return one mutable UI row for the selected ChEBI builder."""
    resource = get_chebi_builder_resource(builder_label_or_key)
    field = DEFAULT_CHEBI_FIELDS_BY_RESOURCE[resource]
    return {
        "field": get_chebi_builder_field_label(builder_label_or_key, field),
        "value": "",
    }


def build_chebi_builder_form_row(
    builder_label_or_key: object,
    ui_row: dict[str, object],
) -> dict[str, object]:
    """Convert a visible ChEBI builder row to pure builder form data."""
    return {
        "field": get_chebi_builder_field_value(builder_label_or_key, ui_row.get("field", "")),
        "value": ui_row.get("value", ""),
    }


def build_chebi_builder_ui_row(
    builder_label_or_key: object,
    form_row: object,
) -> dict[str, object]:
    """Convert a restored ChEBI form row to visible GUI row values."""
    if not isinstance(form_row, dict):
        return make_chebi_builder_ui_row(builder_label_or_key)
    return {
        "field": get_chebi_builder_field_label(builder_label_or_key, form_row.get("field", "")),
        "value": str(form_row.get("value") or ""),
    }


def build_gui_query_builder_state_from_loaded_form(form_values: Mapping[str, object]) -> dict[str, object]:
    """Return the GUI query-builder state implied by loaded form values."""
    query_input_mode = get_labeled_option_default(
        normalize_query_input_mode(form_values.get("query.input_mode")),
        QUERY_INPUT_MODE_LABEL_TO_VALUE,
    )
    builder_key = normalize_query_builder_key(form_values.get("query.builder.key"))
    builder_label = get_query_builder_label(builder_key)
    uniprot_rows = [make_uniprot_builder_ui_row()]
    chembl_rows = [make_chembl_builder_ui_row(get_query_builder_label("chembl_target"))]
    pubchem_row = make_pubchem_builder_ui_row(get_query_builder_label("pubchem_compound"))
    chebi_row = make_chebi_builder_ui_row(get_query_builder_label("chebi_entity"))

    if normalize_query_input_mode(query_input_mode) == "advanced_builder":
        if builder_key == "uniprot":
            uniprot_rows = build_uniprot_builder_ui_rows(
                form_values.get("query.uniprot_builder.rows")
            )
        elif builder_key in CHEMBL_BUILDER_RESOURCE_BY_KEY:
            chembl_rows = build_chembl_builder_ui_rows(
                builder_label,
                form_values.get("query.chembl_builder.rows"),
            )
        elif builder_key in PUBCHEM_BUILDER_RESOURCE_BY_KEY:
            pubchem_row = build_pubchem_builder_ui_row(
                builder_label,
                form_values.get("query.pubchem_builder.row"),
            )
        elif builder_key in CHEBI_BUILDER_RESOURCE_BY_KEY:
            chebi_row = build_chebi_builder_ui_row(
                builder_label,
                form_values.get("query.chebi_builder.row"),
            )

    return {
        "query_input_mode": query_input_mode,
        "builder_key": builder_key,
        "builder_label": builder_label,
        "uniprot_rows": uniprot_rows,
        "chembl_rows": chembl_rows,
        "pubchem_row": pubchem_row,
        "chebi_row": chebi_row,
    }


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
