"""NiceGUI app for generating workflow-v1 YAML descriptors."""

from __future__ import annotations

from functools import partial
from typing import Any, cast

import yaml
from nicegui import ui

from bioseq_dl.gui.form_helpers import (
    IC50_CONDITION_LABEL_TO_VALUE,
    IC50_UNIT_LABEL_TO_VALUE,
    NO_INTERACTION_LABEL,
    UNIPROT_BUILDER_FIELD_LABEL_TO_VALUE,
    build_chebi_builder_form_row,
    build_chembl_builder_form_rows,
    build_chembl_ic50_builder_form_row,
    build_gui_query_builder_state_from_loaded_form,
    build_pubchem_builder_form_row,
    build_query_composition_entries_form_state,
    build_query_composition_entries_ui_state,
    build_uniprot_builder_form_rows,
    get_active_chebi_builder_label,
    get_active_chembl_builder_label,
    get_active_pubchem_builder_label,
    get_chebi_field_entry,
    get_chebi_field_help,
    get_chebi_field_options,
    get_chembl_field_entry,
    get_chembl_field_help,
    get_chembl_field_options,
    get_chembl_filter_type_options,
    get_chembl_ic50_condition_value,
    get_dataset_interaction_type_value,
    get_dataset_modality_value,
    get_pubchem_field_entry,
    get_pubchem_field_help,
    get_pubchem_field_options,
    get_query_builder_key,
    get_query_builder_label,
    get_uniprot_builder_field_help,
    get_uniprot_builder_field_placeholder,
    is_advanced_builder_query_mode,
    is_chebi_builder_key,
    is_chembl_builder_key,
    is_chembl_ic50_builder_key,
    is_manual_query_mode,
    is_pubchem_builder_key,
    is_pubchem_similarity_field,
    is_supported_workflow_yaml_filename,
    is_uniprot_builder_key,
    make_chebi_builder_ui_row,
    make_chembl_builder_ui_row,
    make_chembl_ic50_builder_ui_row,
    make_pubchem_builder_ui_row,
    make_uniprot_builder_ui_row,
    normalize_chembl_ic50_ui_row_for_condition,
    read_upload_event_text,
    should_show_interaction_type_selector,
)
from bioseq_dl.gui.query_builders.chebi import (
    build_chebi_friendly_query,
    build_chebi_interpreted_query,
)
from bioseq_dl.gui.query_builders.chembl import (
    build_chembl_friendly_query,
    build_chembl_ic50_friendly_query,
    build_chembl_ic50_interpreted_query,
    build_chembl_interpreted_query,
)
from bioseq_dl.gui.query_builders.pubchem import (
    build_pubchem_friendly_query,
    build_pubchem_interpreted_query,
)
from bioseq_dl.gui.query_builders.registry import get_compatible_query_builder_choices
from bioseq_dl.gui.query_builders.uniprot import (
    build_uniprot_friendly_query,
    build_uniprot_interpreted_query,
)
from bioseq_dl.gui.yaml_builder import (
    EXPORT_FORMAT_LABEL_TO_VALUE,
    INTERACTION_TYPE_LABEL_TO_VALUE,
    LOADED_INCOMPATIBLE_ENRICHMENT_PASSTHROUGH_FORM_KEY,
    MODALITY_LABEL_TO_VALUE,
    OUTPUT_DIRECTORY_MODE_LABEL_TO_VALUE,
    QUERY_INPUT_MODE_LABEL_TO_VALUE,
    UNIPROT_MATCH_MODE_LABEL_TO_VALUE,
    WORKFLOW_MODE_LABEL_TO_VALUE,
    build_chebi_builder_row_from_form,
    build_chembl_builder_rows_from_form,
    build_chembl_ic50_builder_row_from_form,
    build_pubchem_builder_row_from_form,
    build_uniprot_builder_rows_from_form,
    build_workflow_descriptor,
    build_workflow_filename,
    crossref_fields_from_enrichment_sources,
    crossref_fields_without_selectable_sources,
    enrichment_sources_from_crossref_fields,
    get_effective_uniprot_return_field_text,
    get_enrichment_source_options,
    get_labeled_option_default,
    get_required_uniprot_return_field_text,
    is_enrichment_workflow_compatible,
    load_workflow_yaml_to_form_values,
    normalize_enrichment_sources,
    normalize_labeled_value,
    normalize_query_builder_key,
    parse_bool,
    render_workflow_yaml,
    resolve_query_composition_entry_value,
    validate_generated_descriptor,
    workflow_yaml_gui_form_defaults,
)


def is_query_composition_workflow_mode(value: object) -> bool:
    """Return whether a GUI workflow mode value selects query_composition."""
    return normalize_labeled_value(value, WORKFLOW_MODE_LABEL_TO_VALUE) == "query_composition"


def is_chembl_ic50_range_condition(value: object) -> bool:
    """Return whether a visible IC50 condition uses minimum and maximum controls."""
    return get_chembl_ic50_condition_value(value) == "range"


def is_chembl_ic50_value_condition(value: object) -> bool:
    """Return whether a visible IC50 condition uses one value control."""
    return get_chembl_ic50_condition_value(value) != "range"


