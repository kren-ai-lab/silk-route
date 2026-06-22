"""Pure helpers for generating validated workflow-v1 YAML descriptors."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import yaml

from bioseq_dl.workflow_schema_definition import (
    WORKFLOW_SCHEMA_VERSION,
    get_workflow_v1_schema_definition,
    validate_workflow_v1_descriptor,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

DEFAULT_MAX_WORKERS = 5
DEFAULT_TOTAL_RETRIES = 3
DEFAULT_CHEMBL_PAGES_TO_FETCH = -1

DEFAULT_FORM_VALUES: dict[str, object] = {
    "dataset.name": "",
    "dataset.description": "",
    "dataset.modality": "protein",
    "dataset.mode": "query_first",
    "dataset.interaction_type": "",
    "query.value": "",
    "query.fields": "",
    "query.crossref_fields": "",
    "query.include_isoform": False,
    "execution.enrich": True,
    "execution.max_workers": DEFAULT_MAX_WORKERS,
    "execution.total_retries": DEFAULT_TOTAL_RETRIES,
    "execution.chembl_pages_to_fetch": DEFAULT_CHEMBL_PAGES_TO_FETCH,
    "execution.uniprot_timeout": None,
    "execution.debug": False,
    "harmonization.id_column": "",
    "export.output_dir": "",
    "export.format": "csv",
    "export.include_metadata": True,
    "export.include_summary": True,
    "export.manifest_file": "metadata.json",
    "export.summary_file": "run_summary.yml",
}

FORM_VALUE_ALIASES: dict[str, tuple[str, ...]] = {
    "dataset.name": ("dataset_name",),
    "dataset.description": ("dataset_description",),
    "dataset.modality": ("dataset_modality",),
    "dataset.mode": ("dataset_mode",),
    "dataset.interaction_type": ("dataset_interaction_type",),
    "query.value": ("query_value",),
    "query.fields": ("query_fields",),
    "query.crossref_fields": ("query_crossref_fields",),
    "query.include_isoform": ("query_include_isoform",),
    "execution.enrich": ("execution_enrich",),
    "execution.max_workers": ("execution_max_workers",),
    "execution.total_retries": ("execution_total_retries",),
    "execution.chembl_pages_to_fetch": ("execution_chembl_pages_to_fetch",),
    "execution.uniprot_timeout": ("execution_uniprot_timeout",),
    "execution.debug": ("execution_debug",),
    "harmonization.id_column": ("harmonization_id_column",),
    "export.output_dir": ("export_output_dir",),
    "export.format": ("export_format",),
    "export.include_metadata": ("export_include_metadata",),
    "export.include_summary": ("export_include_summary",),
    "export.manifest_file": ("export_manifest_file",),
    "export.summary_file": ("export_summary_file",),
}


def workflow_yaml_form_defaults() -> dict[str, object]:
    """Return mutable default form values for GUI binding."""
    schema = get_workflow_v1_schema_definition()
    defaults = dict(DEFAULT_FORM_VALUES)
    for field_name in defaults:
        schema_default = schema.get(field_name, {}).get("default")
        if schema_default is not None:
            defaults[field_name] = schema_default
    return defaults


def get_form_value(form_values: Mapping[str, object], field_name: str) -> object:
    """Return a form value using canonical dotted names with legacy aliases."""
    if field_name in form_values:
        return form_values[field_name]
    for alias in FORM_VALUE_ALIASES.get(field_name, ()):
        if alias in form_values:
            return form_values[alias]
    return workflow_yaml_form_defaults()[field_name]


def parse_csv_list(value: object) -> list[str]:
    """Parse a comma-separated string into a list of non-empty values."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    normalized = str(value).replace("\r\n", "\n").replace("\n", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def is_empty_optional_value(value: object) -> bool:
    """Return whether a value should be removed from optional YAML fields."""
    if value is None:
        return True
    return value in ("", [], {})


def remove_empty_values(value: object) -> object:
    """Remove empty optional values from nested dictionaries and lists."""
    if isinstance(value, dict):
        cleaned_dict = {}
        for key, item in value.items():
            cleaned_item = remove_empty_values(item)
            if not is_empty_optional_value(cleaned_item):
                cleaned_dict[key] = cleaned_item
        return cleaned_dict
    if isinstance(value, list):
        cleaned_list = []
        for item in value:
            cleaned_item = remove_empty_values(item)
            if not is_empty_optional_value(cleaned_item):
                cleaned_list.append(cleaned_item)
        return cleaned_list
    if isinstance(value, str):
        return value.strip()
    return value


def parse_bool(value: object) -> bool:
    """Parse a boolean form value."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def parse_int(value: object, field_name: str) -> int:
    """Parse an integer form value."""
    if isinstance(value, bool):
        msg = f"{field_name} must be an integer."
        raise TypeError(msg)
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as exc:
        msg = f"{field_name} must be an integer."
        raise TypeError(msg) from exc


def parse_optional_number(value: object, field_name: str) -> float | int | None:
    """Parse an optional integer or float form value."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        msg = f"{field_name} must be numeric."
        raise TypeError(msg)
    if isinstance(value, int | float):
        return value
    try:
        parsed = float(str(value).strip())
    except ValueError as exc:
        msg = f"{field_name} must be numeric."
        raise TypeError(msg) from exc
    if parsed.is_integer():
        return int(parsed)
    return parsed


