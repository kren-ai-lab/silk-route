"""Lightweight workflow-v1 schema metadata for YAML generators."""

from __future__ import annotations

import datetime as dt
from copy import deepcopy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

WORKFLOW_SCHEMA_VERSION = "workflow-v1"
MODALITIES = ["protein", "compound", "interaction"]
MODES = ["query_first", "query_composition"]
INTERACTION_TYPES = ["protein-protein", "protein-ligand"]
FORMATS = ["csv", "json", "xml", "parquet"]

REQUIRED_DESCRIPTOR_SECTIONS = {"dataset", "query", "execution", "export"}
CORE_DESCRIPTOR_SECTIONS = REQUIRED_DESCRIPTOR_SECTIONS | {
    "resources",
    "harmonization",
    "reporting",
}
DESCRIPTIVE_DESCRIPTOR_SECTIONS = {
    "interaction_retrieval",
    "activity_retrieval",
    "chemical_metadata_integration",
    "protein_target_integration",
    "temperature_enrichment",
    "cross_source_integration",
}
ALLOWED_DESCRIPTOR_SECTION_NAMES = [
    "schema_version",
    "dataset",
    "query",
    "resources",
    "execution",
    "harmonization",
    "export",
    "reporting",
    "interaction_retrieval",
    "activity_retrieval",
    "chemical_metadata_integration",
    "protein_target_integration",
    "temperature_enrichment",
    "cross_source_integration",
]
KNOWN_DESCRIPTOR_SECTIONS = CORE_DESCRIPTOR_SECTIONS | DESCRIPTIVE_DESCRIPTOR_SECTIONS | {"schema_version"}

DATASET_KEYS = {
    "name",
    "description",
    "modality",
    "mode",
    "primary_data_source",
    "interaction_type",
}
QUERY_KEYS = {
    "value",
    "builder",
    "composition",
    "description",
    "filtering_strategy",
    "fields",
    "crossref_fields",
    "include_isoform",
}
RESOURCES_KEYS = {"primary", "integration"}
EXECUTION_KEYS = {
    "enrich",
    "download_alphafold_structures",
    "download_pdb_structures",
    "max_workers",
    "total_retries",
    "chembl_pages_to_fetch",
    "merge_results",
    "uniprot_timeout",
    "debug",
}
HARMONIZATION_KEYS = {
    "id_column",
    "label_column",
    "sequence_column",
    "unique_sequence_strategy",
    "metadata_fields",
}
EXPORT_KEYS = {
    "output_dir",
    "format",
    "include_metadata",
    "include_summary",
    "manifest_file",
    "summary_file",
    "result_files",
}

OLD_ROOT_KEY_ERRORS = {
    "version": (f"Unknown workflow YAML key 'version'. Use schema_version: \"{WORKFLOW_SCHEMA_VERSION}\"."),
    "kind": "Unknown workflow YAML key 'kind'. Use the structured dataset/query/execution/export schema.",
    "workflow": (
        "Unknown workflow YAML key 'workflow'. Use the structured dataset/query/execution/export schema."
    ),
}
OLD_MODE_KEY_ERROR_MESSAGES = [
    "Unknown workflow YAML key 'dispatch_mode'. Use dataset.mode instead.",
    "Unknown workflow YAML key 'dispatch'. Use dataset.mode instead.",
    "Unknown workflow YAML key 'method'. Use dataset.mode instead.",
]
QUERY_KEY_ERRORS = {
    "type": "Unknown query YAML key 'type'. Query type is not supported yet; use query.value.",
    "filters": (
        "Unknown query YAML key 'filters'. Use query.filtering_strategy for descriptive filtering notes."
    ),
}
FORBIDDEN_CREDENTIAL_KEYS = {
    "api_key",
    "access_key",
    "password",
    "email",
    "token",
    "secret",
    "bioseq_dl_biogrid_api_key",
    "bioseq_dl_brenda_email",
    "bioseq_dl_brenda_password",
    "bioseq_dl_refseq_email",
}
CREDENTIAL_ERROR = "Credentials must be provided through environment variables or .env, not workflow YAML."
DATAFRAME_EXPORT_FORMAT_ERROR = "Unsupported export format 'dataframe'. Use 'csv' instead."