class WorkflowYamlBuilderApp:
    """Render and manage the BioSeqDownloader workflow YAML builder."""

    def __init__(self) -> None:
        """Initialize app state for form binding and status output."""
        self.form_values = workflow_yaml_gui_form_defaults()
        self.form_values["query.builder.key"] = get_query_builder_label(self.form_values["query.builder.key"])
        self.active_query_builder_label = str(self.form_values["query.builder.key"])
        self.uniprot_builder_rows = [make_uniprot_builder_ui_row()]
        self.chembl_builder_rows = [make_chembl_builder_ui_row(get_query_builder_label("chembl_target"))]
        self.chembl_ic50_builder_row = make_chembl_ic50_builder_ui_row()
        self.pubchem_builder_row = make_pubchem_builder_ui_row(get_query_builder_label("pubchem_compound"))
        self.chebi_builder_row = make_chebi_builder_ui_row(get_query_builder_label("chebi_entity"))
        self.next_query_composition_entry_id = 1
        self.query_composition_entries = build_query_composition_entries_ui_state(
            self.form_values["query.composition.entries"]
        )
        for entry in self.query_composition_entries:
            self.ensure_query_composition_entry_id(entry)
        self.friendly_query_preview: Any = None
        self.interpreted_query_preview: Any = None
        self.query_composition_preview: Any = None
        self.query_composition_entry_previews: dict[int, Any] = {}
        self.query_builder_select: Any = None
        self.enrichment_toggle_checkbox: Any = None
        self.enrichment_sources_select: Any = None
        self.query_fields_input: Any = None
        self.crossref_fields_input: Any = None
        self.enrichment_required_fields_note: Any = None
        self.enrichment_effective_fields_note: Any = None
        self.interaction_type_select: Any = None
        self.workflow_upload: Any = None
        self.loaded_workflow_filename: str | None = None
        self.loaded_workflow_upload_status: str | None = None
        self.loaded_workflow_upload_message: str | None = None
        self.loaded_workflow_upload_warnings: list[str] = []
        self.builder_availability_message: Any = None
        self.yaml_output: Any = None
        self.status: Any = None
        self.is_loading_form_values = False
        self.is_refreshing_query_section = False

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
                "Compatible query.builder metadata restores Advanced builder mode; otherwise "
                "the saved query text opens in Manual query mode."
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
                    .on_value_change(self.handle_workflow_mode_change)
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

    @ui.refreshable
    def build_query_controls(self) -> None:
        """Build query form controls."""
        with ui.expansion("Query", value=True).classes("w-full"):
            if is_query_composition_workflow_mode(self.form_values["dataset.mode"]):
                self.build_query_composition_controls()
            else:
                self.build_query_first_controls()
            self.build_shared_query_controls()

    def build_query_first_controls(self) -> None:
        """Build the single-query editor and advanced builders."""
        ui.label(
            "Choose manual query entry or build an interpreted query. "
            "query.value remains executable; advanced builders also store neutral "
            "query.builder metadata."
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
            compatible_builder_labels = self.get_compatible_query_builder_labels()
            availability_message = (
                ""
                if compatible_builder_labels
                else (
                    "No advanced builder matches these dataset settings. Use Manual query "
                    "or adjust the modality and interaction type."
                )
            )
            self.builder_availability_message = ui.label(availability_message).classes(
                "text-sm text-orange-700"
            )
            self.query_builder_select = (
                ui.select(compatible_builder_labels, label="Query builder")
                .bind_value(self.form_values, "query.builder.key")
                .on_value_change(self.handle_query_builder_change)
                .tooltip("Choose the database-specific query builder.")
            )
            builder_key = get_query_builder_key(self.form_values["query.builder.key"])
            if builder_key == "uniprot":
                self.build_uniprot_builder_controls()
            elif builder_key == "chembl_ic50":
                self.build_chembl_ic50_builder_controls()
            elif is_chembl_builder_key(builder_key):
                self.build_chembl_builder_controls()
            elif is_pubchem_builder_key(builder_key):
                self.build_pubchem_builder_controls()
            elif is_chebi_builder_key(builder_key):
                self.build_chebi_builder_controls()
            self.friendly_query_preview = (
                ui.textarea("Friendly query preview").classes("w-full font-mono").props("readonly rows=3")
            )
            self.interpreted_query_preview = (
                ui.textarea("Interpreted query.value preview")
                .classes("w-full font-mono")
                .props("readonly rows=3")
            )
        builder_panel.bind_visibility_from(
            self.form_values,
            "query.input_mode",
            backward=is_advanced_builder_query_mode,
        )
        self.update_builder_previews()

    def build_query_composition_controls(self) -> None:
        """Build the labeled query-composition editor."""
        ui.label(
            "Build multiple labeled queries. Each entry keeps its own manual query or "
            "advanced builder state."
        ).classes("text-sm text-gray-700")
        self.build_query_composition_rows()
        ui.button("Add labeled query", on_click=self.add_query_composition_entry)
        self.query_composition_preview = (
            ui.textarea("Executable query.value preview")
            .classes("w-full font-mono")
            .props("readonly rows=3")
        )
        self.update_query_composition_preview()

    def build_shared_query_controls(self) -> None:
        """Build query settings shared by query_first and query_composition modes."""
        with ui.grid(columns=2).classes("w-full gap-3"):
            self.query_fields_input = (
                ui.input("Return fields")
                .props('clearable placeholder="accession, protein_name, organism_name, sequence"')
                .bind_value(self.form_values, "query.fields")
                .tooltip(
                    "Optional UniProt request fields. Leave empty to use the safe default "
                    "field set; enrichment can require extra fields at runtime."
                )
            )
            (
                ui.checkbox("Include UniProt isoforms")
                .bind_value(self.form_values, "query.include_isoform")
                .tooltip("Whether UniProt isoforms should be included when supported by the workflow.")
            )
        ui.label(
            "Empty return fields resolve at execution time to: "
            f"{get_effective_uniprot_return_field_text('', '')}."
        ).classes("text-xs text-gray-600")

    def ensure_query_composition_entry_id(self, entry: dict[str, object]) -> int:
        """Assign and return a stable UI identity for one composition entry."""
        entry_id = entry.get("_entry_id")
        if isinstance(entry_id, int):
            return entry_id
        entry_id = self.next_query_composition_entry_id
        self.next_query_composition_entry_id += 1
        entry["_entry_id"] = entry_id
        return entry_id

    def get_query_composition_entries(self) -> list[dict[str, object]]:
        """Return mutable GUI composition entries, ensuring at least one exists."""
        if not self.query_composition_entries:
            self.add_query_composition_entry(refresh=False)
        for entry in self.query_composition_entries:
            self.ensure_query_composition_entry_id(entry)
        return self.query_composition_entries

    @ui.refreshable
    def build_query_composition_rows(self) -> None:
        """Build editable controls for each labeled composition query."""
        self.query_composition_entry_previews = {}
        for entry in self.get_query_composition_entries():
            self.ensure_query_composition_entry_builder_state(entry)
            entry_id = self.ensure_query_composition_entry_id(entry)
            with ui.card().classes("w-full gap-3 rounded-md"):
                with ui.row().classes("w-full items-end gap-3"):
                    (
                        ui.input("Label")
                        .props("clearable")
                        .bind_value(entry, "label")
                        .on_value_change(self.update_query_composition_preview)
                        .classes("min-w-48")
                    )
                    (
                        ui.input("Description")
                        .props("clearable")
                        .bind_value(entry, "description")
                        .on_value_change(self.update_query_composition_preview)
                        .classes("grow")
                    )
                    if len(self.query_composition_entries) > 1:
                        ui.button("Remove", on_click=partial(self.remove_query_composition_entry, entry_id))
                (
                    ui.select(list(QUERY_INPUT_MODE_LABEL_TO_VALUE), label="Input mode")
                    .bind_value(entry, "query_input_mode")
                    .on_value_change(partial(self.handle_query_composition_entry_mode_change, entry))
                    .classes("w-56")
                )
                with ui.column().classes("w-full gap-2") as manual_panel:
                    (
                        ui.textarea("Executable query value")
                        .bind_value(entry, "value")
                        .on_value_change(
                            partial(self.handle_query_composition_manual_value_change, entry)
                        )
                        .classes("w-full")
                    )
                manual_panel.bind_visibility_from(
                    entry,
                    "query_input_mode",
                    backward=is_manual_query_mode,
                )
                with ui.column().classes("w-full gap-3") as builder_panel:
                    labels = self.get_compatible_query_builder_labels()
                    if labels:
                        (
                            ui.select(labels, label="Query builder")
                            .bind_value(entry, "query_builder_key")
                            .on_value_change(
                                partial(self.handle_query_composition_entry_builder_change, entry)
                            )
                            .classes("w-full")
                        )
                    else:
                        ui.label(
                            "No advanced builder matches these dataset settings. Use Manual query "
                            "or adjust the modality and interaction type."
                        ).classes("text-sm text-orange-700")
                    self.build_query_composition_entry_builder_controls(entry)
                    preview = (
                        ui.textarea("Interpreted entry query preview")
                        .classes("w-full font-mono")
                        .props("readonly rows=2")
                    )
                    self.query_composition_entry_previews[entry_id] = preview
                    self.update_query_composition_entry_preview(entry)
                builder_panel.bind_visibility_from(
                    entry,
                    "query_input_mode",
                    backward=is_advanced_builder_query_mode,
                )

    def build_query_composition_entry_builder_controls(self, entry: dict[str, object]) -> None:
        """Build builder controls for one query-composition entry."""
        builder_key = get_query_builder_key(entry["query_builder_key"])
        if builder_key == "uniprot":
            self.build_query_composition_uniprot_rows(entry)
        elif builder_key == "chembl_ic50":
            self.build_query_composition_chembl_ic50_row(entry)
        elif is_chembl_builder_key(builder_key):
            self.build_query_composition_chembl_rows(entry)
        elif is_pubchem_builder_key(builder_key):
            self.build_query_composition_pubchem_row(entry)
        elif is_chebi_builder_key(builder_key):
            self.build_query_composition_chebi_row(entry)

    def build_query_composition_uniprot_rows(self, entry: dict[str, object]) -> None:
        """Build entry-local UniProt builder rows."""
        rows = cast("list[dict[str, object]]", entry["uniprot_builder_rows"])
        for index, row in enumerate(rows):
            field_help = get_uniprot_builder_field_help(row.get("field", ""))
            values_placeholder = get_uniprot_builder_field_placeholder(row.get("field", ""))
            with ui.row().classes("w-full items-end gap-3"):
                if index == 0:
                    ui.input("First condition").props('readonly placeholder=""').classes("w-32")
                else:
                    (
                        ui.select(["AND", "OR"], label="Connector")
                        .bind_value(row, "connector")
                        .on_value_change(self.update_query_composition_preview)
                        .classes("w-28")
                    )
                (
                    ui.select(list(UNIPROT_BUILDER_FIELD_LABEL_TO_VALUE), label="Field")
                    .bind_value(row, "field")
                    .on_value_change(self.refresh_query_composition_editor)
                    .classes("min-w-56")
                    .tooltip(field_help)
                )
                (
                    ui.input("Values", placeholder=values_placeholder)
                    .props("clearable")
                    .bind_value(row, "values")
                    .on_value_change(self.update_query_composition_preview)
                    .classes("grow")
                )
                (
                    ui.select(list(UNIPROT_MATCH_MODE_LABEL_TO_VALUE), label="Match mode")
                    .bind_value(row, "match_mode")
                    .on_value_change(self.update_query_composition_preview)
                    .classes("w-32")
                )
                if index > 0:
                    ui.button(
                        "Remove",
                        on_click=partial(self.remove_query_composition_uniprot_row, entry, index),
                    )
            ui.label(field_help).classes("text-xs text-gray-600")
        ui.button("Add UniProt condition", on_click=partial(self.add_query_composition_uniprot_row, entry))

    def build_query_composition_chembl_rows(self, entry: dict[str, object]) -> None:
        """Build entry-local ChEMBL builder rows."""
        builder_label = get_active_chembl_builder_label(entry["query_builder_key"])
        rows = cast("list[dict[str, object]]", entry["chembl_builder_rows"])
        for index, row in enumerate(rows):
            field_help = get_chembl_field_help(builder_label, row.get("field", ""))
            values_placeholder = str(get_chembl_field_entry(builder_label, row.get("field", "")).placeholder)
            filter_type_options = get_chembl_filter_type_options(builder_label, row.get("field", ""))
            if row.get("filter_type") not in filter_type_options:
                row["filter_type"] = filter_type_options[0]
            with ui.row().classes("w-full items-end gap-3"):
                (
                    ui.select(get_chembl_field_options(builder_label), label="Field")
                    .bind_value(row, "field")
                    .on_value_change(self.refresh_query_composition_editor)
                    .classes("min-w-72")
                    .tooltip(field_help)
                )
                (
                    ui.select(filter_type_options, label="Filter type")
                    .bind_value(row, "filter_type")
                    .on_value_change(self.update_query_composition_preview)
                    .classes("w-40")
                )
                (
                    ui.input("Value", placeholder=values_placeholder)
                    .props("clearable")
                    .bind_value(row, "value")
                    .on_value_change(self.update_query_composition_preview)
                    .classes("grow")
                )
                if index > 0:
                    ui.button(
                        "Remove",
                        on_click=partial(self.remove_query_composition_chembl_row, entry, index),
                    )
            ui.label(field_help).classes("text-xs text-gray-600")
        ui.button("Add ChEMBL condition", on_click=partial(self.add_query_composition_chembl_row, entry))

    def build_query_composition_chembl_ic50_row(self, entry: dict[str, object]) -> None:
        """Build an entry-local ChEMBL IC50 builder row."""
        row = cast("dict[str, object]", entry["chembl_ic50_builder_row"])
        normalize_chembl_ic50_ui_row_for_condition(row)
        with ui.row().classes("w-full items-end gap-3"):
            (
                ui.select(list(IC50_CONDITION_LABEL_TO_VALUE), label="Condition")
                .bind_value(row, "condition")
                .on_value_change(partial(self.handle_query_composition_chembl_ic50_condition_change, entry))
                .classes("min-w-56")
            )
            minimum_input = (
                ui.number("Minimum", step=0.1)
                .bind_value(row, "minimum")
                .on_value_change(self.update_query_composition_preview)
                .classes("w-32")
            )
            minimum_input.bind_visibility_from(
                row,
                "condition",
                backward=is_chembl_ic50_range_condition,
            )
            maximum_input = (
                ui.number("Maximum", step=0.1)
                .bind_value(row, "maximum")
                .on_value_change(self.update_query_composition_preview)
                .classes("w-32")
            )
            maximum_input.bind_visibility_from(
                row,
                "condition",
                backward=is_chembl_ic50_range_condition,
            )
            value_input = (
                ui.number("Value", step=0.1)
                .bind_value(row, "value")
                .on_value_change(self.update_query_composition_preview)
                .classes("w-32")
            )
            value_input.bind_visibility_from(
                row,
                "condition",
                backward=is_chembl_ic50_value_condition,
            )
            (
                ui.select(list(IC50_UNIT_LABEL_TO_VALUE), label="Unit")
                .bind_value(row, "unit")
                .on_value_change(self.update_query_composition_preview)
                .classes("w-24")
            )

    def build_query_composition_pubchem_row(self, entry: dict[str, object]) -> None:
        """Build an entry-local PubChem builder row."""
        builder_label = get_active_pubchem_builder_label(entry["query_builder_key"])
        row = cast("dict[str, object]", entry["pubchem_builder_row"])
        field_help = get_pubchem_field_help(builder_label, row.get("field", ""))
        values_placeholder = str(get_pubchem_field_entry(builder_label, row.get("field", "")).placeholder)
        with ui.row().classes("w-full items-end gap-3"):
            (
                ui.select(get_pubchem_field_options(builder_label), label="Field")
                .bind_value(row, "field")
                .on_value_change(partial(self.handle_query_composition_pubchem_field_change, entry))
                .classes("min-w-72")
                .tooltip(field_help)
            )
            (
                ui.input("Value", placeholder=values_placeholder)
                .props("clearable")
                .bind_value(row, "value")
                .on_value_change(self.update_query_composition_preview)
                .classes("grow")
            )
            threshold_input = (
                ui.number("Threshold", min=0, max=100, step=1)
                .bind_value(row, "threshold")
                .on_value_change(self.update_query_composition_preview)
                .classes("w-32")
            )
            threshold_input.bind_visibility_from(
                row,
                "field",
                backward=lambda value: is_pubchem_similarity_field(builder_label, value),
            )
        ui.label(field_help).classes("text-xs text-gray-600")

    def build_query_composition_chebi_row(self, entry: dict[str, object]) -> None:
        """Build an entry-local ChEBI builder row."""
        builder_label = get_active_chebi_builder_label(entry["query_builder_key"])
        row = cast("dict[str, object]", entry["chebi_builder_row"])
        field_help = get_chebi_field_help(builder_label, row.get("field", ""))
        values_placeholder = str(get_chebi_field_entry(builder_label, row.get("field", "")).placeholder)
        with ui.row().classes("w-full items-end gap-3"):
            (
                ui.select(get_chebi_field_options(builder_label), label="Field")
                .bind_value(row, "field")
                .on_value_change(self.refresh_query_composition_editor)
                .classes("min-w-72")
                .tooltip(field_help)
            )
            (
                ui.input("Value", placeholder=values_placeholder)
                .props("clearable")
                .bind_value(row, "value")
                .on_value_change(self.update_query_composition_preview)
                .classes("grow")
            )

    def ensure_query_composition_entry_builder_state(self, entry: dict[str, object]) -> None:
        """Ensure one composition entry has compatible builder state."""
        labels = self.get_compatible_query_builder_labels()
        if not labels:
            entry["query_input_mode"] = get_labeled_option_default("manual", QUERY_INPUT_MODE_LABEL_TO_VALUE)
            return
        if entry.get("query_builder_key") not in labels:
            entry["query_builder_key"] = labels[0]
            self.reset_query_composition_entry_builder_rows(entry)
        if not entry.get("uniprot_builder_rows"):
            entry["uniprot_builder_rows"] = [make_uniprot_builder_ui_row()]
        if not entry.get("chembl_builder_rows"):
            entry["chembl_builder_rows"] = [
                make_chembl_builder_ui_row(
                    get_active_chembl_builder_label(entry["query_builder_key"])
                )
            ]
        if not isinstance(entry.get("chembl_ic50_builder_row"), dict) or not entry["chembl_ic50_builder_row"]:
            entry["chembl_ic50_builder_row"] = make_chembl_ic50_builder_ui_row()
        if not isinstance(entry.get("pubchem_builder_row"), dict) or not entry["pubchem_builder_row"]:
            entry["pubchem_builder_row"] = make_pubchem_builder_ui_row(
                get_active_pubchem_builder_label(entry["query_builder_key"])
            )
        if not isinstance(entry.get("chebi_builder_row"), dict) or not entry["chebi_builder_row"]:
            entry["chebi_builder_row"] = make_chebi_builder_ui_row(
                get_active_chebi_builder_label(entry["query_builder_key"])
            )

    def reset_query_composition_entry_builder_rows(self, entry: dict[str, object]) -> None:
        """Reset only one composition entry's rows for its selected builder."""
        builder_label = entry["query_builder_key"]
        if is_uniprot_builder_key(builder_label):
            entry["uniprot_builder_rows"] = [make_uniprot_builder_ui_row()]
        elif is_chembl_ic50_builder_key(builder_label):
            entry["chembl_ic50_builder_row"] = make_chembl_ic50_builder_ui_row()
        elif is_chembl_builder_key(builder_label):
            entry["chembl_builder_rows"] = [make_chembl_builder_ui_row(builder_label)]
        elif is_pubchem_builder_key(builder_label):
            entry["pubchem_builder_row"] = make_pubchem_builder_ui_row(builder_label)
        elif is_chebi_builder_key(builder_label):
            entry["chebi_builder_row"] = make_chebi_builder_ui_row(builder_label)
        entry.pop("preserved_builder", None)

    def add_query_composition_entry(self, *, refresh: bool = True) -> None:
        """Add one independent labeled composition query entry."""
        entry = build_query_composition_entries_ui_state([{}])[0]
        self.ensure_query_composition_entry_id(entry)
        self.ensure_query_composition_entry_builder_state(entry)
        self.query_composition_entries.append(entry)
        self.sync_query_composition_entries_to_form()
        if refresh:
            self.refresh_query_composition_editor()

    def remove_query_composition_entry(self, entry_id: int) -> None:
        """Remove one labeled composition entry by stable identity."""
        if len(self.query_composition_entries) <= 1:
            return
        self.query_composition_entries = [
            entry for entry in self.query_composition_entries if entry.get("_entry_id") != entry_id
        ]
        self.sync_query_composition_entries_to_form()
        self.refresh_query_composition_editor()

    def handle_query_composition_entry_mode_change(self, entry: dict[str, object], *_args: object) -> None:
        """Update one composition entry after its input mode changes."""
        if self.is_loading_form_values:
            return
        self.ensure_query_composition_entry_builder_state(entry)
        self.sync_query_composition_entries_to_form()
        self.update_query_composition_preview()

    def handle_query_composition_entry_builder_change(self, entry: dict[str, object], *_args: object) -> None:
        """Reset only one composition entry after its builder changes."""
        if self.is_loading_form_values:
            return
        self.reset_query_composition_entry_builder_rows(entry)
        self.sync_query_composition_entries_to_form()
        self.refresh_query_composition_editor()

    def handle_query_composition_manual_value_change(
        self,
        entry: dict[str, object],
        *_args: object,
    ) -> None:
        """Clear preserved builder metadata when a fallback manual query is edited."""
        if self.is_loading_form_values:
            return
        entry.pop("preserved_builder", None)
        self.update_query_composition_preview()

    def add_query_composition_uniprot_row(self, entry: dict[str, object]) -> None:
        """Add one UniProt condition to a composition entry."""
        cast("list[dict[str, object]]", entry["uniprot_builder_rows"]).append(
            make_uniprot_builder_ui_row(connector="AND")
        )
        self.refresh_query_composition_editor()

    def remove_query_composition_uniprot_row(self, entry: dict[str, object], index: int) -> None:
        """Remove one UniProt condition from a composition entry."""
        rows = cast("list[dict[str, object]]", entry["uniprot_builder_rows"])
        if index <= 0 or index >= len(rows):
            return
        rows.pop(index)
        self.refresh_query_composition_editor()

    def add_query_composition_chembl_row(self, entry: dict[str, object]) -> None:
        """Add one ChEMBL condition to a composition entry."""
        cast("list[dict[str, object]]", entry["chembl_builder_rows"]).append(
            make_chembl_builder_ui_row(entry["query_builder_key"])
        )
        self.refresh_query_composition_editor()

    def remove_query_composition_chembl_row(self, entry: dict[str, object], index: int) -> None:
        """Remove one ChEMBL condition from a composition entry."""
        rows = cast("list[dict[str, object]]", entry["chembl_builder_rows"])
        if index <= 0 or index >= len(rows):
            return
        rows.pop(index)
        self.refresh_query_composition_editor()

    def handle_query_composition_pubchem_field_change(
        self,
        entry: dict[str, object],
        *_args: object,
    ) -> None:
        """Normalize one composition entry PubChem threshold after field changes."""
        builder_label = str(entry["query_builder_key"])
        row = cast("dict[str, object]", entry["pubchem_builder_row"])
        if is_pubchem_similarity_field(builder_label, row.get("field", "")):
            if row.get("threshold") in {None, ""}:
                row["threshold"] = 80
        else:
            row["threshold"] = None
        self.refresh_query_composition_editor()

    def handle_query_composition_chembl_ic50_condition_change(
        self,
        entry: dict[str, object],
        *_args: object,
    ) -> None:
        """Normalize one composition entry IC50 row after condition changes."""
        row = cast("dict[str, object]", entry["chembl_ic50_builder_row"])
        normalize_chembl_ic50_ui_row_for_condition(row)
        self.refresh_query_composition_editor()

    def sync_query_composition_entries_to_form(self) -> None:
        """Synchronize visible composition entries into pure form values."""
        self.form_values["query.composition.entries"] = build_query_composition_entries_form_state(
            self.query_composition_entries
        )

    def refresh_query_composition_editor(self, *_args: object) -> None:
        """Refresh composition controls and previews after entry-local changes."""
        self.sync_query_composition_entries_to_form()
        self.build_query_composition_rows.refresh()
        self.update_query_composition_preview()

    def update_query_composition_entry_preview(self, entry: dict[str, object]) -> None:
        """Update the interpreted preview for one advanced composition entry."""
        entry_id = self.ensure_query_composition_entry_id(entry)
        preview = self.query_composition_entry_previews.get(entry_id)
        if preview is None:
            return
        try:
            form_entry = build_query_composition_entries_form_state([entry])[0]
            preview.value = resolve_query_composition_entry_value(
                form_entry,
                modality=get_dataset_modality_value(self.form_values),
                interaction_type=get_dataset_interaction_type_value(self.form_values),
            )
        except (TypeError, ValueError) as exc:
            preview.value = f"Builder error: {exc}"

    def update_query_composition_preview(self, *_args: object) -> None:
        """Update the executable query.value preview for query_composition mode."""
        self.sync_query_composition_entries_to_form()
        if self.query_composition_preview is None:
            return
        try:
            descriptor = build_workflow_descriptor(self.form_values)
        except (TypeError, ValueError) as exc:
            self.query_composition_preview.value = f"Composition error: {exc}"
            return
        self.query_composition_preview.value = str(descriptor["query"]["value"])

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

    def build_chembl_ic50_builder_controls(self) -> None:
        """Build dedicated ChEMBL IC50 advanced builder controls."""
        with ui.column().classes("w-full gap-3"):
            self.build_chembl_ic50_builder_row()
            with ui.row().classes("items-center gap-3"):
                ui.button("Update query preview", on_click=self.update_builder_previews)

    @ui.refreshable
    def build_chembl_ic50_builder_row(self) -> None:
        """Build the dedicated ChEMBL IC50 query builder row."""
        row = self.chembl_ic50_builder_row
        normalize_chembl_ic50_ui_row_for_condition(row)
        with ui.row().classes("w-full items-end gap-3"):
            (
                ui.select(list(IC50_CONDITION_LABEL_TO_VALUE), label="Condition")
                .bind_value(row, "condition")
                .on_value_change(self.handle_chembl_ic50_condition_change)
                .classes("min-w-56")
                .tooltip("Choose whether the IC50 query uses a range, comparison, or exact value.")
            )
            minimum_input = (
                ui.number("Minimum", step=0.1)
                .bind_value(row, "minimum")
                .on_value_change(self.update_builder_previews)
                .classes("w-32")
                .tooltip("Required lower IC50 bound for range queries.")
            )
            minimum_input.bind_visibility_from(
                row,
                "condition",
                backward=is_chembl_ic50_range_condition,
            )
            maximum_input = (
                ui.number("Maximum", step=0.1)
                .bind_value(row, "maximum")
                .on_value_change(self.update_builder_previews)
                .classes("w-32")
                .tooltip("Required upper IC50 bound for range queries.")
            )
            maximum_input.bind_visibility_from(
                row,
                "condition",
                backward=is_chembl_ic50_range_condition,
            )
            value_input = (
                ui.number("Value", step=0.1)
                .bind_value(row, "value")
                .on_value_change(self.update_builder_previews)
                .classes("w-32")
                .tooltip("Required IC50 value for comparison and exact queries.")
            )
            value_input.bind_visibility_from(
                row,
                "condition",
                backward=is_chembl_ic50_value_condition,
            )
            (
                ui.select(list(IC50_UNIT_LABEL_TO_VALUE), label="Unit")
                .bind_value(row, "unit")
                .on_value_change(self.update_builder_previews)
                .classes("w-24")
                .tooltip("ChEMBL standard_units value for this IC50 query.")
            )

    def handle_chembl_ic50_condition_change(self, *_args: object) -> None:
        """Normalize visible ChEMBL IC50 state after condition changes."""
        normalize_chembl_ic50_ui_row_for_condition(self.chembl_ic50_builder_row)
        self.sync_builder_rows_to_form()
        self.build_chembl_ic50_builder_row.refresh()
        self.update_builder_previews()

    def build_pubchem_builder_controls(self) -> None:
        """Build PubChem-specific advanced builder controls."""
        with ui.column().classes("w-full gap-3"):
            ui.label(
                "Build a PubChem compound or structure query using one field. "
                "The final interpreted query is stored as query.value in the YAML."
            ).classes("text-sm text-gray-700")
            ui.label(
                "The threshold is required only for PubChem 2-D similarity searches."
            ).classes("text-sm text-gray-700")
            self.build_pubchem_builder_row()
            with ui.row().classes("items-center gap-3"):
                ui.button("Update query preview", on_click=self.update_builder_previews)

    @ui.refreshable
    def build_pubchem_builder_row(self) -> None:
        """Build the single PubChem query builder row."""
        builder_label = get_active_pubchem_builder_label(self.form_values["query.builder.key"])
        row = self.pubchem_builder_row
        field_help = get_pubchem_field_help(builder_label, row.get("field", ""))
        values_placeholder = str(get_pubchem_field_entry(builder_label, row.get("field", "")).placeholder)
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
                .tooltip("Enter the value for this PubChem lookup or structure search.")
            )
            threshold_input = (
                ui.number("Threshold", min=0, max=100, step=1)
                .bind_value(row, "threshold")
                .on_value_change(self.update_builder_previews)
                .classes("w-32")
                .tooltip("Required integer threshold from 0 to 100 for 2-D similarity searches.")
            )
            threshold_input.bind_visibility_from(
                row,
                "field",
                backward=lambda value: is_pubchem_similarity_field(builder_label, value),
            )
        ui.label(field_help).classes("text-xs text-gray-600")

    def handle_pubchem_builder_field_change(self, *_args: object) -> None:
        """Refresh PubChem field-specific threshold visibility and help."""
        builder_label = get_active_pubchem_builder_label(self.form_values["query.builder.key"])
        if is_pubchem_similarity_field(builder_label, self.pubchem_builder_row.get("field", "")):
            if self.pubchem_builder_row.get("threshold") in {None, ""}:
                self.pubchem_builder_row["threshold"] = 80
        else:
            self.pubchem_builder_row["threshold"] = None
        self.sync_builder_rows_to_form()
        self.build_pubchem_builder_row.refresh()
        self.update_builder_previews()

    def build_chebi_builder_controls(self) -> None:
        """Build ChEBI-specific advanced builder controls."""
        with ui.column().classes("w-full gap-3"):
            ui.label(
                "Build a ChEBI entity query using one field. "
                "The final interpreted query is stored as query.value in the YAML."
            ).classes("text-sm text-gray-700")
            self.build_chebi_builder_row()
            with ui.row().classes("items-center gap-3"):
                ui.button("Update query preview", on_click=self.update_builder_previews)

    @ui.refreshable
    def build_chebi_builder_row(self) -> None:
        """Build the single ChEBI entity query builder row."""
        builder_label = get_active_chebi_builder_label(self.form_values["query.builder.key"])
        row = self.chebi_builder_row
        field_help = get_chebi_field_help(builder_label, row.get("field", ""))
        values_placeholder = str(get_chebi_field_entry(builder_label, row.get("field", "")).placeholder)
        with ui.row().classes("w-full items-end gap-3"):
            (
                ui.select(get_chebi_field_options(builder_label), label="Field")
                .bind_value(row, "field")
                .on_value_change(self.handle_chebi_builder_field_change)
                .classes("min-w-72")
                .tooltip(field_help)
            )
            (
                ui.input("Value", placeholder=values_placeholder)
                .props("clearable")
                .bind_value(row, "value")
                .on_value_change(self.update_builder_previews)
                .classes("grow")
                .tooltip("Enter the value for this ChEBI entity query.")
            )
        ui.label(field_help).classes("text-xs text-gray-600")

    def handle_chebi_builder_field_change(self, *_args: object) -> None:
        """Refresh ChEBI field-specific help."""
        self.sync_builder_rows_to_form()
        self.build_chebi_builder_row.refresh()
        self.update_builder_previews()

    def handle_query_builder_change(self, *_args: object) -> None:
        """Refresh builder-specific controls after the selected builder changes."""
        if self.is_loading_form_values or self.is_refreshing_query_section:
            return
        builder_label = self.form_values["query.builder.key"]
        if builder_label == self.active_query_builder_label:
            return
        self.active_query_builder_label = str(builder_label)
        if is_chembl_ic50_builder_key(builder_label):
            self.chembl_ic50_builder_row = make_chembl_ic50_builder_ui_row()
        elif is_chembl_builder_key(builder_label):
            self.chembl_builder_rows = [make_chembl_builder_ui_row(builder_label)]
        elif is_pubchem_builder_key(builder_label):
            self.pubchem_builder_row = make_pubchem_builder_ui_row(builder_label)
        elif is_chebi_builder_key(builder_label):
            self.chebi_builder_row = make_chebi_builder_ui_row(builder_label)
        self.sync_builder_rows_to_form()
        self.refresh_query_section()

    def get_compatible_query_builder_labels(self) -> list[str]:
        """Return visible labels for builders compatible with current dataset settings."""
        choices = get_compatible_query_builder_choices(
            get_dataset_modality_value(self.form_values),
            get_dataset_interaction_type_value(self.form_values),
        )
        return list(choices.values())

    def is_current_query_builder_compatible(self) -> bool:
        """Return whether the selected builder is compatible with current dataset settings."""
        return self.form_values.get("query.builder.key") in self.get_compatible_query_builder_labels()

    def normalize_query_builder_state_for_context(self) -> None:
        """Normalize query-first builder state for the selected dataset context."""
        labels = self.get_compatible_query_builder_labels()
        builder_changed = False
        if labels:
            if not self.is_current_query_builder_compatible():
                self.form_values["query.builder.key"] = labels[0]
                builder_changed = True
            if is_chembl_ic50_builder_key(self.form_values["query.builder.key"]):
                if builder_changed:
                    self.chembl_ic50_builder_row = make_chembl_ic50_builder_ui_row()
            elif is_chembl_builder_key(self.form_values["query.builder.key"]):
                if builder_changed:
                    self.chembl_builder_rows = [
                        make_chembl_builder_ui_row(self.form_values["query.builder.key"])
                    ]
            elif is_pubchem_builder_key(self.form_values["query.builder.key"]):
                if builder_changed:
                    self.pubchem_builder_row = make_pubchem_builder_ui_row(
                        self.form_values["query.builder.key"]
                    )
            elif is_chebi_builder_key(self.form_values["query.builder.key"]):
                if builder_changed:
                    self.chebi_builder_row = make_chebi_builder_ui_row(self.form_values["query.builder.key"])
            elif builder_changed and is_uniprot_builder_key(self.form_values["query.builder.key"]):
                self.uniprot_builder_rows = [make_uniprot_builder_ui_row()]
            self.active_query_builder_label = str(self.form_values["query.builder.key"])
            self.sync_builder_rows_to_form()
            return

        self.form_values["query.input_mode"] = get_labeled_option_default(
            "manual",
            QUERY_INPUT_MODE_LABEL_TO_VALUE,
        )
        self.active_query_builder_label = str(self.form_values["query.builder.key"])

    def refresh_query_section(self) -> None:
        """Rebuild the Query section without refreshing stale child controls."""
        previous_refreshing_state = self.is_refreshing_query_section
        self.is_refreshing_query_section = True
        self.query_builder_select = None
        self.friendly_query_preview = None
        self.interpreted_query_preview = None
        self.query_composition_preview = None
        self.query_composition_entry_previews = {}
        try:
            self.build_query_controls.refresh()
        finally:
            self.is_refreshing_query_section = previous_refreshing_state

    def is_enrichment_context_compatible(self) -> bool:
        """Return whether the current workflow can run protein enrichment."""
        return is_enrichment_workflow_compatible(self.form_values)

    def clear_loaded_incompatible_enrichment_passthrough(self) -> None:
        """Mark loaded incompatible enrichment data as user-edited."""
        self.form_values.pop(LOADED_INCOMPATIBLE_ENRICHMENT_PASSTHROUGH_FORM_KEY, None)

    def update_enrichment_control_availability(self) -> None:
        """Enable enrichment toggle only for compatible protein workflows."""
        if self.enrichment_toggle_checkbox is None:
            return
        if self.is_enrichment_context_compatible():
            self.enrichment_toggle_checkbox.enable()
        else:
            self.enrichment_toggle_checkbox.disable()

    def handle_dataset_builder_context_change(self, *_args: object) -> None:
        """Refresh builder choices after dataset modality or interaction type changes."""
        if self.is_loading_form_values or self.is_refreshing_query_section:
            return
        self.clear_loaded_incompatible_enrichment_passthrough()
        self.is_refreshing_query_section = True
        try:
            self.update_interaction_type_visibility()
            if is_query_composition_workflow_mode(self.form_values["dataset.mode"]):
                for entry in self.get_query_composition_entries():
                    self.ensure_query_composition_entry_builder_state(entry)
                self.sync_query_composition_entries_to_form()
                self.refresh_query_section()
                return
            self.normalize_query_builder_state_for_context()
            self.refresh_query_section()
        finally:
            self.is_refreshing_query_section = False
            self.update_enrichment_control_availability()
            self.build_enrichment_controls.refresh()

    def handle_workflow_mode_change(self, *_args: object) -> None:
        """Rebuild query controls after switching workflow mode."""
        if self.is_loading_form_values or self.is_refreshing_query_section:
            return
        self.is_refreshing_query_section = True
        try:
            if is_query_composition_workflow_mode(self.form_values["dataset.mode"]):
                self.sync_query_composition_entries_to_form()
            else:
                self.normalize_query_builder_state_for_context()
                self.sync_builder_rows_to_form()
            self.refresh_query_section()
        finally:
            self.is_refreshing_query_section = False

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
        if is_chembl_ic50_builder_key(self.form_values["query.builder.key"]):
            self.form_values["query.chembl_ic50_builder.row"] = build_chembl_ic50_builder_form_row(
                self.chembl_ic50_builder_row
            )
        elif is_chembl_builder_key(self.form_values["query.builder.key"]):
            self.form_values["query.chembl_builder.rows"] = build_chembl_builder_form_rows(
                self.form_values["query.builder.key"],
                self.chembl_builder_rows,
            )
        elif is_pubchem_builder_key(self.form_values["query.builder.key"]):
            self.form_values["query.pubchem_builder.row"] = build_pubchem_builder_form_row(
                self.form_values["query.builder.key"],
                self.pubchem_builder_row,
            )
        elif is_chebi_builder_key(self.form_values["query.builder.key"]):
            self.form_values["query.chebi_builder.row"] = build_chebi_builder_form_row(
                self.form_values["query.builder.key"],
                self.chebi_builder_row,
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
            elif is_chembl_ic50_builder_key(builder_key):
                row = build_chembl_ic50_builder_row_from_form(self.form_values)
                friendly_query = build_chembl_ic50_friendly_query(row)
                interpreted_query = build_chembl_ic50_interpreted_query(row)
            elif is_chembl_builder_key(builder_key):
                rows = build_chembl_builder_rows_from_form(self.form_values)
                friendly_query = build_chembl_friendly_query(rows)
                interpreted_query = build_chembl_interpreted_query(rows)
            elif is_pubchem_builder_key(builder_key):
                row = build_pubchem_builder_row_from_form(self.form_values)
                friendly_query = build_pubchem_friendly_query(row)
                interpreted_query = build_pubchem_interpreted_query(row)
            else:
                row = build_chebi_builder_row_from_form(self.form_values)
                friendly_query = build_chebi_friendly_query(row)
                interpreted_query = build_chebi_interpreted_query(row)
        except ValueError as exc:
            self.friendly_query_preview.value = ""
            self.interpreted_query_preview.value = f"Builder error: {exc}"
            return
        self.friendly_query_preview.value = friendly_query
        self.interpreted_query_preview.value = interpreted_query

    def build_execution_controls(self) -> None:
        """Build execution form controls."""
        with ui.expansion("Execution", value=True).classes("w-full"):
            self.enrichment_toggle_checkbox = (
                ui.checkbox("Enable enrichment")
                .bind_value(self.form_values, "execution.enrich")
                .on_value_change(self.handle_enrichment_toggle)
                .tooltip("Enables supported enrichment steps when the workflow supports them.")
            )
            self.update_enrichment_control_availability()
            with ui.grid(columns=3).classes("w-full gap-3"):
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
            self.build_enrichment_controls()

    @ui.refreshable
    def build_enrichment_controls(self) -> None:
        """Build optional enrichment controls when enrichment is enabled."""
        self.enrichment_sources_select = None
        self.crossref_fields_input = None
        self.enrichment_required_fields_note = None
        self.enrichment_effective_fields_note = None
        if not self.is_enrichment_context_compatible() or not parse_bool(
            self.form_values.get("execution.enrich", False)
        ):
            return

        options = {source_key: label for label, source_key in get_enrichment_source_options().items()}
        with ui.column().classes("w-full gap-3 border-l-4 border-green-500 pl-3"):
            self.enrichment_sources_select = (
                ui.select(options, label="Enrichment sources", multiple=True)
                .bind_value(self.form_values, "execution.enrichment_sources")
                .on_value_change(self.handle_enrichment_sources_change)
                .classes("w-full")
                .tooltip("Select supported cross-reference enrichment sources.")
            )
            self.crossref_fields_input = (
                ui.input("Advanced cross-reference fields")
                .props('clearable placeholder="alphafold, biogrid, pathwaycommons_fetch"')
                .bind_value(self.form_values, "query.crossref_fields")
                .on_value_change(self.handle_crossref_fields_change)
                .classes("w-full")
                .tooltip(
                    "Comma-separated source keys or endpoint-specific fields. Custom values are "
                    "preserved even when they are not selectable above."
                )
            )
            self.enrichment_required_fields_note = ui.label("").classes("text-xs text-gray-600")
            self.enrichment_effective_fields_note = ui.label("").classes("text-xs text-gray-600")
            ui.label(
                "BioGRID requires API credential configuration. RefSeq requires Entrez email "
                "configuration."
            ).classes("text-xs text-gray-600")
            self.update_enrichment_field_notes()

    def update_enrichment_field_notes(self) -> None:
        """Update enrichment field requirement helper text."""
        crossref_fields = self.form_values.get("query.crossref_fields")
        required_fields = get_required_uniprot_return_field_text(crossref_fields)
        effective_fields = get_effective_uniprot_return_field_text(
            self.form_values.get("query.fields"),
            crossref_fields,
        )
        if self.enrichment_required_fields_note is not None:
            self.enrichment_required_fields_note.text = (
                f"Fields required by selected enrichment: {required_fields}."
                if required_fields
                else "Selected enrichment sources do not require extra UniProt fields."
            )
        if self.enrichment_effective_fields_note is not None:
            self.enrichment_effective_fields_note.text = (
                f"Effective UniProt request fields: {effective_fields}."
            )

    def handle_enrichment_toggle(self, event: object) -> None:
        """Show or hide enrichment source controls after a checkbox event."""
        if self.is_loading_form_values:
            return
        self.clear_loaded_incompatible_enrichment_passthrough()
        enrich_enabled = parse_bool(getattr(event, "value", False))
        self.form_values["execution.enrich"] = enrich_enabled
        if not self.is_enrichment_context_compatible():
            self.build_enrichment_controls.refresh()
            return
        if enrich_enabled:
            self.form_values["query.crossref_fields"] = crossref_fields_from_enrichment_sources(
                self.form_values.get("execution.enrichment_sources"),
                existing_crossref_fields=self.form_values.get("query.crossref_fields"),
            )
        else:
            self.form_values["query.crossref_fields"] = crossref_fields_without_selectable_sources(
                self.form_values.get("query.crossref_fields")
            )
        self.build_enrichment_controls.refresh()

    def handle_enrichment_sources_change(self, event: object) -> None:
        """Synchronize selected enrichment sources to cross-reference fields."""
        if self.is_loading_form_values:
            return
        self.clear_loaded_incompatible_enrichment_passthrough()
        if not self.is_enrichment_context_compatible():
            return
        sources = normalize_enrichment_sources(getattr(event, "value", []))
        self.form_values["execution.enrichment_sources"] = sources
        crossref_fields = crossref_fields_from_enrichment_sources(
            sources,
            existing_crossref_fields=self.form_values.get("query.crossref_fields"),
            preserve_known_existing=False,
        )
        self.form_values["query.crossref_fields"] = crossref_fields
        if self.crossref_fields_input is not None:
            self.crossref_fields_input.value = crossref_fields
            self.crossref_fields_input.update()
        self.update_enrichment_field_notes()

    def handle_crossref_fields_change(self, event: object) -> None:
        """Synchronize manual cross-reference fields to known source selections."""
        if self.is_loading_form_values:
            return
        self.clear_loaded_incompatible_enrichment_passthrough()
        crossref_fields = str(getattr(event, "value", "") or "")
        self.form_values["query.crossref_fields"] = crossref_fields
        sources = enrichment_sources_from_crossref_fields(crossref_fields)
        self.form_values["execution.enrichment_sources"] = sources
        if self.enrichment_sources_select is not None:
            self.enrichment_sources_select.value = sources
            self.enrichment_sources_select.update()
        self.update_enrichment_field_notes()

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
        if is_query_composition_workflow_mode(self.form_values["dataset.mode"]):
            self.sync_query_composition_entries_to_form()
        else:
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
        """Apply loaded descriptor values and synchronize visible widgets."""
        self.apply_loaded_form_values_to_state(loaded_form_values)
        self.sync_loaded_form_values_to_widgets()

    def apply_loaded_form_values_to_state(self, loaded_form_values: dict[str, object]) -> None:
        """Apply loaded form values to internal GUI state without touching widgets."""
        self.form_values.update(loaded_form_values)
        self.query_composition_entries = build_query_composition_entries_ui_state(
            self.form_values.get("query.composition.entries")
        )
        for entry in self.query_composition_entries:
            self.ensure_query_composition_entry_id(entry)
        state = build_gui_query_builder_state_from_loaded_form(self.form_values)
        self.form_values["query.input_mode"] = state["query_input_mode"]
        self.form_values["query.builder.key"] = state["builder_label"]
        self.active_query_builder_label = str(state["builder_label"])
        self.uniprot_builder_rows = cast("list[dict[str, object]]", state["uniprot_rows"])
        self.chembl_builder_rows = cast("list[dict[str, object]]", state["chembl_rows"])
        self.chembl_ic50_builder_row = cast("dict[str, object]", state["chembl_ic50_row"])
        self.pubchem_builder_row = cast("dict[str, object]", state["pubchem_row"])
        self.chebi_builder_row = cast("dict[str, object]", state["chebi_row"])

    def sync_loaded_form_values_to_widgets(self) -> None:
        """Refresh non-query widgets and rebuild the Query section from loaded state."""
        self.is_loading_form_values = True
        try:
            self.update_interaction_type_visibility()
            self.update_enrichment_control_availability()
            self.build_query_controls.refresh()
            self.build_enrichment_controls.refresh()
            if is_query_composition_workflow_mode(self.form_values["dataset.mode"]):
                self.sync_query_composition_entries_to_form()
                self.update_query_composition_preview()
            else:
                self.sync_loaded_query_builder_select()
                self.sync_builder_rows_to_form()
                self.update_builder_previews()
        finally:
            self.is_loading_form_values = False

    def sync_loaded_query_builder_select(self) -> None:
        """Keep the rebuilt query-builder select on the restored builder after YAML load."""
        if self.query_builder_select is None:
            return
        labels = self.get_compatible_query_builder_labels()
        restored_label = str(self.form_values["query.builder.key"])
        self.query_builder_select.options = labels
        if restored_label in labels:
            self.query_builder_select.value = restored_label
            self.form_values["query.builder.key"] = restored_label
            self.active_query_builder_label = restored_label
        self.query_builder_select.update()

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
    ui.run(
        root=create_app,
        title="BioSeqDownloader Workflow YAML Builder",
        reload=False,
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
