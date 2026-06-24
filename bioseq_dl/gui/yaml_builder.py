"""Pure helpers for generating validated workflow-v1 YAML descriptors."""

from __future__ import annotations

import re
from collections.abc import Mapping
from copy import deepcopy
from pathlib import PurePosixPath, PureWindowsPath
from typing import cast

import yaml

from bioseq_dl.workflow_schema_definition import (
    WORKFLOW_SCHEMA_VERSION,
    get_workflow_v1_schema_definition,
    validate_workflow_v1_descriptor,
)

DEFAULT_MAX_WORKERS = 5
DEFAULT_TOTAL_RETRIES = 3
DEFAULT_CHEMBL_PAGES_TO_FETCH = -1
DEFAULT_WORKFLOW_FILENAME = "workflow-v1.yml"
LOADED_QUERY_VALUE_WARNING = (
    "Loaded query.value into Manual query mode. Advanced builder rows cannot be "
    "reconstructed because query.builder metadata is not currently stored."
)
QUERY_BUILDER_NOT_EDITABLE_WARNING = (
    "query.builder metadata was found but is not editable in this GUI version."
)
QUERY_COMPOSITION_NOT_EDITABLE_WARNING = (
    "query.composition metadata was found but is not editable in this GUI version."
)
NON_EDITABLE_METADATA_WARNINGS = {
    "resources": "resources metadata was found but is not editable in this GUI version.",
    "reporting": "reporting metadata was found but is not editable in this GUI version.",
    "interaction_retrieval": (
        "interaction_retrieval metadata was found but is not editable in this GUI version."
    ),
    "activity_retrieval": (
        "activity_retrieval metadata was found but is not editable in this GUI version."
    ),
    "chemical_metadata_integration": (
        "chemical_metadata_integration metadata was found but is not editable in this GUI version."
    ),
    "protein_target_integration": (
        "protein_target_integration metadata was found but is not editable in this GUI version."
    ),
    "temperature_enrichment": (
        "temperature_enrichment metadata was found but is not editable in this GUI version."
    ),
    "cross_source_integration": (
        "cross_source_integration metadata was found but is not editable in this GUI version."
    ),
}
UNSAFE_FILENAME_CHARACTERS = re.compile(r"[^a-z0-9_-]+")
REPEATED_FILENAME_SEPARATOR = re.compile(r"_+")

MODALITY_LABEL_TO_VALUE = {
    "Protein": "protein",
    "Compound": "compound",
    "Interaction": "interaction",
}
WORKFLOW_MODE_LABEL_TO_VALUE = {
    "Query First": "query_first",
    "Query Composition": "query_composition",
}
INTERACTION_TYPE_LABEL_TO_VALUE = {
    "No interaction": None,
    "Protein-protein interaction": "protein-protein",
    "Protein-ligand interaction": "protein-ligand",
}
EXPORT_FORMAT_LABEL_TO_VALUE = {
    "CSV": "csv",
    "JSON": "json",
    "XML": "xml",
    "Parquet": "parquet",
}
OUTPUT_DIRECTORY_MODE_LABEL_TO_VALUE = {
    "Use default results folder": "default",
    "Use custom relative path": "custom",
}
QUERY_INPUT_MODE_LABEL_TO_VALUE = {
    "Manual query": "manual",
    "Advanced builder": "advanced_builder",
}
UNIPROT_MATCH_MODE_LABEL_TO_VALUE = {
    "Any": "any",
    "All": "all",
    "Not": "not",
}
CHEMBL_BUILDER_RESOURCE_BY_KEY = {
    "chembl_target": "target",
    "chembl_assay": "assay",
    "chembl_cell_line": "cell_line",
    "chembl_molecule": "molecule",
    "chembl_activity": "activity",
}