_WORKFLOW_V1_SCHEMA_DEFINITION: dict[str, object] = {
    "schema_version": {
        "type": "string",
        "required": True,
        "default": WORKFLOW_SCHEMA_VERSION,
        "allowed_values": [WORKFLOW_SCHEMA_VERSION],
        "role": "required_input",
        "description": "Workflow schema version.",
        "gui_visible": False,
    },
    "dataset.name": {
        "type": "string",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Dataset name used for metadata and default output directory.",
        "gui_visible": True,
    },
    "dataset.description": {
        "type": "string",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Human-readable dataset description.",
        "gui_visible": True,
    },
    "dataset.modality": {
        "type": "enum",
        "required": True,
        "default": "protein",
        "allowed_values": ["protein", "compound", "interaction"],
        "role": "required_input",
        "description": "Workflow modality.",
        "gui_visible": True,
    },
    "dataset.mode": {
        "type": "enum",
        "required": True,
        "default": "query_first",
        "allowed_values": ["query_first", "query_composition"],
        "role": "required_input",
        "description": "Workflow execution mode.",
        "gui_visible": True,
    },
    "dataset.interaction_type": {
        "type": "enum",
        "required": False,
        "default": None,
        "allowed_values": ["protein-protein", "protein-ligand"],
        "role": "optional_input",
        "description": "Interaction type required when dataset.modality is interaction.",
        "gui_visible": True,
    },
    "query.value": {
        "type": "string",
        "required": True,
        "default": None,
        "allowed_values": None,
        "role": "required_input",
        "description": "Executable query string.",
        "gui_visible": True,
    },
    "query.fields": {
        "type": "string_list",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Optional UniProt fields request parameter.",
        "gui_visible": True,
    },
    "query.crossref_fields": {
        "type": "string_list",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Optional cross-reference fields for supported enrichment paths.",
        "gui_visible": True,
    },
    "query.include_isoform": {
        "type": "boolean",
        "required": False,
        "default": False,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Whether UniProt requests should include isoforms.",
        "gui_visible": True,
    },
    "query.builder": {
        "type": "mapping",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "preserved_metadata",
        "description": "GUI-oriented metadata kept for future builder reconstruction.",
        "gui_visible": False,
    },
    "query.composition": {
        "type": "list",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "preserved_metadata",
        "description": "Preserved composition metadata. It must match query.value when present.",
        "gui_visible": False,
    },
    "execution.enrich": {
        "type": "boolean",
        "required": False,
        "default": False,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Enable supported enrichment behavior.",
        "gui_visible": True,
    },
    "execution.download_alphafold_structures": {
        "type": "boolean",
        "required": False,
        "default": False,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Download AlphaFold PDB structure files during AlphaFold enrichment.",
        "gui_visible": False,
    },
    "execution.download_pdb_structures": {
        "type": "boolean",
        "required": False,
        "default": False,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Download local PDB structure files during PDB enrichment.",
        "gui_visible": False,
    },
    "execution.max_workers": {
        "type": "integer",
        "required": False,
        "default": 5,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Worker count for supported workflow and enrichment paths.",
        "gui_visible": True,
    },
    "execution.total_retries": {
        "type": "integer",
        "required": False,
        "default": 3,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Retry count for supported interfaces.",
        "gui_visible": True,
    },
    "execution.chembl_pages_to_fetch": {
        "type": "integer",
        "required": False,
        "default": -1,
        "allowed_values": None,
        "role": "optional_input",
        "description": "ChEMBL page cap. Use -1 for all pages or a positive integer.",
        "gui_visible": True,
    },
    "execution.uniprot_timeout": {
        "type": "number",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Optional UniProt request timeout.",
        "gui_visible": True,
    },
    "execution.debug": {
        "type": "boolean",
        "required": False,
        "default": False,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Enable debug logging.",
        "gui_visible": True,
    },
    "harmonization.id_column": {
        "type": "string",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Optional deterministic row identifier column for tabular exports.",
        "gui_visible": True,
    },
    "harmonization.label_column": {
        "type": "string",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Optional label or group column preserved in the descriptor.",
        "gui_visible": True,
    },
    "harmonization.sequence_column": {
        "type": "string",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Optional biological sequence column used for reporting when present.",
        "gui_visible": True,
    },
    "export.output_dir": {
        "type": "string",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Output directory.",
        "gui_visible": True,
    },
    "export.format": {
        "type": "enum",
        "required": False,
        "default": "csv",
        "allowed_values": ["csv", "json", "xml", "parquet"],
        "role": "optional_input",
        "description": "Output format.",
        "gui_visible": True,
    },
    "export.include_metadata": {
        "type": "boolean",
        "required": False,
        "default": True,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Write metadata.json.",
        "gui_visible": True,
    },
    "export.include_summary": {
        "type": "boolean",
        "required": False,
        "default": True,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Write run_summary.yml.",
        "gui_visible": True,
    },
    "export.manifest_file": {
        "type": "string",
        "required": False,
        "default": "metadata.json",
        "allowed_values": None,
        "role": "optional_input",
        "description": "Metadata manifest filename.",
        "gui_visible": True,
    },
    "export.summary_file": {
        "type": "string",
        "required": False,
        "default": "run_summary.yml",
        "allowed_values": None,
        "role": "optional_input",
        "description": "Run summary filename.",
        "gui_visible": True,
    },
    "resources.primary": {
        "type": "string_list",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "future_feature",
        "description": "Future resource-driven routing metadata.",
        "gui_visible": False,
    },
    "resources.integration": {
        "type": "string_list",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "future_feature",
        "description": "Future resource-driven integration metadata.",
        "gui_visible": False,
    },
    "export.result_files": {
        "type": "mapping",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "future_feature",
        "description": "Future user-defined output filename control.",
        "gui_visible": False,
    },
    "harmonization.unique_sequence_strategy": {
        "type": "string",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Optional descriptive sequence uniqueness strategy.",
        "gui_visible": True,
    },
    "harmonization.metadata_fields": {
        "type": "string_list",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Optional metadata fields expected or relevant in output.",
        "gui_visible": True,
    },
    "interaction_retrieval": {
        "type": "mapping",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "future_feature",
        "description": "Future explicit PPI or PLI retrieval configuration.",
        "gui_visible": False,
    },
    "activity_retrieval": {
        "type": "mapping",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "future_feature",
        "description": "Future explicit activity retrieval configuration.",
        "gui_visible": False,
    },
    "chemical_metadata_integration": {
        "type": "mapping",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "future_feature",
        "description": "Future compound metadata integration configuration.",
        "gui_visible": False,
    },
    "protein_target_integration": {
        "type": "mapping",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "future_feature",
        "description": "Future protein target metadata integration configuration.",
        "gui_visible": False,
    },
    "temperature_enrichment": {
        "type": "mapping",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "future_feature",
        "description": "Future temperature metadata enrichment configuration.",
        "gui_visible": False,
    },
    "cross_source_integration": {
        "type": "mapping",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "future_feature",
        "description": "Future cross-source integration rule configuration.",
        "gui_visible": False,
    },
}