def add_optional_string(section: dict[str, object], key: str, value: object) -> None:
    """Add an optional string when it contains non-whitespace text."""
    if value is None:
        return
    cleaned = str(value).strip()
    if cleaned:
        section[key] = cleaned


def add_optional_list(section: dict[str, object], key: str, value: object) -> None:
    """Add an optional list when it contains values."""
    parsed = parse_csv_list(value)
    if parsed:
        section[key] = parsed


def build_dataset_section(form_values: Mapping[str, object]) -> dict[str, object]:
    """Build the workflow dataset section."""
    dataset: dict[str, object] = {
        "name": get_form_value(form_values, "dataset.name"),
        "description": get_form_value(form_values, "dataset.description"),
        "modality": get_form_value(form_values, "dataset.modality"),
        "mode": get_form_value(form_values, "dataset.mode"),
        "interaction_type": get_form_value(form_values, "dataset.interaction_type"),
    }
    return cast("dict[str, object]", remove_empty_values(dataset))


def build_query_section(form_values: Mapping[str, object]) -> dict[str, object]:
    """Build the workflow query section."""
    query: dict[str, object] = {
        "value": get_form_value(form_values, "query.value"),
        "include_isoform": parse_bool(get_form_value(form_values, "query.include_isoform")),
    }
    add_optional_list(query, "fields", get_form_value(form_values, "query.fields"))
    add_optional_list(query, "crossref_fields", get_form_value(form_values, "query.crossref_fields"))
    return cast("dict[str, object]", remove_empty_values(query))


def build_execution_section(form_values: Mapping[str, object]) -> dict[str, object]:
    """Build the workflow execution section."""
    execution: dict[str, object] = {
        "enrich": parse_bool(get_form_value(form_values, "execution.enrich")),
        "max_workers": parse_int(
            get_form_value(form_values, "execution.max_workers"),
            "execution.max_workers",
        ),
        "total_retries": parse_int(
            get_form_value(form_values, "execution.total_retries"),
            "execution.total_retries",
        ),
        "chembl_pages_to_fetch": parse_int(
            get_form_value(form_values, "execution.chembl_pages_to_fetch"),
            "execution.chembl_pages_to_fetch",
        ),
        "debug": parse_bool(get_form_value(form_values, "execution.debug")),
    }
    uniprot_timeout = parse_optional_number(
        get_form_value(form_values, "execution.uniprot_timeout"),
        "execution.uniprot_timeout",
    )
    if uniprot_timeout is not None:
        execution["uniprot_timeout"] = uniprot_timeout
    return execution


def build_harmonization_section(form_values: Mapping[str, object]) -> dict[str, object]:
    """Build the workflow harmonization section."""
    harmonization: dict[str, object] = {
        "id_column": get_form_value(form_values, "harmonization.id_column"),
    }
    return cast("dict[str, object]", remove_empty_values(harmonization))


def build_export_section(form_values: Mapping[str, object]) -> dict[str, object]:
    """Build the workflow export section."""
    export: dict[str, object] = {
        "output_dir": get_form_value(form_values, "export.output_dir"),
        "format": get_form_value(form_values, "export.format"),
        "include_metadata": parse_bool(get_form_value(form_values, "export.include_metadata")),
        "include_summary": parse_bool(get_form_value(form_values, "export.include_summary")),
        "manifest_file": get_form_value(form_values, "export.manifest_file"),
        "summary_file": get_form_value(form_values, "export.summary_file"),
    }
    return cast("dict[str, object]", remove_empty_values(export))


def build_workflow_descriptor(form_values: dict[str, object]) -> dict[str, object]:
    """Build a workflow-v1 descriptor from GUI form values."""
    return {
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "dataset": build_dataset_section(form_values),
        "query": build_query_section(form_values),
        "execution": build_execution_section(form_values),
        "harmonization": build_harmonization_section(form_values),
        "export": build_export_section(form_values),
    }


def render_workflow_yaml(descriptor: dict[str, object]) -> str:
    """Render a workflow descriptor as YAML text."""
    return yaml.safe_dump(descriptor, sort_keys=False, allow_unicode=True)


def collect_prevalidation_errors(descriptor: Mapping[str, object]) -> list[str]:
    """Return GUI-specific validation errors before workflow-v1 validation."""
    errors: list[str] = []
    dataset = descriptor.get("dataset")
    query = descriptor.get("query")
    if not isinstance(dataset, dict):
        errors.append("Missing dataset section.")
    else:
        if not dataset.get("name"):
            errors.append("dataset.name is required.")
        if dataset.get("modality") == "interaction" and not dataset.get("interaction_type"):
            errors.append("dataset.interaction_type is required when dataset.modality is 'interaction'.")
    if not isinstance(query, dict) or not query.get("value"):
        errors.append("query.value is required.")
    return errors


def validate_generated_descriptor(descriptor: dict[str, object]) -> list[str]:
    """Validate a generated descriptor and return user-facing error messages."""
    errors = collect_prevalidation_errors(descriptor)
    try:
        validate_workflow_v1_descriptor(descriptor)
    except (TypeError, ValueError) as exc:
        errors.append(str(exc))
    return list(dict.fromkeys(errors))
