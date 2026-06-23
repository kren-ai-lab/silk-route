"""NiceGUI app for generating workflow-v1 YAML descriptors."""

from __future__ import annotations

from typing import Any

import yaml
from nicegui import ui

from bioseq_dl.gui.yaml_builder import (
    EXPORT_FORMAT_LABEL_TO_VALUE,
    INTERACTION_TYPE_LABEL_TO_VALUE,
    MODALITY_LABEL_TO_VALUE,
    OUTPUT_DIRECTORY_MODE_LABEL_TO_VALUE,
    WORKFLOW_MODE_LABEL_TO_VALUE,
    build_workflow_descriptor,
    build_workflow_filename,
    get_labeled_option_default,
    render_workflow_yaml,
    validate_generated_descriptor,
    workflow_yaml_form_defaults,
)


class WorkflowYamlBuilderApp:
    """Render and manage the BioSeqDownloader workflow YAML builder."""

    def __init__(self) -> None:
        """Initialize app state for form binding and status output."""
        self.form_values = workflow_yaml_form_defaults()
        self.form_values["dataset.modality"] = get_labeled_option_default(
            self.form_values["dataset.modality"],
            MODALITY_LABEL_TO_VALUE,
        )
        self.form_values["dataset.mode"] = get_labeled_option_default(
            self.form_values["dataset.mode"],
            WORKFLOW_MODE_LABEL_TO_VALUE,
        )
        self.form_values["dataset.interaction_type"] = get_labeled_option_default(
            self.form_values["dataset.interaction_type"],
            INTERACTION_TYPE_LABEL_TO_VALUE,
        )
        self.form_values["export.output_dir_mode"] = get_labeled_option_default(
            self.form_values["export.output_dir_mode"],
            OUTPUT_DIRECTORY_MODE_LABEL_TO_VALUE,
        )
        self.form_values["export.format"] = get_labeled_option_default(
            self.form_values["export.format"],
            EXPORT_FORMAT_LABEL_TO_VALUE,
        )
        self.yaml_output: Any = None
        self.status: Any = None

    def build(self) -> None:
        """Build the NiceGUI page."""
        ui.page_title("BioSeqDownloader Workflow YAML Builder")
        with ui.column().classes("w-full max-w-5xl mx-auto gap-4 p-4"):
            ui.label("BioSeqDownloader Workflow YAML Builder").classes("text-2xl font-semibold")
            ui.label(
                "This GUI only generates workflow-v1 YAML descriptors. "
                "It does not execute workflows or call external APIs."
            ).classes("text-sm text-gray-700")
            self.build_dataset_controls()
            self.build_query_controls()
            self.build_execution_controls()
            self.build_harmonization_controls()
            self.build_export_controls()
            self.build_preview_controls()

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
                (
                    ui.select(list(INTERACTION_TYPE_LABEL_TO_VALUE), label="Interaction type")
                    .bind_value(self.form_values, "dataset.interaction_type")
                    .tooltip(
                        "Only needed when Modality is Interaction. Choose No interaction for "
                        "protein or compound datasets."
                    )
                )
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
                "The GUI does not build queries automatically yet. "
                "Write the executable query.value manually."
            ).classes("text-sm text-gray-700")
            (
                ui.textarea("Executable query value")
                .bind_value(self.form_values, "query.value")
                .classes("w-full")
                .tooltip(
                    "The executable query string used by BioSeqDownloader. The GUI does not "
                    "build this automatically yet."
                )
            )
            with ui.grid(columns=2).classes("w-full gap-3"):
                (
                    ui.input("Return fields")
                    .props('clearable placeholder="accession, protein_name, organism_name, sequence"')
                    .bind_value(self.form_values, "query.fields")
                    .tooltip(
                        "Optional fields to request or keep when supported. Enter comma-separated "
                        "values."
                    )
                )
                (
                    ui.input("Cross-reference fields")
                    .props('clearable placeholder="xref_alphafolddb, xref_pdb, xref_string"')
                    .bind_value(self.form_values, "query.crossref_fields")
                    .tooltip(
                        "Optional database cross-references used by supported enrichment logic. "
                        "Enter comma-separated values."
                    )
                )
                (
                    ui.checkbox("Include UniProt isoforms")
                    .bind_value(self.form_values, "query.include_isoform")
                    .tooltip(
                        "Whether UniProt isoforms should be included when supported by the workflow."
                    )
                )

    def build_execution_controls(self) -> None:
        """Build execution form controls."""
        with ui.expansion("Execution", value=True).classes("w-full"), ui.grid(columns=3).classes(
            "w-full gap-3"
        ):
            (
                ui.checkbox("Enable enrichment")
                .bind_value(self.form_values, "execution.enrich")
                .tooltip("Enables supported enrichment steps when the workflow supports them.")
            )
            (
                ui.checkbox("Enable debug logging")
                .bind_value(self.form_values, "execution.debug")
                .tooltip(
                    "Enable more verbose debugging information in supported workflow operations."
                )
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
                    "This is preserved in the descriptor and does not rename output columns by "
                    "itself."
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
                    "Optional descriptive strategy name for sequence uniqueness handling. It "
                    "does not currently perform full deduplication."
                )
            )
            (
                ui.input("Metadata fields")
                .props('clearable placeholder="accession, protein_name, organism_name, sequence"')
                .bind_value(self.form_values, "harmonization.metadata_fields")
                .classes("col-span-2")
                .tooltip(
                    "Optional comma-separated list of metadata fields expected or relevant in "
                    "the output. This does not currently filter exported columns."
                )
            )

    def build_export_controls(self) -> None:
        """Build export form controls."""
        with ui.expansion("Export", value=True).classes("w-full"), ui.grid(columns=2).classes(
            "w-full gap-3"
        ):
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
                    "Directory used later when the YAML is executed. The GUI does not create it. "
                    "Absolute paths and '..' are not allowed."
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