def get_workflow_v1_schema_definition() -> dict[str, object]:
    """Return the workflow-v1 schema definition used by YAML generators."""
    return deepcopy(_WORKFLOW_V1_SCHEMA_DEFINITION)


def check_forbidden_workflow_recipe_keys(value: object) -> None:
    """Reject credential-like keys anywhere in a workflow descriptor."""
    if isinstance(value, dict):
        for key, nested_value in value.items():
            if str(key).lower() in FORBIDDEN_CREDENTIAL_KEYS:
                raise ValueError(CREDENTIAL_ERROR)
            check_forbidden_workflow_recipe_keys(nested_value)
    elif isinstance(value, list):
        for item in value:
            check_forbidden_workflow_recipe_keys(item)


def require_mapping(section_name: str, value: object) -> dict[str, object]:
    """Return a section as a string-keyed mapping."""
    if not isinstance(value, dict):
        msg = f"Workflow YAML section '{section_name}' must be a mapping."
        raise TypeError(msg)
    return {str(key): item for key, item in value.items()}


def validate_allowed_section_keys(
    section_name: str,
    section: dict[str, object],
    allowed_keys: set[str],
    special_errors: dict[str, str] | None = None,
) -> None:
    """Validate known keys for a descriptor section."""
    for key in section:
        if special_errors and key in special_errors:
            raise ValueError(special_errors[key])
        if key not in allowed_keys:
            msg = f"Unknown {section_name} YAML key '{key}'."
            raise ValueError(msg)