DEFAULT_FORM_VALUES: dict[str, object] = {
    "dataset.name": "",
    "dataset.description": "",
    "dataset.modality": "protein",
    "dataset.mode": "query_first",
    "dataset.interaction_type": None,
    "query.input_mode": "manual",
    "query.builder.key": "uniprot",
    "query.value": "",
    "query.uniprot_builder.rows": [
        {
            "connector": None,
            "field": "organism",
            "values": "",
            "match_mode": "any",
        }
    ],
    "query.chembl_builder.rows": [
        {
            "field": "gene_symbol",
            "filter_type": "icontains",
            "value": "",
        }
    ],
    "query.fields": "",
    "query.crossref_fields": "",
    "query.include_isoform": False,
    "execution.enrich": False,
    "execution.max_workers": DEFAULT_MAX_WORKERS,
    "execution.total_retries": DEFAULT_TOTAL_RETRIES,
    "execution.chembl_pages_to_fetch": DEFAULT_CHEMBL_PAGES_TO_FETCH,
    "execution.uniprot_timeout": None,
    "execution.debug": False,
    "harmonization.id_column": "",
    "harmonization.label_column": "",
    "harmonization.sequence_column": "",
    "harmonization.unique_sequence_strategy": "",
    "harmonization.metadata_fields": "",
    "export.output_dir_mode": "default",
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
    "query.input_mode": ("query_input_mode",),
    "query.builder.key": ("query_builder_key",),
    "query.value": ("query_value",),
    "query.uniprot_builder.rows": ("query_uniprot_builder_rows",),
    "query.chembl_builder.rows": ("query_chembl_builder_rows",),
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
    "harmonization.label_column": ("harmonization_label_column",),
    "harmonization.sequence_column": ("harmonization_sequence_column",),
    "harmonization.unique_sequence_strategy": ("harmonization_unique_sequence_strategy",),
    "harmonization.metadata_fields": ("harmonization_metadata_fields",),
    "export.output_dir_mode": ("export_output_dir_mode",),
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
    defaults = deepcopy(DEFAULT_FORM_VALUES)
    for field_name in defaults:
        schema_default = schema.get(field_name, {}).get("default")
        if schema_default is not None:
            defaults[field_name] = schema_default
    return defaults


def workflow_yaml_gui_form_defaults() -> dict[str, object]:
    """Return mutable default form values using visible GUI labels."""
    defaults = workflow_yaml_form_defaults()
    defaults["dataset.modality"] = get_labeled_option_default(
        defaults["dataset.modality"],
        MODALITY_LABEL_TO_VALUE,
    )
    defaults["dataset.mode"] = get_labeled_option_default(
        defaults["dataset.mode"],
        WORKFLOW_MODE_LABEL_TO_VALUE,
    )
    defaults["dataset.interaction_type"] = get_labeled_option_default(
        defaults["dataset.interaction_type"],
        INTERACTION_TYPE_LABEL_TO_VALUE,
    )
    defaults["query.input_mode"] = get_labeled_option_default(
        defaults["query.input_mode"],
        QUERY_INPUT_MODE_LABEL_TO_VALUE,
    )
    defaults["export.output_dir_mode"] = get_labeled_option_default(
        defaults["export.output_dir_mode"],
        OUTPUT_DIRECTORY_MODE_LABEL_TO_VALUE,
    )
    defaults["export.format"] = get_labeled_option_default(
        defaults["export.format"],
        EXPORT_FORMAT_LABEL_TO_VALUE,
    )
    return defaults


def get_form_value(form_values: Mapping[str, object], field_name: str) -> object:
    """Return a form value using canonical dotted names with legacy aliases."""
    if field_name in form_values:
        return form_values[field_name]
    for alias in FORM_VALUE_ALIASES.get(field_name, ()):
        if alias in form_values:
            return form_values[alias]
    return workflow_yaml_form_defaults()[field_name]


def has_form_value(form_values: Mapping[str, object], field_name: str) -> bool:
    """Return whether canonical or legacy form data explicitly contains a field."""
    if field_name in form_values:
        return True
    return any(alias in form_values for alias in FORM_VALUE_ALIASES.get(field_name, ()))


def normalize_labeled_value(value: object, label_to_value: Mapping[str, object]) -> object:
    """Translate a human-readable form label to its workflow-v1 value."""
    if isinstance(value, str) and value in label_to_value:
        return label_to_value[value]
    return value


def get_labeled_option_default(value: object, label_to_value: Mapping[str, object]) -> str:
    """Return the human-readable label matching an internal option value."""
    for label, internal_value in label_to_value.items():
        if value == internal_value:
            return label
    return str(value)


def get_mapping_section(
    descriptor: Mapping[str, object],
    section_name: str,
) -> Mapping[str, object]:
    """Return a mapping section from a workflow descriptor, or an empty mapping."""
    section = descriptor.get(section_name)
    if isinstance(section, Mapping):
        return section
    return {}


def csv_text_from_value(value: object) -> str:
    """Convert a YAML string-list field into comma-separated GUI text."""
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()


def collect_load_warnings(descriptor: Mapping[str, object]) -> list[str]:
    """Return warnings for loaded metadata the GUI cannot edit."""
    warnings = []
    query = get_mapping_section(descriptor, "query")
    if query.get("value"):
        warnings.append(LOADED_QUERY_VALUE_WARNING)
    if "builder" in query:
        warnings.append(QUERY_BUILDER_NOT_EDITABLE_WARNING)
    if "composition" in query:
        warnings.append(QUERY_COMPOSITION_NOT_EDITABLE_WARNING)
    for section_name, warning in NON_EDITABLE_METADATA_WARNINGS.items():
        if section_name in descriptor:
            warnings.append(warning)
    return warnings


def load_workflow_yaml_text(yaml_text: str) -> dict[str, object]:
    """Parse workflow YAML text into a descriptor dictionary."""
    try:
        descriptor = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        msg = f"Invalid YAML: {exc}"
        raise ValueError(msg) from exc
    if not isinstance(descriptor, dict):
        msg = "Workflow YAML root must be a mapping."
        raise TypeError(msg)
    return cast("dict[str, object]", descriptor)


def descriptor_to_form_values(descriptor: Mapping[str, object]) -> dict[str, object]:
    """Convert a workflow-v1 descriptor into GUI form values."""
    form_values = workflow_yaml_gui_form_defaults()
    dataset = get_mapping_section(descriptor, "dataset")
    query = get_mapping_section(descriptor, "query")
    execution = get_mapping_section(descriptor, "execution")
    harmonization = get_mapping_section(descriptor, "harmonization")
    export = get_mapping_section(descriptor, "export")

    form_values["dataset.name"] = str(dataset.get("name") or "")
    form_values["dataset.description"] = str(dataset.get("description") or "")
    form_values["dataset.modality"] = get_labeled_option_default(
        dataset.get("modality", "protein"),
        MODALITY_LABEL_TO_VALUE,
    )
    form_values["dataset.mode"] = get_labeled_option_default(
        dataset.get("mode", "query_first"),
        WORKFLOW_MODE_LABEL_TO_VALUE,
    )
    form_values["dataset.interaction_type"] = get_labeled_option_default(
        dataset.get("interaction_type"),
        INTERACTION_TYPE_LABEL_TO_VALUE,
    )

    form_values["query.input_mode"] = get_labeled_option_default(
        "manual",
        QUERY_INPUT_MODE_LABEL_TO_VALUE,
    )
    form_values["query.value"] = str(query.get("value") or "")
    form_values["query.fields"] = csv_text_from_value(query.get("fields"))
    form_values["query.crossref_fields"] = csv_text_from_value(query.get("crossref_fields"))
    form_values["query.include_isoform"] = parse_bool(query.get("include_isoform", False))

    for key in (
        "enrich",
        "max_workers",
        "total_retries",
        "chembl_pages_to_fetch",
        "uniprot_timeout",
        "debug",
    ):
        field_name = f"execution.{key}"
        if key in execution:
            form_values[field_name] = execution[key]

    for key in ("id_column", "label_column", "sequence_column", "unique_sequence_strategy"):
        form_values[f"harmonization.{key}"] = str(harmonization.get(key) or "")
    form_values["harmonization.metadata_fields"] = csv_text_from_value(
        harmonization.get("metadata_fields")
    )

    output_dir = str(export.get("output_dir") or "").strip()
    if output_dir:
        form_values["export.output_dir_mode"] = get_labeled_option_default(
            "custom",
            OUTPUT_DIRECTORY_MODE_LABEL_TO_VALUE,
        )
        form_values["export.output_dir"] = output_dir
    else:
        form_values["export.output_dir_mode"] = get_labeled_option_default(
            "default",
            OUTPUT_DIRECTORY_MODE_LABEL_TO_VALUE,
        )
        form_values["export.output_dir"] = ""
    form_values["export.format"] = get_labeled_option_default(
        export.get("format", "csv"),
        EXPORT_FORMAT_LABEL_TO_VALUE,
    )
    for key in ("include_metadata", "include_summary", "manifest_file", "summary_file"):
        field_name = f"export.{key}"
        if key in export:
            form_values[field_name] = export[key]

    return form_values


def load_workflow_yaml_to_form_values(yaml_text: str) -> tuple[dict[str, object], list[str]]:
    """Parse, validate, and convert workflow YAML text to form values and warnings."""
    descriptor = load_workflow_yaml_text(yaml_text)
    validated_descriptor = validate_workflow_v1_descriptor(descriptor)
    form_values = descriptor_to_form_values(validated_descriptor)
    warnings = collect_load_warnings(validated_descriptor)
    return form_values, warnings



def normalize_query_input_mode(value: object) -> str:
    """Normalize the GUI query input mode."""
    if value == "Advanced UniProt builder":
        return "advanced_builder"
    normalized = normalize_labeled_value(value, QUERY_INPUT_MODE_LABEL_TO_VALUE)
    if normalized == "uniprot_builder":
        return "advanced_builder"
    if normalized in {"manual", "advanced_builder"}:
        return str(normalized)
    msg = f"Unsupported query input mode '{value}'."
    raise ValueError(msg)


def normalize_query_builder_key(value: object) -> str:
    """Normalize the selected advanced query builder key."""
    from bioseq_dl.gui.query_builders.registry import get_query_builder_choices  # noqa: PLC0415

    text = str(value or "uniprot").strip()
    choices = get_query_builder_choices()
    if text in choices:
        return text
    for key, label in choices.items():
        if text == label:
            return key
    msg = f"Unsupported query builder '{value}'."
    raise ValueError(msg)


def get_builder_row_value(row: object, key: str, default: object = "") -> object:
    """Return a value from a mapping-like or attribute-like builder row."""
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def normalize_uniprot_builder_match_mode(value: object) -> str:
    """Normalize a UniProt builder match mode label or value."""
    normalized = normalize_labeled_value(value, UNIPROT_MATCH_MODE_LABEL_TO_VALUE)
    return str(normalized).strip().lower()


def build_uniprot_builder_rows_from_form(form_values: Mapping[str, object]) -> list[object]:
    """Build pure UniProt query builder rows from GUI form values."""
    from bioseq_dl.gui.query_builders.uniprot import UniProtQueryBuilderRow  # noqa: PLC0415

    raw_rows = get_form_value(form_values, "query.uniprot_builder.rows")
    if not isinstance(raw_rows, list):
        msg = "Advanced UniProt builder rows must be a list."
        raise TypeError(msg)

    rows = []
    for index, raw_row in enumerate(raw_rows):
        connector = get_builder_row_value(raw_row, "connector", None)
        if index == 0 and str(connector or "").strip() == "":
            connector = None
        field = get_builder_row_value(raw_row, "field", "")
        values = get_builder_row_value(raw_row, "values", "")
        match_mode = normalize_uniprot_builder_match_mode(
            get_builder_row_value(raw_row, "match_mode", "any")
        )
        rows.append(
            UniProtQueryBuilderRow(
                connector=cast("str | None", connector),
                field=str(field),
                values=str(values),
                match_mode=match_mode,
            )
        )
    return rows


def build_chembl_builder_rows_from_form(form_values: Mapping[str, object]) -> list[object]:
    """Build pure ChEMBL query builder rows from GUI form values."""
    from bioseq_dl.gui.query_builders.chembl import ChEMBLFilterQueryBuilderRow  # noqa: PLC0415

    builder_key = normalize_query_builder_key(get_form_value(form_values, "query.builder.key"))
    if builder_key not in CHEMBL_BUILDER_RESOURCE_BY_KEY:
        msg = f"Query builder '{builder_key}' is not a ChEMBL builder."
        raise ValueError(msg)

    raw_rows = get_form_value(form_values, "query.chembl_builder.rows")
    if not isinstance(raw_rows, list):
        msg = "Advanced ChEMBL builder rows must be a list."
        raise TypeError(msg)

    resource = CHEMBL_BUILDER_RESOURCE_BY_KEY[builder_key]
    return [
        ChEMBLFilterQueryBuilderRow(
            resource=resource,
            field=str(get_builder_row_value(raw_row, "field", "")),
            filter_type=str(get_builder_row_value(raw_row, "filter_type", "")),
            value=str(get_builder_row_value(raw_row, "value", "")),
        )
        for raw_row in raw_rows
    ]


def resolve_query_value_from_form(form_values: Mapping[str, object]) -> str:
    """Resolve the executable query.value from manual or advanced query form values."""
    mode = normalize_query_input_mode(get_form_value(form_values, "query.input_mode"))
    if mode == "manual":
        return str(get_form_value(form_values, "query.value") or "").strip()

    builder_key = normalize_query_builder_key(get_form_value(form_values, "query.builder.key"))
    if builder_key == "uniprot":
        from bioseq_dl.gui.query_builders.uniprot import build_uniprot_interpreted_query  # noqa: PLC0415

        rows = build_uniprot_builder_rows_from_form(form_values)
        if not rows:
            msg = "Advanced UniProt builder requires at least one condition."
            raise ValueError(msg)
        return build_uniprot_interpreted_query(rows)

    if builder_key in CHEMBL_BUILDER_RESOURCE_BY_KEY:
        from bioseq_dl.gui.query_builders.chembl import build_chembl_interpreted_query  # noqa: PLC0415

        rows = build_chembl_builder_rows_from_form(form_values)
        if not rows:
            msg = "Advanced ChEMBL builder requires at least one condition."
            raise ValueError(msg)
        return build_chembl_interpreted_query(rows)

    msg = f"Unsupported query builder '{builder_key}'."
    raise ValueError(msg)


def parse_csv_list(value: object) -> list[str]:
    """Parse a comma-separated string into a list of non-empty values."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    normalized = str(value).replace("\r\n", "\n").replace("\n", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def build_workflow_filename(dataset_name: object) -> str:
    """Return a safe workflow-v1 download filename for a dataset name."""
    if dataset_name is None:
        return DEFAULT_WORKFLOW_FILENAME
    normalized_name = str(dataset_name).strip().lower()
    safe_name = UNSAFE_FILENAME_CHARACTERS.sub("_", normalized_name)
    safe_name = REPEATED_FILENAME_SEPARATOR.sub("_", safe_name).strip("_-")
    if not safe_name:
        return DEFAULT_WORKFLOW_FILENAME
    return f"{safe_name}.workflow-v1.yml"


def normalize_relative_output_path(value: object) -> str | None:
    """Normalize a safe relative output path for generated workflow YAML."""
    if value is None:
        return None
    normalized = str(value).strip().replace("\\", "/")
    if not normalized:
        return None

    posix_path = PurePosixPath(normalized)
    windows_path = PureWindowsPath(normalized)
    if posix_path.is_absolute() or windows_path.drive or windows_path.root:
        msg = "export.output_dir must be a relative path."
        raise ValueError(msg)
    if ".." in posix_path.parts:
        msg = "export.output_dir must not contain path traversal ('..')."
        raise ValueError(msg)

    cleaned_parts = [part for part in posix_path.parts if part not in {"", "."}]
    return "/".join(cleaned_parts) or None


def build_output_directory(form_values: Mapping[str, object]) -> str | None:
    """Build the output directory selected by the GUI form."""
    mode_value = get_form_value(form_values, "export.output_dir_mode")
    mode = normalize_labeled_value(mode_value, OUTPUT_DIRECTORY_MODE_LABEL_TO_VALUE)
    explicit_path = get_form_value(form_values, "export.output_dir")

    if not has_form_value(form_values, "export.output_dir_mode") and explicit_path:
        mode = "custom"
    if mode == "default":
        dataset_name = str(get_form_value(form_values, "dataset.name") or "").strip()
        if not dataset_name:
            return None
        return normalize_relative_output_path(f"results/{dataset_name}")
    if mode == "custom":
        return normalize_relative_output_path(explicit_path)

    msg = f"Unsupported output directory mode '{mode_value}'."
    raise ValueError(msg)


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
    modality = normalize_labeled_value(
        get_form_value(form_values, "dataset.modality"),
        MODALITY_LABEL_TO_VALUE,
    )
    dataset: dict[str, object] = {
        "name": get_form_value(form_values, "dataset.name"),
        "description": get_form_value(form_values, "dataset.description"),
        "modality": modality,
        "mode": normalize_labeled_value(
            get_form_value(form_values, "dataset.mode"),
            WORKFLOW_MODE_LABEL_TO_VALUE,
        ),
    }
    if modality == "interaction":
        dataset["interaction_type"] = normalize_labeled_value(
            get_form_value(form_values, "dataset.interaction_type"),
            INTERACTION_TYPE_LABEL_TO_VALUE,
        )
    return cast("dict[str, object]", remove_empty_values(dataset))


def build_query_section(form_values: Mapping[str, object]) -> dict[str, object]:
    """Build the workflow query section."""
    query: dict[str, object] = {
        "value": resolve_query_value_from_form(form_values),
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
        "label_column": get_form_value(form_values, "harmonization.label_column"),
        "sequence_column": get_form_value(form_values, "harmonization.sequence_column"),
        "unique_sequence_strategy": get_form_value(
            form_values,
            "harmonization.unique_sequence_strategy",
        ),
        "metadata_fields": parse_csv_list(
            get_form_value(form_values, "harmonization.metadata_fields")
        ),
    }
    return cast("dict[str, object]", remove_empty_values(harmonization))


def build_export_section(form_values: Mapping[str, object]) -> dict[str, object]:
    """Build the workflow export section."""
    export: dict[str, object] = {
        "output_dir": build_output_directory(form_values),
        "format": normalize_labeled_value(
            get_form_value(form_values, "export.format"),
            EXPORT_FORMAT_LABEL_TO_VALUE,
        ),
        "include_metadata": parse_bool(get_form_value(form_values, "export.include_metadata")),
        "include_summary": parse_bool(get_form_value(form_values, "export.include_summary")),
        "manifest_file": get_form_value(form_values, "export.manifest_file"),
        "summary_file": get_form_value(form_values, "export.summary_file"),
    }
    return cast("dict[str, object]", remove_empty_values(export))


def build_workflow_descriptor(form_values: dict[str, object]) -> dict[str, object]:
    """Build a workflow-v1 descriptor from GUI form values."""
    descriptor: dict[str, object] = {
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "dataset": build_dataset_section(form_values),
        "query": build_query_section(form_values),
        "execution": build_execution_section(form_values),
    }
    harmonization = build_harmonization_section(form_values)
    if harmonization:
        descriptor["harmonization"] = harmonization
    descriptor["export"] = build_export_section(form_values)
    return descriptor


def render_workflow_yaml(descriptor: dict[str, object]) -> str:
    """Render a workflow descriptor as YAML text."""
    return yaml.safe_dump(descriptor, sort_keys=False, allow_unicode=True)


def collect_prevalidation_errors(descriptor: Mapping[str, object]) -> list[str]:
    """Return GUI-specific validation errors before workflow-v1 validation."""
    errors: list[str] = []
    dataset = descriptor.get("dataset")
    query = descriptor.get("query")
    export = descriptor.get("export")
    if not isinstance(dataset, dict):
        errors.append("Missing dataset section.")
    else:
        output_dir = export.get("output_dir") if isinstance(export, dict) else None
        if not dataset.get("name") and not output_dir:
            errors.append("dataset.name is required when export.output_dir is not provided.")
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
