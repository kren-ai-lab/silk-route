"""NiceGUI app for generating workflow-v1 YAML descriptors."""

from __future__ import annotations

from functools import partial
from typing import Any

import yaml
from nicegui import ui

from bioseq_dl.core.workflow.chebi_query_catalog import get_chebi_query_builder_field_catalog
from bioseq_dl.core.workflow.chembl_query_catalog import get_chembl_query_builder_field_catalog
from bioseq_dl.core.workflow.pubchem_query_catalog import get_pubchem_query_builder_field_catalog
from bioseq_dl.core.workflow.query_field_catalog import get_uniprot_query_builder_field_catalog
from bioseq_dl.gui.query_builders.chebi import (
    build_chebi_friendly_query,
    build_chebi_interpreted_query,
)
from bioseq_dl.gui.query_builders.chembl import (
    build_chembl_friendly_query,
    build_chembl_interpreted_query,
)
from bioseq_dl.gui.query_builders.pubchem import (
    build_pubchem_friendly_query,
    build_pubchem_interpreted_query,
)
from bioseq_dl.gui.query_builders.registry import (
    get_compatible_query_builder_choices,
    get_query_builder_choices,
)
from bioseq_dl.gui.query_builders.uniprot import (
    build_uniprot_friendly_query,
    build_uniprot_interpreted_query,
    get_uniprot_query_builder_field_metadata,
)
from bioseq_dl.gui.yaml_builder import (
    CHEBI_BUILDER_RESOURCE_BY_KEY,
    CHEMBL_BUILDER_RESOURCE_BY_KEY,
    EXPORT_FORMAT_LABEL_TO_VALUE,
    INTERACTION_TYPE_LABEL_TO_VALUE,
    MODALITY_LABEL_TO_VALUE,
    OUTPUT_DIRECTORY_MODE_LABEL_TO_VALUE,
    PUBCHEM_BUILDER_RESOURCE_BY_KEY,
    QUERY_INPUT_MODE_LABEL_TO_VALUE,
    UNIPROT_MATCH_MODE_LABEL_TO_VALUE,
    WORKFLOW_MODE_LABEL_TO_VALUE,
    build_chebi_builder_rows_from_form,
    build_chembl_builder_rows_from_form,
    build_pubchem_builder_row_from_form,
    build_uniprot_builder_rows_from_form,
    build_workflow_descriptor,
    build_workflow_filename,
    get_labeled_option_default,
    load_workflow_yaml_to_form_values,
    normalize_labeled_value,
    normalize_query_builder_key,
    normalize_query_input_mode,
    render_workflow_yaml,
    validate_generated_descriptor,
    workflow_yaml_gui_form_defaults,
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
    "entity": "name",
    "ontology": "ontology_relation",
    "structure": "substructure",
}
DEFAULT_CHEBI_OPERATORS_BY_FIELD = {
    "chebi_id": "exact",
    "name": "contains",
    "formula": "exact",
    "average_mass": "range",
    "monoisotopic_mass": "range",
    "charge": "range",
    "database_xref": "exact",
    "star": "exact",
    "ontology_relation": "exact",
    "ontology_term": "exact",
    "connectivity": "connectivity",
    "substructure": "substructure",
    "similarity": "similarity",
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


def is_uniprot_builder_query_mode(value: object) -> bool:
    """Return whether a GUI query mode value means advanced UniProt builder entry."""
    return normalize_query_input_mode(value) == "advanced_builder"


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


def make_pubchem_builder_ui_row(builder_label_or_key: object) -> dict[str, object]:
    """Return one mutable UI row for the selected PubChem builder."""
    resource = get_pubchem_builder_resource(builder_label_or_key)
    field = DEFAULT_PUBCHEM_FIELDS_BY_RESOURCE[resource]
    return {
        "field": get_pubchem_builder_field_label(builder_label_or_key, field),
        "value": "",
        "threshold": 80 if field == "similarity_2d" else "",
    }


def build_pubchem_builder_form_row(
    builder_label_or_key: object,
    ui_row: dict[str, object],
) -> dict[str, object]:
    """Convert a visible PubChem builder row to pure builder form data."""
    return {
        "field": get_pubchem_builder_field_value(builder_label_or_key, ui_row.get("field", "")),
        "value": ui_row.get("value", ""),
        "threshold": ui_row.get("threshold", ""),
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


def get_chebi_operator_options(builder_label_or_key: object, label_or_value: object) -> list[str]:
    """Return operator options for one selected ChEBI field."""
    entry = get_chebi_field_entry(builder_label_or_key, label_or_value)
    return list(entry.supported_operators)


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
        "operator": DEFAULT_CHEBI_OPERATORS_BY_FIELD[field],
        "value": "",
        "secondary_value": "",
    }


def build_chebi_builder_form_rows(
    builder_label_or_key: object,
    ui_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Convert visible ChEBI builder rows to pure builder form rows."""
    return [
        {
            "field": get_chebi_builder_field_value(builder_label_or_key, row.get("field", "")),
            "operator": row.get("operator", ""),
            "value": row.get("value", ""),
            "secondary_value": row.get("secondary_value", ""),
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


class WorkflowYamlBuilderApp:
    """Render and manage the BioSeqDownloader workflow YAML builder."""

    def __init__(self) -> None:
        """Initialize app state for form binding and status output."""
        self.form_values = workflow_yaml_gui_form_defaults()
        self.form_values["query.builder.key"] = get_query_builder_label(self.form_values["query.builder.key"])
        self.uniprot_builder_rows = [make_uniprot_builder_ui_row()]
        self.chembl_builder_rows = [make_chembl_builder_ui_row(get_query_builder_label("chembl_target"))]
        self.pubchem_builder_row = make_pubchem_builder_ui_row(get_query_builder_label("pubchem_compound"))
        self.chebi_builder_rows = [make_chebi_builder_ui_row(get_query_builder_label("chebi_entity"))]
        self.friendly_query_preview: Any = None
        self.interpreted_query_preview: Any = None
        self.query_builder_select: Any = None
        self.interaction_type_select: Any = None
        self.workflow_upload: Any = None
        self.loaded_workflow_filename: str | None = None
        self.loaded_workflow_upload_status: str | None = None
        self.loaded_workflow_upload_message: str | None = None
        self.loaded_workflow_upload_warnings: list[str] = []
        self.builder_availability_message: Any = None
        self.yaml_output: Any = None
        self.status: Any = None

    def build(self) -> None:
        """Build the NiceGUI page."""
        ui.page_title("BioSeqDownloader Workflow YAML Builder")
        with ui.column().classes("w-full max-w-5xl mx-auto gap-4 p-4"):
            ui.label("BioSeqDownloader Workflow YAML Builder").classes("text-2xl font-semibold")
            ui.label(
                "Use this page to prepare workflow-v1 YAML descriptors for BioSeqDownloader. "
                "Run the workflow later from the CLI."
            ).classes("text-sm text-gray-700")
            self.build_load_controls()
            self.build_dataset_controls()
            self.build_query_controls()
            self.build_execution_controls()
            self.build_harmonization_controls()
            self.build_export_controls()
            self.build_preview_controls()

    def build_load_controls(self) -> None:
        """Build upload controls for loading an existing workflow YAML file."""
        with ui.expansion("Load existing workflow YAML", value=False).classes("w-full"):
            ui.label(
                "Upload a workflow-v1 .yml or .yaml file to populate supported form fields. "
                "When a file is loaded, the saved query text is shown in Manual query mode."
            ).classes("text-sm text-gray-700")
            ui.label(
                "Upload one .yml or .yaml file. Uploading another file replaces the current loaded workflow."
            ).classes("text-sm text-gray-700")
            self.workflow_upload = (
                ui.upload(
                    label="Select workflow YAML",
                    on_upload=self.load_yaml_upload,
                    max_files=1,
                    auto_upload=True,
                )
                .props('accept=".yml,.yaml"')
                .classes("w-full")
            )
            self.build_upload_status_card()

    @ui.refreshable
    def build_upload_status_card(self) -> None:
        """Build the persistent workflow upload status card."""
        if self.loaded_workflow_upload_status is None:
            return
        is_success = self.loaded_workflow_upload_status == "success"
        title = "Loaded workflow YAML" if is_success else "Could not load workflow YAML"
        tone_classes = (
            "border-l-4 border-green-500 bg-green-50" if is_success else "border-l-4 border-red-500 bg-red-50"
        )
        with ui.card().classes(f"w-full gap-2 rounded-md {tone_classes}"):
            ui.label(title).classes("text-base font-semibold")
            filename = self.loaded_workflow_filename or "workflow YAML file"
            status_text = (
                f"{filename} loaded successfully." if is_success else f"{filename} could not be loaded."
            )
            ui.label(status_text).classes("text-sm font-medium")
            if self.loaded_workflow_upload_message:
                ui.label(self.loaded_workflow_upload_message).classes("text-sm text-gray-700")
            if self.loaded_workflow_upload_warnings:
                ui.label("Load notes").classes("text-sm font-semibold text-orange-800")
                for warning in self.loaded_workflow_upload_warnings:
                    ui.label(f"- {warning}").classes("text-sm text-orange-800")

    def build_dataset_controls(self) -> None:
        """Build dataset form controls."""
        with ui.expansion("Dataset", value=True).classes("w-full"):
            with ui.grid(columns=2).classes("w-full gap-3"):
                (
                    ui.input("Dataset name")
                    .props("clearable")
                    .bind_value(self.form_values, "dataset.name")
                    .tooltip(
                        "A short identifier for this dataset. It can also be used to derive "
                        "default output names."
                    )
                )
                (
                    ui.select(list(MODALITY_LABEL_TO_VALUE), label="Modality")
                    .bind_value(self.form_values, "dataset.modality")
                    .on_value_change(self.handle_dataset_builder_context_change)
                    .tooltip("The type of biomolecular data described by this workflow.")
                )
                (
                    ui.select(list(WORKFLOW_MODE_LABEL_TO_VALUE), label="Workflow mode")
                    .bind_value(self.form_values, "dataset.mode")
                    .tooltip(
                        "Controls how query.value is interpreted. Query First uses one main query; "
                        "Query Composition groups multiple query fragments with labels."
                    )
                )
                self.interaction_type_select = (
                    ui.select(list(INTERACTION_TYPE_LABEL_TO_VALUE), label="Interaction type")
                    .bind_value(self.form_values, "dataset.interaction_type")
                    .on_value_change(self.handle_dataset_builder_context_change)
                    .tooltip(
                        "Only needed when Modality is Interaction. Choose No interaction for "
                        "protein or compound datasets."
                    )
                )
                self.update_interaction_type_visibility(update_select=False)
            (
                ui.textarea("Dataset description")
                .bind_value(self.form_values, "dataset.description")
                .classes("w-full")
                .tooltip("Optional human-readable description stored in the YAML descriptor.")
            )

    def build_query_controls(self) -> None:
        """Build query form controls."""
        with ui.expansion("Query", value=True).classes("w-full"):
            ui.label(
                "Choose manual query entry or build an interpreted query. "
                "Generated YAML always stores only query.value."
            ).classes("text-sm text-gray-700")
            (
                ui.select(list(QUERY_INPUT_MODE_LABEL_TO_VALUE), label="Query input mode")
                .bind_value(self.form_values, "query.input_mode")
                .on_value_change(self.update_builder_previews)
                .tooltip("Manual mode writes query.value directly. Advanced builder mode builds it.")
            )
            with ui.column().classes("w-full gap-2") as manual_query_panel:
                (
                    ui.textarea("Executable query value")
                    .bind_value(self.form_values, "query.value")
                    .classes("w-full")
                    .tooltip("The executable query string stored as query.value.")
                )
            manual_query_panel.bind_visibility_from(
                self.form_values,
                "query.input_mode",
                backward=is_manual_query_mode,
            )

            with ui.column().classes("w-full gap-3") as builder_panel:
                ui.label(
                    "Available builders depend on the selected dataset modality and interaction type."
                ).classes("text-sm text-gray-700")
                self.builder_availability_message = ui.label("").classes("text-sm text-orange-700")
                self.query_builder_select = (
                    ui.select(self.get_compatible_query_builder_labels(), label="Query builder")
                    .bind_value(self.form_values, "query.builder.key")
                    .on_value_change(self.handle_query_builder_change)
                    .tooltip("Choose the database-specific query builder.")
                )
                with ui.column().classes("w-full gap-3") as uniprot_builder_panel:
                    self.build_uniprot_builder_controls()
                uniprot_builder_panel.bind_visibility_from(
                    self.form_values,
                    "query.builder.key",
                    backward=is_uniprot_builder_key,
                )
                with ui.column().classes("w-full gap-3") as chembl_builder_panel:
                    self.build_chembl_builder_controls()
                chembl_builder_panel.bind_visibility_from(
                    self.form_values,
                    "query.builder.key",
                    backward=is_chembl_builder_key,
                )
                with ui.column().classes("w-full gap-3") as pubchem_builder_panel:
                    self.build_pubchem_builder_controls()
                pubchem_builder_panel.bind_visibility_from(
                    self.form_values,
                    "query.builder.key",
                    backward=is_pubchem_builder_key,
                )
                with ui.column().classes("w-full gap-3") as chebi_builder_panel:
                    self.build_chebi_builder_controls()
                chebi_builder_panel.bind_visibility_from(
                    self.form_values,
                    "query.builder.key",
                    backward=is_chebi_builder_key,
                )
                self.friendly_query_preview = (
                    ui.textarea("Friendly query preview").classes("w-full font-mono").props("readonly rows=3")
                )
                self.interpreted_query_preview = (
                    ui.textarea("Interpreted query.value preview")
                    .classes("w-full font-mono")
                    .props("readonly rows=3")
                )
                self.refresh_query_builder_options(refresh_rows=False)
            builder_panel.bind_visibility_from(
                self.form_values,
                "query.input_mode",
                backward=is_advanced_builder_query_mode,
            )

            with ui.grid(columns=2).classes("w-full gap-3"):
                (
                    ui.input("Return fields")
                    .props('clearable placeholder="accession, protein_name, organism_name, sequence"')
                    .bind_value(self.form_values, "query.fields")
                    .tooltip(
                        "Optional output/request fields. This is separate from advanced builder "
                        "search fields. Enter comma-separated values."
                    )
                )
                (
                    ui.input("Cross-reference fields")
                    .props('clearable placeholder="xref_alphafolddb, xref_pdb, xref_string"')
                    .bind_value(self.form_values, "query.crossref_fields")
                    .tooltip(
                        "Optional database cross-references used by supported enrichment logic. "
                        "This is separate from advanced builder search fields. Enter "
                        "comma-separated values."
                    )
                )
                (
                    ui.checkbox("Include UniProt isoforms")
                    .bind_value(self.form_values, "query.include_isoform")
                    .tooltip("Whether UniProt isoforms should be included when supported by the workflow.")
                )

    def build_uniprot_builder_controls(self) -> None:
        """Build UniProt-specific advanced builder controls."""
        with ui.column().classes("w-full gap-3"):
            ui.label(
                "Build a UniProt-style query using rows. Each row selects a query field, "
                "one or more comma-separated values, and how those values are matched. "
                "The final interpreted query is stored as query.value in the YAML."
            ).classes("text-sm text-gray-700")
            ui.label(
                "The builder prepares the query text only. UniProt validation happens later "
                "when the workflow runs."
            ).classes("text-sm text-gray-700")
            ui.label(
                "Connector combines this row with the previous row. Use AND when both "
                "conditions should be required; use OR when either condition can match."
            ).classes("text-sm text-gray-700")
            ui.label(
                "Match mode combines comma-separated values inside one row. Any means at "
                "least one value can match. All means every value must match. Not means the "
                "values are excluded."
            ).classes("text-sm text-gray-700")
            self.build_uniprot_builder_rows()
            with ui.row().classes("items-center gap-3"):
                ui.button("Add condition", on_click=self.add_uniprot_builder_row)
                ui.button("Update query preview", on_click=self.update_builder_previews)

    @ui.refreshable
    def build_uniprot_builder_rows(self) -> None:
        """Build advanced UniProt query builder row controls."""
        for index, row in enumerate(self.uniprot_builder_rows):
            field_help = get_uniprot_builder_field_help(row.get("field", ""))
            values_placeholder = get_uniprot_builder_field_placeholder(row.get("field", ""))
            with ui.row().classes("w-full items-end gap-3"):
                if index == 0:
                    ui.input("First condition").props('readonly placeholder=""').classes("w-32")
                else:
                    (
                        ui.select(["AND", "OR"], label="Connector")
                        .bind_value(row, "connector")
                        .on_value_change(self.update_builder_previews)
                        .classes("w-28")
                        .tooltip("Connector controls how this row is combined with the previous row.")
                    )
                (
                    ui.select(list(UNIPROT_BUILDER_FIELD_LABEL_TO_VALUE), label="Field")
                    .bind_value(row, "field")
                    .on_value_change(partial(self.handle_uniprot_builder_field_change, index))
                    .classes("min-w-56")
                    .tooltip(field_help)
                )
                (
                    ui.input("Values", placeholder=values_placeholder)
                    .props("clearable")
                    .bind_value(row, "values")
                    .on_value_change(self.update_builder_previews)
                    .classes("grow")
                    .tooltip("Enter one or more comma-separated values for the selected field.")
                )
                (
                    ui.select(list(UNIPROT_MATCH_MODE_LABEL_TO_VALUE), label="Match mode")
                    .bind_value(row, "match_mode")
                    .on_value_change(self.update_builder_previews)
                    .classes("w-32")
                    .tooltip("Match mode controls how comma-separated values inside this row are combined.")
                )
                if index > 0:
                    ui.button("Remove", on_click=partial(self.remove_uniprot_builder_row, index))
            ui.label(field_help).classes("text-xs text-gray-600")

    def add_uniprot_builder_row(self) -> None:
        """Add one advanced UniProt builder condition row."""
        self.uniprot_builder_rows.append(make_uniprot_builder_ui_row(connector="AND"))
        self.sync_builder_rows_to_form()
        self.build_uniprot_builder_rows.refresh()
        self.update_builder_previews()

    def remove_uniprot_builder_row(self, index: int) -> None:
        """Remove one advanced UniProt builder condition row."""
        if index <= 0 or index >= len(self.uniprot_builder_rows):
            return
        self.uniprot_builder_rows.pop(index)
        self.sync_builder_rows_to_form()
        self.build_uniprot_builder_rows.refresh()
        self.update_builder_previews()

    def handle_uniprot_builder_field_change(self, _index: int, *_args: object) -> None:
        """Refresh field-specific help after a builder field changes."""
        self.sync_builder_rows_to_form()
        self.build_uniprot_builder_rows.refresh()
        self.update_builder_previews()

    def build_chembl_builder_controls(self) -> None:
        """Build ChEMBL-specific advanced builder controls."""
        with ui.column().classes("w-full gap-3"):
            ui.label(
                "ChEMBL builders use resource-specific filters. Rows are combined with AND. "
                "Use the IN filter type for multiple allowed values in one field."
            ).classes("text-sm text-gray-700")
            ui.label(
                "The builder prepares the ChEMBL query text only. ChEMBL validation happens "
                "later when the workflow runs."
            ).classes("text-sm text-gray-700")
            self.build_chembl_builder_rows()
            with ui.row().classes("items-center gap-3"):
                ui.button("Add condition", on_click=self.add_chembl_builder_row)
                ui.button("Update query preview", on_click=self.update_builder_previews)

    @ui.refreshable
    def build_chembl_builder_rows(self) -> None:
        """Build ChEMBL query builder row controls."""
        builder_label = get_active_chembl_builder_label(self.form_values["query.builder.key"])
        for index, row in enumerate(self.chembl_builder_rows):
            field_help = get_chembl_field_help(builder_label, row.get("field", ""))
            values_placeholder = str(get_chembl_field_entry(builder_label, row.get("field", "")).placeholder)
            filter_type_options = get_chembl_filter_type_options(builder_label, row.get("field", ""))
            if row.get("filter_type") not in filter_type_options:
                row["filter_type"] = filter_type_options[0]
            with ui.row().classes("w-full items-end gap-3"):
                (
                    ui.select(get_chembl_field_options(builder_label), label="Field")
                    .bind_value(row, "field")
                    .on_value_change(partial(self.handle_chembl_builder_field_change, index))
                    .classes("min-w-72")
                    .tooltip(field_help)
                )
                (
                    ui.select(filter_type_options, label="Filter type")
                    .bind_value(row, "filter_type")
                    .on_value_change(self.update_builder_previews)
                    .classes("w-40")
                    .tooltip("Filter type controls the ChEMBL field suffix/operator.")
                )
                (
                    ui.input("Value", placeholder=values_placeholder)
                    .props("clearable")
                    .bind_value(row, "value")
                    .on_value_change(self.update_builder_previews)
                    .classes("grow")
                    .tooltip("Enter the value for this ChEMBL filter.")
                )
                if index > 0:
                    ui.button("Remove", on_click=partial(self.remove_chembl_builder_row, index))
            ui.label(field_help).classes("text-xs text-gray-600")

    def add_chembl_builder_row(self) -> None:
        """Add one ChEMBL builder condition row."""
        self.chembl_builder_rows.append(make_chembl_builder_ui_row(self.form_values["query.builder.key"]))
        self.sync_builder_rows_to_form()
        self.build_chembl_builder_rows.refresh()
        self.update_builder_previews()

    def remove_chembl_builder_row(self, index: int) -> None:
        """Remove one ChEMBL builder condition row."""
        if index <= 0 or index >= len(self.chembl_builder_rows):
            return
        self.chembl_builder_rows.pop(index)
        self.sync_builder_rows_to_form()
        self.build_chembl_builder_rows.refresh()
        self.update_builder_previews()

    def handle_chembl_builder_field_change(self, _index: int, *_args: object) -> None:
        """Refresh ChEMBL field-specific filter options and help."""
        self.sync_builder_rows_to_form()
        self.build_chembl_builder_rows.refresh()
        self.update_builder_previews()

    def build_pubchem_builder_controls(self) -> None:
        """Build PubChem-specific advanced builder controls."""
        with ui.column().classes("w-full gap-3"):
            ui.label(
                "PubChem builders help prepare compound lookup and structure-search descriptors. "
                "Workflow execution for PubChem will be added in a later phase."
            ).classes("text-sm text-gray-700")
            self.build_pubchem_builder_row()
            with ui.row().classes("items-center gap-3"):
                ui.button("Update query preview", on_click=self.update_builder_previews)

    @ui.refreshable
    def build_pubchem_builder_row(self) -> None:
        """Build PubChem query builder row controls."""
        builder_label = get_active_pubchem_builder_label(self.form_values["query.builder.key"])
        row = self.pubchem_builder_row
        field_help = get_pubchem_field_help(builder_label, row.get("field", ""))
        values_placeholder = str(get_pubchem_field_entry(builder_label, row.get("field", "")).placeholder)
        field_value = get_pubchem_builder_field_value(builder_label, row.get("field", ""))
        with ui.row().classes("w-full items-end gap-3"):
            (
                ui.select(get_pubchem_field_options(builder_label), label="Field")
                .bind_value(row, "field")
                .on_value_change(self.handle_pubchem_builder_field_change)
                .classes("min-w-72")
                .tooltip(field_help)
            )
            (
                ui.input("Value", placeholder=values_placeholder)
                .props("clearable")
                .bind_value(row, "value")
                .on_value_change(self.update_builder_previews)
                .classes("grow")
                .tooltip("Enter the lookup or structure value for this PubChem query.")
            )
            if field_value == "similarity_2d":
                (
                    ui.number("Threshold", min=0, max=100, step=1)
                    .bind_value(row, "threshold")
                    .on_value_change(self.update_builder_previews)
                    .classes("w-36")
                    .tooltip("2-D similarity threshold from 0 to 100.")
                )
        ui.label(field_help).classes("text-xs text-gray-600")

    def handle_pubchem_builder_field_change(self, *_args: object) -> None:
        """Refresh PubChem field-specific controls and help."""
        builder_label = get_active_pubchem_builder_label(self.form_values["query.builder.key"])
        field = get_pubchem_builder_field_value(builder_label, self.pubchem_builder_row.get("field", ""))
        if field == "similarity_2d" and not self.pubchem_builder_row.get("threshold"):
            self.pubchem_builder_row["threshold"] = 80
        self.sync_builder_rows_to_form()
        self.build_pubchem_builder_row.refresh()
        self.update_builder_previews()

    def build_chebi_builder_controls(self) -> None:
        """Build ChEBI-specific advanced builder controls."""
        with ui.column().classes("w-full gap-3"):
            ui.label(
                "ChEBI builders help prepare entity, ontology, and structure descriptors. "
                "Workflow execution for ChEBI will be added in a later phase."
            ).classes("text-sm text-gray-700")
            self.build_chebi_builder_rows()
            with ui.row().classes("items-center gap-3"):
                active_builder_label = get_active_chebi_builder_label(self.form_values["query.builder.key"])
                if get_chebi_builder_resource(active_builder_label) == "entity":
                    ui.button("Add condition", on_click=self.add_chebi_builder_row)
                ui.button("Update query preview", on_click=self.update_builder_previews)

    @ui.refreshable
    def build_chebi_builder_rows(self) -> None:
        """Build ChEBI query builder row controls."""
        builder_label = get_active_chebi_builder_label(self.form_values["query.builder.key"])
        resource = get_chebi_builder_resource(builder_label)
        for index, row in enumerate(self.chebi_builder_rows):
            field_help = get_chebi_field_help(builder_label, row.get("field", ""))
            values_placeholder = str(get_chebi_field_entry(builder_label, row.get("field", "")).placeholder)
            operator_options = get_chebi_operator_options(builder_label, row.get("field", ""))
            if row.get("operator") not in operator_options:
                row["operator"] = operator_options[0]
            with ui.row().classes("w-full items-end gap-3"):
                if resource == "ontology":
                    (
                        ui.input("Relation", placeholder=values_placeholder)
                        .props("clearable")
                        .bind_value(row, "value")
                        .on_value_change(self.update_builder_previews)
                        .classes("grow")
                        .tooltip("Enter the ChEBI ontology relation.")
                    )
                else:
                    (
                        ui.select(get_chebi_field_options(builder_label), label="Field")
                        .bind_value(row, "field")
                        .on_value_change(partial(self.handle_chebi_builder_field_change, index))
                        .classes("min-w-72")
                        .tooltip(field_help)
                    )
                    (
                        ui.select(operator_options, label="Operator")
                        .bind_value(row, "operator")
                        .on_value_change(self.update_builder_previews)
                        .classes("w-40")
                        .tooltip("Operator controls the ChEBI search parameter.")
                    )
                    (
                        ui.input("Value", placeholder=values_placeholder)
                        .props("clearable")
                        .bind_value(row, "value")
                        .on_value_change(self.update_builder_previews)
                        .classes("grow")
                        .tooltip("Enter the value for this ChEBI query.")
                    )
                if resource == "ontology":
                    (
                        ui.input("Term", placeholder="metabolite")
                        .props("clearable")
                        .bind_value(row, "secondary_value")
                        .on_value_change(self.update_builder_previews)
                        .classes("grow")
                        .tooltip("Enter the ontology term paired with the relation.")
                    )
                if resource == "entity" and index > 0:
                    ui.button("Remove", on_click=partial(self.remove_chebi_builder_row, index))
            ui.label(field_help).classes("text-xs text-gray-600")

    def add_chebi_builder_row(self) -> None:
        """Add one ChEBI entity builder condition row."""
        self.chebi_builder_rows.append(make_chebi_builder_ui_row(self.form_values["query.builder.key"]))
        self.sync_builder_rows_to_form()
        self.build_chebi_builder_rows.refresh()
        self.update_builder_previews()

    def remove_chebi_builder_row(self, index: int) -> None:
        """Remove one ChEBI entity builder condition row."""
        if index <= 0 or index >= len(self.chebi_builder_rows):
            return
        self.chebi_builder_rows.pop(index)
        self.sync_builder_rows_to_form()
        self.build_chebi_builder_rows.refresh()
        self.update_builder_previews()

    def handle_chebi_builder_field_change(self, _index: int, *_args: object) -> None:
        """Refresh ChEBI field-specific operator options and help."""
        self.sync_builder_rows_to_form()
        self.build_chebi_builder_rows.refresh()
        self.update_builder_previews()

    def handle_query_builder_change(self, *_args: object) -> None:
        """Refresh builder-specific controls after the selected builder changes."""
        builder_label = self.form_values["query.builder.key"]
        if is_chembl_builder_key(builder_label):
            self.chembl_builder_rows = [make_chembl_builder_ui_row(builder_label)]
            self.build_chembl_builder_rows.refresh()
        if is_pubchem_builder_key(builder_label):
            self.pubchem_builder_row = make_pubchem_builder_ui_row(builder_label)
            self.build_pubchem_builder_row.refresh()
        if is_chebi_builder_key(builder_label):
            self.chebi_builder_rows = [make_chebi_builder_ui_row(builder_label)]
            self.build_chebi_builder_rows.refresh()
        self.sync_builder_rows_to_form()
        self.update_builder_previews()

    def get_compatible_query_builder_labels(self) -> list[str]:
        """Return visible labels for builders compatible with current dataset settings."""
        choices = get_compatible_query_builder_choices(
            get_dataset_modality_value(self.form_values),
            get_dataset_interaction_type_value(self.form_values),
        )
        return list(choices.values())

    def get_first_compatible_query_builder_label(self) -> str | None:
        """Return the first compatible builder label, if any."""
        labels = self.get_compatible_query_builder_labels()
        return labels[0] if labels else None

    def is_current_query_builder_compatible(self) -> bool:
        """Return whether the selected builder is compatible with current dataset settings."""
        return self.form_values.get("query.builder.key") in self.get_compatible_query_builder_labels()

    def refresh_query_builder_options(self, *, refresh_rows: bool = True) -> None:
        """Refresh query-builder choices for the selected dataset settings."""
        labels = self.get_compatible_query_builder_labels()
        if self.query_builder_select is not None:
            self.query_builder_select.options = labels
            self.query_builder_select.update()

        if labels:
            if not self.is_current_query_builder_compatible():
                self.form_values["query.builder.key"] = labels[0]
            if self.builder_availability_message is not None:
                self.builder_availability_message.text = ""
            if is_chembl_builder_key(self.form_values["query.builder.key"]):
                self.chembl_builder_rows = [make_chembl_builder_ui_row(self.form_values["query.builder.key"])]
                if refresh_rows:
                    self.build_chembl_builder_rows.refresh()
            if is_pubchem_builder_key(self.form_values["query.builder.key"]):
                self.pubchem_builder_row = make_pubchem_builder_ui_row(self.form_values["query.builder.key"])
                if refresh_rows:
                    self.build_pubchem_builder_row.refresh()
            if is_chebi_builder_key(self.form_values["query.builder.key"]):
                self.chebi_builder_rows = [make_chebi_builder_ui_row(self.form_values["query.builder.key"])]
                if refresh_rows:
                    self.build_chebi_builder_rows.refresh()
            if refresh_rows:
                self.build_uniprot_builder_rows.refresh()
            self.sync_builder_rows_to_form()
            self.update_builder_previews()
            return

        self.form_values["query.input_mode"] = get_labeled_option_default(
            "manual",
            QUERY_INPUT_MODE_LABEL_TO_VALUE,
        )
        if self.builder_availability_message is not None:
            self.builder_availability_message.text = (
                "No advanced builder matches these dataset settings. Use Manual query or adjust "
                "the modality and interaction type."
            )
        self.update_builder_previews()

    def handle_dataset_builder_context_change(self, *_args: object) -> None:
        """Refresh builder choices after dataset modality or interaction type changes."""
        self.update_interaction_type_visibility()
        self.refresh_query_builder_options()

    def update_interaction_type_visibility(self, *, update_select: bool = True) -> None:
        """Update interaction type selector visibility for the selected modality."""
        should_show = should_show_interaction_type_selector(self.form_values)
        if not should_show:
            self.form_values["dataset.interaction_type"] = NO_INTERACTION_LABEL
        if self.interaction_type_select is None:
            return
        self.interaction_type_select.visible = should_show
        if not should_show:
            self.interaction_type_select.value = NO_INTERACTION_LABEL
        if update_select:
            self.interaction_type_select.update()

    def sync_builder_rows_to_form(self) -> None:
        """Synchronize visible builder rows into pure form values."""
        self.form_values["query.uniprot_builder.rows"] = build_uniprot_builder_form_rows(
            self.uniprot_builder_rows
        )
        if is_chembl_builder_key(self.form_values["query.builder.key"]):
            self.form_values["query.chembl_builder.rows"] = build_chembl_builder_form_rows(
                self.form_values["query.builder.key"],
                self.chembl_builder_rows,
            )
        if is_pubchem_builder_key(self.form_values["query.builder.key"]):
            self.form_values["query.pubchem_builder.row"] = build_pubchem_builder_form_row(
                self.form_values["query.builder.key"],
                self.pubchem_builder_row,
            )
        if is_chebi_builder_key(self.form_values["query.builder.key"]):
            self.form_values["query.chebi_builder.rows"] = build_chebi_builder_form_rows(
                self.form_values["query.builder.key"],
                self.chebi_builder_rows,
            )

    def update_builder_previews(self, *_args: object) -> None:
        """Update friendly and interpreted advanced query previews."""
        self.sync_builder_rows_to_form()
        if self.friendly_query_preview is None or self.interpreted_query_preview is None:
            return
        try:
            builder_key = normalize_query_builder_key(self.form_values["query.builder.key"])
            if builder_key == "uniprot":
                rows = build_uniprot_builder_rows_from_form(self.form_values)
                friendly_query = build_uniprot_friendly_query(rows)
                interpreted_query = build_uniprot_interpreted_query(rows)
            elif builder_key in CHEMBL_BUILDER_RESOURCE_BY_KEY:
                rows = build_chembl_builder_rows_from_form(self.form_values)
                friendly_query = build_chembl_friendly_query(rows)
                interpreted_query = build_chembl_interpreted_query(rows)
            elif builder_key in PUBCHEM_BUILDER_RESOURCE_BY_KEY:
                row = build_pubchem_builder_row_from_form(self.form_values)
                friendly_query = build_pubchem_friendly_query(row)
                interpreted_query = build_pubchem_interpreted_query(row)
            else:
                rows = build_chebi_builder_rows_from_form(self.form_values)
                friendly_query = build_chebi_friendly_query(rows)
                interpreted_query = build_chebi_interpreted_query(rows)
        except ValueError as exc:
            self.friendly_query_preview.value = ""
            self.interpreted_query_preview.value = f"Builder error: {exc}"
            return
        self.friendly_query_preview.value = friendly_query
        self.interpreted_query_preview.value = interpreted_query

    def build_execution_controls(self) -> None:
        """Build execution form controls."""
        with (
            ui.expansion("Execution", value=True).classes("w-full"),
            ui.grid(columns=3).classes("w-full gap-3"),
        ):
            (
                ui.checkbox("Enable enrichment")
                .bind_value(self.form_values, "execution.enrich")
                .tooltip("Enables supported enrichment steps when the workflow supports them.")
            )
            (
                ui.checkbox("Enable debug logging")
                .bind_value(self.form_values, "execution.debug")
                .tooltip("Enable more verbose debugging information in supported workflow operations.")
            )
            (
                ui.number("Max workers", min=1, step=1)
                .bind_value(self.form_values, "execution.max_workers")
                .tooltip("Maximum number of worker threads used by supported operations.")
            )
            (
                ui.number("Total retries", min=0, step=1)
                .bind_value(self.form_values, "execution.total_retries")
                .tooltip("Number of retry attempts for supported network operations.")
            )
            (
                ui.number("ChEMBL pages to fetch", step=1)
                .bind_value(self.form_values, "execution.chembl_pages_to_fetch")
                .tooltip(
                    "Number of ChEMBL pages to retrieve for supported workflows. Use -1 to fetch "
                    "all available pages."
                )
            )
            (
                ui.number("UniProt timeout", min=0, step=0.1)
                .bind_value(self.form_values, "execution.uniprot_timeout")
                .tooltip("Optional timeout in seconds. Leave empty to use the default.")
            )

    def build_harmonization_controls(self) -> None:
        """Build harmonization form controls."""
        with (
            ui.expansion("Harmonization", value=True).classes("w-full"),
            ui.grid(columns=2).classes("w-full gap-3"),
        ):
            (
                ui.input("ID column")
                .props('clearable placeholder="_id"')
                .bind_value(self.form_values, "harmonization.id_column")
                .tooltip(
                    "Optional column name used as a deterministic row identifier in tabular "
                    "outputs when needed. Example: _id."
                )
            )
            (
                ui.input("Label column")
                .props('clearable placeholder="_label"')
                .bind_value(self.form_values, "harmonization.label_column")
                .tooltip(
                    "Optional column name that identifies labels or groups in tabular outputs. "
                    "Stored with the descriptor for reference. Exported columns keep their "
                    "original names."
                )
            )
            (
                ui.input("Sequence column")
                .props('clearable placeholder="sequence"')
                .bind_value(self.form_values, "harmonization.sequence_column")
                .tooltip(
                    "Optional column name used to identify biological sequences for reporting, "
                    "such as unique sequence counts, when that column exists in tabular outputs."
                )
            )
            (
                ui.input("Unique sequence strategy")
                .props('clearable placeholder="exact"')
                .bind_value(self.form_values, "harmonization.unique_sequence_strategy")
                .tooltip(
                    "Optional strategy name for sequence uniqueness notes. Deduplication is "
                    "handled elsewhere for now."
                )
            )
            (
                ui.input("Metadata fields")
                .props('clearable placeholder="accession, protein_name, organism_name, sequence"')
                .bind_value(self.form_values, "harmonization.metadata_fields")
                .classes("col-span-2")
                .tooltip(
                    "Optional comma-separated list of metadata fields expected in the output. "
                    "Exported columns stay unchanged."
                )
            )

    def build_export_controls(self) -> None:
        """Build export form controls."""
        with ui.expansion("Export", value=True).classes("w-full"), ui.grid(columns=2).classes("w-full gap-3"):
            (
                ui.select(
                    list(OUTPUT_DIRECTORY_MODE_LABEL_TO_VALUE),
                    label="Output directory mode",
                )
                .bind_value(self.form_values, "export.output_dir_mode")
                .tooltip(
                    "Use results/{dataset.name}, or choose a custom relative path for later "
                    "workflow execution."
                )
            )
            (
                ui.input("Custom relative output path")
                .props('clearable placeholder="results/my_dataset"')
                .bind_value(self.form_values, "export.output_dir")
                .tooltip(
                    "Directory used later when the workflow runs. Use a relative path; absolute "
                    "paths and '..' are blocked."
                )
            )
            (
                ui.select(list(EXPORT_FORMAT_LABEL_TO_VALUE), label="Output format")
                .bind_value(self.form_values, "export.format")
                .tooltip("File format to use when the workflow is executed later.")
            )
            (
                ui.input("Metadata manifest filename")
                .props("clearable")
                .bind_value(self.form_values, "export.manifest_file")
                .tooltip("Metadata manifest filename.")
            )
            (
                ui.input("Run summary filename")
                .props("clearable")
                .bind_value(self.form_values, "export.summary_file")
                .tooltip("Run summary filename.")
            )
            (
                ui.checkbox("Include metadata manifest")
                .bind_value(self.form_values, "export.include_metadata")
                .tooltip("Whether the workflow should write metadata when executed later.")
            )
            (
                ui.checkbox("Include run summary")
                .bind_value(self.form_values, "export.include_summary")
                .tooltip("Whether the workflow should write a compact summary when executed later.")
            )

    def build_preview_controls(self) -> None:
        """Build YAML preview controls."""
        with ui.expansion("YAML preview", value=True).classes("w-full"):
            with ui.row().classes("items-center gap-3"):
                ui.button("Generate YAML", on_click=self.generate_yaml)
                ui.button("Validate YAML", on_click=self.validate_yaml)
                ui.button("Save YAML", on_click=self.save_yaml)
            self.status = ui.label("")
            self.yaml_output = (
                ui.textarea("Generated workflow-v1 YAML")
                .classes("w-full font-mono")
                .props("readonly rows=24")
            )

    def generate_yaml(self) -> None:
        """Generate YAML from the current form state."""
        self.sync_builder_rows_to_form()
        try:
            descriptor = build_workflow_descriptor(self.form_values)
        except (TypeError, ValueError) as exc:
            self.show_errors([str(exc)])
            return

        self.yaml_output.value = render_workflow_yaml(descriptor)
        self.show_validation_result(validate_generated_descriptor(descriptor))

    def validate_yaml(self) -> None:
        """Validate the current YAML preview text."""
        yaml_text = str(self.yaml_output.value or "")
        if not yaml_text.strip():
            self.generate_yaml()
            return
        try:
            descriptor = yaml.safe_load(yaml_text)
        except yaml.YAMLError as exc:
            self.show_errors([f"Invalid YAML: {exc}"])
            return
        if not isinstance(descriptor, dict):
            self.show_errors(["Workflow YAML root must be a mapping."])
            return
        self.show_validation_result(validate_generated_descriptor(descriptor))

    def save_yaml(self) -> None:
        """Download the current YAML preview."""
        if not str(self.yaml_output.value or "").strip():
            self.generate_yaml()
        errors = self.current_validation_errors()
        if errors:
            self.show_errors(errors)
            return
        filename = build_workflow_filename(self.form_values.get("dataset.name"))
        ui.download.content(str(self.yaml_output.value), filename)
        self.status.text = f"Downloaded {filename}."

    async def load_yaml_upload(self, event: Any) -> None:
        """Load an uploaded workflow YAML file into supported form controls."""
        try:
            upload_file = getattr(event, "file", None)
            filename = getattr(upload_file, "name", "")
            if filename and not is_supported_workflow_yaml_filename(filename):
                message = "Unsupported file type. Upload a .yml or .yaml workflow file."
                self.set_workflow_upload_error(filename, message)
                self.show_errors([message])
                return
            try:
                yaml_text = await read_upload_event_text(event)
                loaded_form_values, warnings = load_workflow_yaml_to_form_values(yaml_text)
            except (TypeError, ValueError, UnicodeDecodeError) as exc:
                message = f"Could not load workflow YAML: {exc}"
                self.set_workflow_upload_error(filename, message)
                self.show_errors([message])
                return
            self.apply_loaded_form_values(loaded_form_values)
            errors = self.regenerate_loaded_yaml_preview(warnings)
            if errors:
                self.set_workflow_upload_error(filename, "\n".join(errors))
                return
            self.set_workflow_upload_success(filename, warnings)
        finally:
            self.reset_workflow_upload()

    def set_workflow_upload_success(self, filename: object, warnings: list[str]) -> None:
        """Set upload status state for a successfully loaded workflow YAML file."""
        self.loaded_workflow_filename = str(filename or "workflow YAML file")
        self.loaded_workflow_upload_status = "success"
        self.loaded_workflow_upload_message = (
            "The form was populated from this file. Upload another YAML file to replace it."
        )
        self.loaded_workflow_upload_warnings = list(warnings)
        self.refresh_upload_status_card()

    def set_workflow_upload_error(self, filename: object, message: str) -> None:
        """Set upload status state for a failed workflow YAML upload."""
        self.loaded_workflow_filename = str(filename or "workflow YAML file")
        self.loaded_workflow_upload_status = "error"
        self.loaded_workflow_upload_message = message
        self.loaded_workflow_upload_warnings = []
        self.refresh_upload_status_card()

    def refresh_upload_status_card(self) -> None:
        """Refresh the workflow upload status card when the app is running."""
        self.build_upload_status_card.refresh()

    def reset_workflow_upload(self) -> None:
        """Clear the workflow upload control after each load attempt."""
        upload = getattr(self, "workflow_upload", None)
        if upload is None:
            return
        reset = getattr(upload, "reset", None)
        if callable(reset):
            reset()
            return
        clear = getattr(upload, "clear", None)
        if callable(clear):
            clear()

    def apply_loaded_form_values(self, loaded_form_values: dict[str, object]) -> None:
        """Apply loaded descriptor values to GUI state."""
        self.form_values.update(loaded_form_values)
        self.form_values["query.input_mode"] = get_labeled_option_default(
            "manual",
            QUERY_INPUT_MODE_LABEL_TO_VALUE,
        )
        self.form_values["query.builder.key"] = get_query_builder_label(
            self.form_values.get("query.builder.key", "uniprot")
        )
        self.uniprot_builder_rows = [make_uniprot_builder_ui_row()]
        self.chembl_builder_rows = [make_chembl_builder_ui_row(get_query_builder_label("chembl_target"))]
        self.pubchem_builder_row = make_pubchem_builder_ui_row(get_query_builder_label("pubchem_compound"))
        self.chebi_builder_rows = [make_chebi_builder_ui_row(get_query_builder_label("chebi_entity"))]
        self.update_interaction_type_visibility()
        self.refresh_query_builder_options()

    def regenerate_loaded_yaml_preview(self, warnings: list[str]) -> list[str]:
        """Regenerate YAML preview from loaded editable form values."""
        try:
            descriptor = build_workflow_descriptor(self.form_values)
        except (TypeError, ValueError) as exc:
            errors = [f"Loaded YAML could not be regenerated: {exc}"]
            self.show_errors(errors)
            return errors
        self.yaml_output.value = render_workflow_yaml(descriptor)
        errors = validate_generated_descriptor(descriptor)
        if errors:
            self.show_errors(errors)
            return errors
        self.show_load_result(warnings)
        return []

    def show_load_result(self, warnings: list[str]) -> None:
        """Show YAML loading success with non-editable metadata warnings."""
        lines = ["Workflow YAML loaded into supported form fields."]
        if warnings:
            lines.extend(warnings)
            ui.notify("Workflow YAML loaded with warnings.", type="warning")
        else:
            ui.notify("Workflow YAML loaded.", type="positive")
        self.status.text = "\n".join(lines)

    def current_validation_errors(self) -> list[str]:
        """Return validation errors for the current YAML preview."""
        yaml_text = str(self.yaml_output.value or "")
        try:
            descriptor = yaml.safe_load(yaml_text)
        except yaml.YAMLError as exc:
            return [f"Invalid YAML: {exc}"]
        if not isinstance(descriptor, dict):
            return ["Workflow YAML root must be a mapping."]
        return validate_generated_descriptor(descriptor)

    def show_validation_result(self, errors: list[str]) -> None:
        """Show validation success or validation errors."""
        if errors:
            self.show_errors(errors)
            return
        self.status.text = "Validation succeeded."
        ui.notify("Validation succeeded.", type="positive")

    def show_errors(self, errors: list[str]) -> None:
        """Show user-facing validation errors."""
        message = "\n".join(errors)
        self.status.text = message
        ui.notify(message, type="negative")


def create_app() -> WorkflowYamlBuilderApp:
    """Create the NiceGUI workflow YAML builder app."""
    app = WorkflowYamlBuilderApp()
    app.build()
    return app


def main() -> None:
    """Run the BioSeqDownloader workflow YAML builder GUI."""
    create_app()
    ui.run(title="BioSeqDownloader Workflow YAML Builder")


if __name__ in {"__main__", "__mp_main__"}:
    main()