def get_rejected_mode_key_message(key: str) -> str | None:
    """Return the validation message for removed workflow mode keys."""
    for message in OLD_MODE_KEY_ERROR_MESSAGES:
        if key == message.split("'")[1]:
            return message
    return None


def validate_descriptor_section_names(workflow_descriptor: dict[str, object]) -> None:
    """Validate top-level workflow descriptor section names."""
    allowed_sections = ", ".join(ALLOWED_DESCRIPTOR_SECTION_NAMES)
    for key in workflow_descriptor:
        rejected_mode_message = get_rejected_mode_key_message(key)
        if rejected_mode_message:
            raise ValueError(rejected_mode_message)
        if key in OLD_ROOT_KEY_ERRORS:
            raise ValueError(OLD_ROOT_KEY_ERRORS[key])
        if key not in KNOWN_DESCRIPTOR_SECTIONS:
            msg = f"Unknown workflow YAML section '{key}'. Allowed sections are: {allowed_sections}."
            raise ValueError(msg)


def validate_schema_version(workflow_descriptor: dict[str, object]) -> str:
    """Validate the required workflow schema version."""
    if "schema_version" not in workflow_descriptor:
        msg = (
            "Workflow YAML is missing required top-level key 'schema_version'. "
            f'Use schema_version: "{WORKFLOW_SCHEMA_VERSION}".'
        )
        raise ValueError(msg)

    schema_version = workflow_descriptor["schema_version"]
    if schema_version != WORKFLOW_SCHEMA_VERSION:
        msg = (
            f"Unsupported workflow schema_version '{schema_version}'. "
            f'Only schema_version: "{WORKFLOW_SCHEMA_VERSION}" is supported.'
        )
        raise ValueError(msg)
    return schema_version


def validate_required_section_keys(
    section_name: str,
    section: dict[str, object],
    required_keys: set[str],
) -> None:
    """Validate that a descriptor section contains required keys."""
    missing = sorted(key for key in required_keys if key not in section or section[key] is None)
    if missing:
        missing_text = ", ".join(missing)
        msg = f"Workflow YAML section '{section_name}' is missing required key(s): {missing_text}."
        raise ValueError(msg)


def validate_optional_string(section_name: str, key: str, value: object) -> None:
    """Validate an optional string field."""
    if value is not None and not isinstance(value, str):
        msg = f"Workflow YAML key '{section_name}.{key}' must be a string or null."
        raise ValueError(msg)


def validate_bool(section_name: str, key: str, value: object) -> None:
    """Validate a boolean field."""
    if not isinstance(value, bool):
        msg = f"Workflow YAML key '{section_name}.{key}' must be a boolean."
        raise TypeError(msg)


def validate_int(section_name: str, key: str, value: object) -> None:
    """Validate an integer field without accepting booleans."""
    if isinstance(value, bool) or not isinstance(value, int):
        msg = f"Workflow YAML key '{section_name}.{key}' must be an integer."
        raise TypeError(msg)


def validate_numeric_or_null(section_name: str, key: str, value: object) -> None:
    """Validate a numeric or null field without accepting booleans."""
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
        msg = f"Workflow YAML key '{section_name}.{key}' must be numeric or null."
        raise ValueError(msg)


