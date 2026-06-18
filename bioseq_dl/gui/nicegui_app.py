"""NiceGUI app for generating workflow-v1 YAML descriptors."""

from __future__ import annotations

from typing import Any

import yaml
from nicegui import ui

from bioseq_dl.gui.yaml_builder import (
    build_workflow_descriptor,
    render_workflow_yaml,
    validate_generated_descriptor,
    workflow_yaml_form_defaults,
)

DEFAULT_SAVE_FILENAME = "workflow.yml"


class WorkflowYamlBuilderApp:
    """Render and manage the BioSeqDownloader workflow YAML builder."""

    def __init__(self) -> None:
        """Initialize app state for form binding and status output."""
        self.form_values = workflow_yaml_form_defaults()
        self.yaml_output: Any = None
        self.status: Any = None

    def build(self) -> None:
        """Build the NiceGUI page."""
        ui.page_title("BioSeqDownloader Workflow YAML Builder")
        with ui.column().classes("w-full max-w-5xl mx-auto gap-4 p-4"):
            ui.label("BioSeqDownloader Workflow YAML Builder").classes("text-2xl font-semibold")
            ui.label(
                "Generate a validated workflow-v1 YAML file. This GUI does not execute workflows."
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
                ui.input("dataset.name").props("clearable").bind_value(self.form_values, "dataset.name")
                ui.select(
                    ["protein", "compound", "interaction"],
                    label="dataset.modality",
                ).bind_value(self.form_values, "dataset.modality")
                ui.select(
                    ["query_first", "query_composition"],
                    label="dataset.mode",
                ).bind_value(self.form_values, "dataset.mode")
                ui.select(
                    ["", "protein-protein", "protein-ligand"],
                    label="dataset.interaction_type",
                ).bind_value(self.form_values, "dataset.interaction_type")
            ui.textarea("dataset.description").bind_value(
                self.form_values,
                "dataset.description",
            ).classes("w-full")

    def build_query_controls(self) -> None:
        """Build query form controls."""
        with ui.expansion("Query", value=True).classes("w-full"):
            ui.textarea("query.value").bind_value(self.form_values, "query.value").classes("w-full")
            with ui.grid(columns=2).classes("w-full gap-3"):
                ui.input("query.fields").props("clearable").bind_value(
                    self.form_values,
                    "query.fields",
                )
                ui.input("query.crossref_fields").props("clearable").bind_value(
                    self.form_values,
                    "query.crossref_fields",
                )
                ui.checkbox("query.include_isoform").bind_value(
                    self.form_values,
                    "query.include_isoform",
                )

    def build_execution_controls(self) -> None:
        """Build execution form controls."""
        with ui.expansion("Execution", value=True).classes("w-full"), ui.grid(columns=3).classes(
            "w-full gap-3"
        ):
            ui.checkbox("execution.enrich").bind_value(self.form_values, "execution.enrich")
            ui.checkbox("execution.debug").bind_value(self.form_values, "execution.debug")
            ui.number("execution.max_workers", min=1, step=1).bind_value(
                self.form_values,
                "execution.max_workers",
            )
            ui.number("execution.total_retries", min=0, step=1).bind_value(
                self.form_values,
                "execution.total_retries",
            )
            ui.number("execution.chembl_pages_to_fetch", step=1).bind_value(
                self.form_values,
                "execution.chembl_pages_to_fetch",
            )
            ui.number("execution.uniprot_timeout", min=0, step=0.1).bind_value(
                self.form_values,
                "execution.uniprot_timeout",
            )

    def build_harmonization_controls(self) -> None:
        """Build harmonization form controls."""
        with ui.expansion("Harmonization", value=True).classes("w-full"):
            ui.input("harmonization.id_column").props("clearable").bind_value(
                self.form_values,
                "harmonization.id_column",
            )

    def build_export_controls(self) -> None:
        """Build export form controls."""
        with ui.expansion("Export", value=True).classes("w-full"), ui.grid(columns=2).classes(
            "w-full gap-3"
        ):
            ui.input("export.output_dir").props("clearable").bind_value(
                self.form_values,
                "export.output_dir",
            )
            ui.select(["csv", "json", "xml", "parquet"], label="export.format").bind_value(
                self.form_values,
                "export.format",
            )
            ui.input("export.manifest_file").props("clearable").bind_value(
                self.form_values,
                "export.manifest_file",
            )
            ui.input("export.summary_file").props("clearable").bind_value(
                self.form_values,
                "export.summary_file",
            )
            ui.checkbox("export.include_metadata").bind_value(
                self.form_values,
                "export.include_metadata",
            )
            ui.checkbox("export.include_summary").bind_value(
                self.form_values,
                "export.include_summary",
            )

    def build_preview_controls(self) -> None:
        """Build YAML preview controls."""
        with ui.expansion("YAML preview", value=True).classes("w-full"):
            with ui.row().classes("items-center gap-3"):
                ui.button("Generate YAML", on_click=self.generate_yaml)
                ui.button("Validate YAML", on_click=self.validate_yaml)
                ui.button("Save YAML", on_click=self.save_yaml)
            self.status = ui.label("")
            self.yaml_output = ui.textarea("Validated YAML").classes("w-full font-mono").props("rows=24")

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
        ui.download.content(str(self.yaml_output.value), DEFAULT_SAVE_FILENAME)
        self.status.text = f"Saved {DEFAULT_SAVE_FILENAME}."

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