def validate_pages_to_fetch(section_name: str, key: str, value: object) -> None:
    """Validate a ChEMBL page count where -1 means all pages."""
    validate_int(section_name, key, value)
    if value == 0 or (isinstance(value, int) and value < -1):
        msg = f"Workflow YAML key '{section_name}.{key}' must be -1 or a positive integer."
        raise ValueError(msg)


def validate_string_list(section_name: str, key: str, value: object) -> None:
    """Validate a list containing only strings."""
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        msg = f"Workflow YAML key '{section_name}.{key}' must be a list of strings."
        raise ValueError(msg)


def validate_query_builder(value: object) -> None:
    """Validate optional GUI query-builder metadata."""
    if value is not None and not isinstance(value, dict):
        msg = "Workflow YAML key 'query.builder' must be a mapping."
        raise TypeError(msg)


def validate_query_composition(value: object) -> None:
    """Validate optional GUI query-composition metadata."""
    if value is None:
        return
    if not isinstance(value, list):
        msg = "Workflow YAML key 'query.composition' must be a list of mappings."
        raise TypeError(msg)
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            msg = f"Workflow YAML key 'query.composition[{index}]' must be a mapping."
            raise TypeError(msg)
        for required_key in ("label", "value"):
            required_value = item.get(required_key)
            if not isinstance(required_value, str) or not required_value.strip():
                msg = (
                    f"Workflow YAML key 'query.composition[{index}].{required_key}' "
                    "must be a non-empty string."
                )
                raise ValueError(msg)
        description = item.get("description")
        if "description" in item and description is not None and not isinstance(description, str):
            msg = f"Workflow YAML key 'query.composition[{index}].description' must be a string or null."
            raise ValueError(msg)
        builder = item.get("builder")
        if "builder" in item and not isinstance(builder, dict):
            msg = f"Workflow YAML key 'query.composition[{index}].builder' must be a mapping."
            raise TypeError(msg)


def parse_query_composition_value(query_value: str) -> list[tuple[str, str]]:
    """Parse executable query-composition pairs from query.value."""
    pairs = []
    for raw_part in query_value.split(","):
        query_part = raw_part.strip()
        if not query_part:
            continue
        if "=" not in query_part:
            msg = "query.composition does not match executable query.value."
            raise ValueError(msg)
        query_text, label = query_part.rsplit("=", 1)
        query_text = query_text.strip()
        label = label.strip()
        if not query_text or not label:
            msg = "query.composition does not match executable query.value."
            raise ValueError(msg)
        pairs.append((query_text, label))
    if not pairs:
        msg = "query.composition does not match executable query.value."
        raise ValueError(msg)
    return pairs


def validate_query_composition_matches_query_value(
    query_descriptor: dict[str, object],
    mode: object,
) -> None:
    """Require preserved query.composition metadata to match executable query.value."""
    composition = query_descriptor.get("composition")
    if mode != "query_composition" or composition is None:
        return

    executable_pairs = parse_query_composition_value(str(query_descriptor["value"]))
    executable_pair_set = set(executable_pairs)
    composition_pair_set = {(item["value"].strip(), item["label"].strip()) for item in composition}
    if composition_pair_set != executable_pair_set:
        msg = "query.composition does not match executable query.value."
        raise ValueError(msg)


def normalize_optional_field_list(section_name: str, key: str, value: object) -> str | None:
    """Normalize null, comma-separated string, or string-list fields for workflow calls."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        cleaned = [item.strip() for item in value if item.strip()]
        return ",".join(cleaned) if cleaned else None
    msg = f"Workflow YAML key '{section_name}.{key}' must be null, a string, or a list of strings."
    raise ValueError(msg)


def is_reporting_value_allowed(value: object) -> bool:
    """Return whether a reporting value is YAML-descriptor safe."""
    if value is None or isinstance(value, (str, int, float, bool, dt.date, dt.datetime)):
        return True
    if isinstance(value, list):
        return all(is_reporting_value_allowed(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and is_reporting_value_allowed(item) for key, item in value.items())
    return False


def validate_reporting_section(reporting: dict[str, object]) -> None:
    """Validate free-form reporting metrics."""
    for key, value in reporting.items():
        if not is_reporting_value_allowed(value):
            msg = f"Workflow YAML key 'reporting.{key}' has an unsupported value type."
            raise ValueError(msg)


def validate_dataset_section(
    dataset: dict[str, object],
    export_section: dict[str, object],
) -> dict[str, object]:
    """Validate and return the dataset descriptor section."""
    validate_allowed_section_keys("dataset", dataset, DATASET_KEYS)
    validate_required_section_keys("dataset", dataset, {"modality", "mode"})

    modality = dataset.get("modality")
    mode = dataset.get("mode")
    if modality not in MODALITIES:
        supported_modalities = ", ".join(MODALITIES)
        msg = f"Unsupported dataset.modality '{modality}'. Supported modalities are: {supported_modalities}."
        raise ValueError(msg)
    if mode not in MODES:
        msg = f"Unsupported dataset.mode '{mode}'. Supported modes are: {', '.join(MODES)}."
        raise ValueError(msg)

    for key in ("name", "description", "primary_data_source", "interaction_type"):
        validate_optional_string("dataset", key, dataset.get(key))

    interaction_type = dataset.get("interaction_type")
    if modality == "interaction" and not interaction_type:
        msg = "dataset.interaction_type is required when dataset.modality is 'interaction'."
        raise ValueError(msg)
    if interaction_type is not None and interaction_type not in INTERACTION_TYPES:
        msg = (
            f"Unsupported dataset.interaction_type '{interaction_type}'. "
            f"Supported interaction types are: {', '.join(INTERACTION_TYPES)}."
        )
        raise ValueError(msg)

    if not export_section.get("output_dir") and not dataset.get("name"):
        msg = "dataset.name is required when export.output_dir is not provided."
        raise ValueError(msg)
    return dict(dataset)


def validate_query_section(query_section: dict[str, object]) -> dict[str, object]:
    """Validate and return the query descriptor section."""
    validate_allowed_section_keys("query", query_section, QUERY_KEYS, special_errors=QUERY_KEY_ERRORS)
    validate_required_section_keys("query", query_section, {"value"})

    query_value = query_section.get("value")
    if not isinstance(query_value, str) or not query_value.strip():
        msg = "Workflow YAML key 'query.value' must be a non-empty string."
        raise ValueError(msg)

    for key in ("description", "filtering_strategy"):
        validate_optional_string("query", key, query_section.get(key))
    validate_query_builder(query_section.get("builder"))
    validate_query_composition(query_section.get("composition"))
    if "include_isoform" in query_section:
        validate_bool("query", "include_isoform", query_section["include_isoform"])

    normalize_optional_field_list("query", "fields", query_section.get("fields"))
    normalize_optional_field_list("query", "crossref_fields", query_section.get("crossref_fields"))
    return dict(query_section)


def validate_resources_section(resources: dict[str, object]) -> dict[str, object]:
    """Validate and return resource descriptors."""
    validate_allowed_section_keys("resources", resources, RESOURCES_KEYS)
    for key in ("primary", "integration"):
        if key in resources:
            validate_string_list("resources", key, resources[key])
    return dict(resources)


def validate_execution_section(execution: dict[str, object]) -> dict[str, object]:
    """Validate and return executable workflow controls."""
    validate_allowed_section_keys("execution", execution, EXECUTION_KEYS)
    if "enrich" in execution:
        validate_bool("execution", "enrich", execution["enrich"])
    for key in ("download_alphafold_structures", "download_pdb_structures"):
        if key in execution:
            validate_bool("execution", key, execution[key])
    if "merge_results" in execution:
        validate_bool("execution", "merge_results", execution["merge_results"])
    if "max_workers" in execution:
        validate_int("execution", "max_workers", execution["max_workers"])
    if "total_retries" in execution:
        validate_int("execution", "total_retries", execution["total_retries"])
    if "chembl_pages_to_fetch" in execution:
        validate_pages_to_fetch("execution", "chembl_pages_to_fetch", execution["chembl_pages_to_fetch"])
    if "uniprot_timeout" in execution:
        validate_numeric_or_null("execution", "uniprot_timeout", execution["uniprot_timeout"])
    if "debug" in execution:
        validate_bool("execution", "debug", execution["debug"])
    return dict(execution)


def validate_structure_download_controls(
    dataset: dict[str, object], execution: dict[str, object]
) -> None:
    """Reject active structure downloads outside protein metadata enrichment."""
    active_keys = [
        key
        for key in ("download_alphafold_structures", "download_pdb_structures")
        if execution.get(key) is True
    ]
    if not active_keys:
        return

    modality = dataset.get("modality")
    interaction_type = dataset.get("interaction_type")
    if modality != "protein" or interaction_type is not None:
        keys = ", ".join(f"execution.{key}" for key in active_keys)
        msg = (
            f"{keys} may be true only for protein workflows with no interaction_type."
        )
        raise ValueError(msg)

    if execution.get("enrich") is not True:
        keys = ", ".join(f"execution.{key}" for key in active_keys)
        msg = f"{keys} require execution.enrich: true."
        raise ValueError(msg)


def validate_harmonization_section(harmonization: dict[str, object]) -> dict[str, object]:
    """Validate and return harmonization descriptors."""
    validate_allowed_section_keys("harmonization", harmonization, HARMONIZATION_KEYS)
    for key in ("id_column", "label_column", "sequence_column", "unique_sequence_strategy"):
        validate_optional_string("harmonization", key, harmonization.get(key))
    if "metadata_fields" in harmonization:
        validate_string_list("harmonization", "metadata_fields", harmonization["metadata_fields"])
    return dict(harmonization)


def normalize_workflow_export_format(output_format: object) -> str | None:
    """Normalize a workflow-v1 user-facing export format."""
    if output_format is None:
        return None
    normalized = str(output_format).lower().lstrip(".")
    if normalized == "dataframe":
        raise ValueError(DATAFRAME_EXPORT_FORMAT_ERROR)
    if normalized in FORMATS:
        return normalized
    return None


def validate_export_section(export_section: dict[str, object]) -> dict[str, object]:
    """Validate and return export controls."""
    validate_allowed_section_keys("export", export_section, EXPORT_KEYS)
    validate_optional_string("export", "output_dir", export_section.get("output_dir"))
    validate_optional_string("export", "manifest_file", export_section.get("manifest_file"))
    validate_optional_string("export", "summary_file", export_section.get("summary_file"))

    export_format = normalize_workflow_export_format(export_section.get("format", "csv"))
    if export_format is None:
        raw_format = export_section.get("format", "csv")
        msg = f"Unsupported export format '{raw_format}'. Supported formats are: {', '.join(FORMATS)}."
        raise ValueError(msg)

    for key in ("include_metadata", "include_summary"):
        if key in export_section:
            validate_bool("export", key, export_section[key])

    normalized_export = dict(export_section)
    normalized_export["format"] = export_format
    return normalized_export


def collect_workflow_v1_descriptor_errors(recipe: object) -> list[str]:
    """Return every section-level workflow-v1 validation error found."""
    if not isinstance(recipe, dict):
        return ["Workflow YAML root must be a mapping."]

    errors: list[str] = []

    def _check(step: Callable[[], object]) -> None:
        try:
            step()
        except (ValueError, TypeError) as exc:
            errors.append(str(exc))

    _check(lambda: check_forbidden_workflow_recipe_keys(recipe))
    descriptor = {str(key): value for key, value in recipe.items()}
    _check(lambda: validate_descriptor_section_names(descriptor))
    _check(lambda: validate_schema_version(descriptor))

    missing_sections = sorted(REQUIRED_DESCRIPTOR_SECTIONS - set(descriptor))
    if missing_sections:
        errors.append(
            f"Workflow YAML is missing required top-level section(s): {', '.join(missing_sections)}."
        )

    export_section: dict[str, object] = {}

    def _validate_export() -> None:
        nonlocal export_section
        export_section = validate_export_section(require_mapping("export", descriptor["export"]))

    section_steps: list[tuple[str, Callable[[], object]]] = [
        ("export", _validate_export),
        (
            "dataset",
            lambda: validate_dataset_section(
                require_mapping("dataset", descriptor["dataset"]), export_section
            ),
        ),
        ("query", lambda: validate_query_section(require_mapping("query", descriptor["query"]))),
        (
            "execution",
            lambda: validate_execution_section(require_mapping("execution", descriptor["execution"])),
        ),
        (
            "resources",
            lambda: validate_resources_section(require_mapping("resources", descriptor["resources"])),
        ),
        (
            "harmonization",
            lambda: validate_harmonization_section(
                require_mapping("harmonization", descriptor["harmonization"])
            ),
        ),
        (
            "reporting",
            lambda: validate_reporting_section(require_mapping("reporting", descriptor["reporting"])),
        ),
    ]
    valid_sections: set[str] = set()
    for name, step in section_steps:
        if name in descriptor:
            before = len(errors)
            _check(step)
            if len(errors) == before:
                valid_sections.add(name)

    if {"dataset", "query"} <= valid_sections:
        _check(
            lambda: validate_query_composition_matches_query_value(
                require_mapping("query", descriptor["query"]),
                require_mapping("dataset", descriptor["dataset"]).get("mode"),
            )
        )
    if {"dataset", "execution"} <= valid_sections:
        _check(
            lambda: validate_structure_download_controls(
                require_mapping("dataset", descriptor["dataset"]),
                require_mapping("execution", descriptor["execution"]),
            )
        )

    return errors


def validate_workflow_v1_descriptor(recipe: object) -> dict[str, object]:
    """Validate and return a lightweight normalized workflow-v1 descriptor."""
    if not isinstance(recipe, dict):
        msg = "Workflow YAML root must be a mapping."
        raise TypeError(msg)

    check_forbidden_workflow_recipe_keys(recipe)
    workflow_descriptor = {str(key): value for key, value in recipe.items()}
    validate_descriptor_section_names(workflow_descriptor)
    schema_version = validate_schema_version(workflow_descriptor)

    missing_sections = sorted(REQUIRED_DESCRIPTOR_SECTIONS - set(workflow_descriptor))
    if missing_sections:
        missing = ", ".join(missing_sections)
        msg = f"Workflow YAML is missing required top-level section(s): {missing}."
        raise ValueError(msg)

    export_section = validate_export_section(require_mapping("export", workflow_descriptor["export"]))
    dataset = validate_dataset_section(
        require_mapping("dataset", workflow_descriptor["dataset"]),
        export_section,
    )
    query = validate_query_section(require_mapping("query", workflow_descriptor["query"]))
    validate_query_composition_matches_query_value(query, dataset["mode"])
    execution = validate_execution_section(require_mapping("execution", workflow_descriptor["execution"]))
    validate_structure_download_controls(dataset, execution)

    validated: dict[str, object] = {
        "schema_version": schema_version,
        "dataset": dataset,
        "query": query,
    }
    if "resources" in workflow_descriptor:
        validated["resources"] = validate_resources_section(
            require_mapping("resources", workflow_descriptor["resources"])
        )
    validated["execution"] = execution
    if "harmonization" in workflow_descriptor:
        validated["harmonization"] = validate_harmonization_section(
            require_mapping("harmonization", workflow_descriptor["harmonization"])
        )
    validated["export"] = export_section
    if "reporting" in workflow_descriptor:
        reporting = require_mapping("reporting", workflow_descriptor["reporting"])
        validate_reporting_section(reporting)
        validated["reporting"] = reporting
    for section_name in ALLOWED_DESCRIPTOR_SECTION_NAMES:
        if section_name in DESCRIPTIVE_DESCRIPTOR_SECTIONS and section_name in workflow_descriptor:
            validated[section_name] = workflow_descriptor[section_name]
    return validated
