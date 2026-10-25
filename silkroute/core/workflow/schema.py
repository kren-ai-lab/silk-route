"""Lightweight workflow-v1 schema metadata for YAML generators."""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from copy import deepcopy
from typing import TYPE_CHECKING, cast

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
HARMONIZATION_KEYS = {"id_column", "sequence_column"}
EXPORT_KEYS = {
    "output_dir",
    "format",
    "include_metadata",
    "include_summary",
    "manifest_file",
    "summary_file",
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
    "silkroute_biogrid_api_key",
    "silkroute_brenda_email",
    "silkroute_brenda_password",
    "silkroute_refseq_email",
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
    "dataset.primary_data_source": {
        "type": "string",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Optional primary data source label recorded in the descriptor.",
        "gui_visible": False,
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
    "query.description": {
        "type": "string",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Human-readable query description.",
        "gui_visible": False,
    },
    "query.filtering_strategy": {
        "type": "string",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Descriptive note about the query's filtering strategy.",
        "gui_visible": False,
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
    "execution.merge_results": {
        "type": "boolean",
        "required": False,
        "default": None,
        "allowed_values": None,
        "role": "optional_input",
        "description": "Merge per-source results into a single output when supported.",
        "gui_visible": False,
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
        "description": "Name of the record id column in primary result tables (default: id).",
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


class SchemaValueError(ValueError):
    """A descriptor value error that knows the dotted path of the offending key."""

    def __init__(self, message: str, path: str) -> None:
        """Store the message and the dotted path of the offending key."""
        super().__init__(message)
        self.path = path


class SchemaTypeError(TypeError):
    """A descriptor type error that knows the dotted path of the offending key."""

    def __init__(self, message: str, path: str) -> None:
        """Store the message and the dotted path of the offending key."""
        super().__init__(message)
        self.path = path


def _check(errors: list[tuple[str, str]] | None, step: Callable[..., object], *args: object) -> None:
    """Run one validation step; raise its error, or append ``(path, message)`` when collecting."""
    if errors is None:
        step(*args)
        return
    try:
        step(*args)
    except (ValueError, TypeError) as exc:
        errors.append((getattr(exc, "path", ""), str(exc)))


def get_workflow_v1_schema_definition() -> dict[str, object]:
    """Return the workflow-v1 schema definition used by YAML generators."""
    return deepcopy(_WORKFLOW_V1_SCHEMA_DEFINITION)


def check_forbidden_workflow_recipe_keys(
    value: object,
    path: str = "",
    errors: list[tuple[str, str]] | None = None,
) -> None:
    """Reject credential-like keys anywhere in a workflow descriptor."""
    if isinstance(value, dict):
        for key, nested_value in value.items():
            nested_path = f"{path}.{key}" if path else str(key)
            if str(key).lower() in FORBIDDEN_CREDENTIAL_KEYS:
                _check(errors, _raise_value, nested_path, CREDENTIAL_ERROR)
            check_forbidden_workflow_recipe_keys(nested_value, nested_path, errors)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            check_forbidden_workflow_recipe_keys(item, f"{path}[{index}]", errors)


def _raise_value(path: str, message: str) -> None:
    raise SchemaValueError(message, path)


def require_mapping(section_name: str, value: object) -> dict[str, object]:
    """Return a section as a string-keyed mapping."""
    if not isinstance(value, dict):
        msg = f"Workflow YAML section '{section_name}' must be a mapping."
        raise SchemaTypeError(msg, section_name)
    return {str(key): item for key, item in value.items()}


def validate_allowed_section_keys(
    section_name: str,
    section: dict[str, object],
    allowed_keys: set[str],
    special_errors: dict[str, str] | None = None,
    errors: list[tuple[str, str]] | None = None,
) -> None:
    """Validate known keys for a descriptor section."""
    for key in section:
        path = f"{section_name}.{key}"
        if special_errors and key in special_errors:
            _check(errors, _raise_value, path, special_errors[key])
        elif key not in allowed_keys:
            _check(errors, _raise_value, path, f"Unknown {section_name} YAML key '{key}'.")


def get_rejected_mode_key_message(key: str) -> str | None:
    """Return the validation message for removed workflow mode keys."""
    for message in OLD_MODE_KEY_ERROR_MESSAGES:
        if key == message.split("'")[1]:
            return message
    return None


def validate_descriptor_section_names(
    workflow_descriptor: dict[str, object],
    errors: list[tuple[str, str]] | None = None,
) -> None:
    """Validate top-level workflow descriptor section names."""
    allowed_sections = ", ".join(ALLOWED_DESCRIPTOR_SECTION_NAMES)
    for key in workflow_descriptor:
        message = get_rejected_mode_key_message(key) or OLD_ROOT_KEY_ERRORS.get(key)
        if message is None and key not in KNOWN_DESCRIPTOR_SECTIONS:
            message = f"Unknown workflow YAML section '{key}'. Allowed sections are: {allowed_sections}."
        if message is not None:
            _check(errors, _raise_value, key, message)


def validate_schema_version(workflow_descriptor: dict[str, object]) -> str:
    """Validate the required workflow schema version."""
    if "schema_version" not in workflow_descriptor:
        msg = (
            "Workflow YAML is missing required top-level key 'schema_version'. "
            f'Use schema_version: "{WORKFLOW_SCHEMA_VERSION}".'
        )
        raise SchemaValueError(msg, "schema_version")

    schema_version = workflow_descriptor["schema_version"]
    if schema_version != WORKFLOW_SCHEMA_VERSION:
        msg = (
            f"Unsupported workflow schema_version '{schema_version}'. "
            f'Only schema_version: "{WORKFLOW_SCHEMA_VERSION}" is supported.'
        )
        raise SchemaValueError(msg, "schema_version")
    return cast("str", schema_version)


def validate_required_section_keys(
    section_name: str,
    section: dict[str, object],
    required_keys: set[str],
    errors: list[tuple[str, str]] | None = None,
) -> None:
    """Validate that a descriptor section contains required keys."""
    missing = sorted(key for key in required_keys if key not in section or section[key] is None)
    if missing:
        missing_text = ", ".join(missing)
        msg = f"Workflow YAML section '{section_name}' is missing required key(s): {missing_text}."
        _check(errors, _raise_value, section_name, msg)


def validate_optional_string(section_name: str, key: str, value: object) -> None:
    """Validate an optional string field."""
    if value is not None and not isinstance(value, str):
        msg = f"Workflow YAML key '{section_name}.{key}' must be a string or null."
        raise SchemaValueError(msg, f"{section_name}.{key}")


def validate_bool(section_name: str, key: str, value: object) -> None:
    """Validate a boolean field."""
    if not isinstance(value, bool):
        msg = f"Workflow YAML key '{section_name}.{key}' must be a boolean."
        raise SchemaTypeError(msg, f"{section_name}.{key}")


def validate_int(section_name: str, key: str, value: object) -> None:
    """Validate an integer field without accepting booleans."""
    if isinstance(value, bool) or not isinstance(value, int):
        msg = f"Workflow YAML key '{section_name}.{key}' must be an integer."
        raise SchemaTypeError(msg, f"{section_name}.{key}")


def validate_numeric_or_null(section_name: str, key: str, value: object) -> None:
    """Validate a numeric or null field without accepting booleans."""
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
        msg = f"Workflow YAML key '{section_name}.{key}' must be numeric or null."
        raise SchemaValueError(msg, f"{section_name}.{key}")


def validate_pages_to_fetch(section_name: str, key: str, value: object) -> None:
    """Validate a ChEMBL page count where -1 means all pages."""
    validate_int(section_name, key, value)
    if value == 0 or (isinstance(value, int) and value < -1):
        msg = f"Workflow YAML key '{section_name}.{key}' must be -1 or a positive integer."
        raise SchemaValueError(msg, f"{section_name}.{key}")


def validate_string_list(section_name: str, key: str, value: object) -> None:
    """Validate a list containing only strings."""
    path = f"{section_name}.{key}"
    if not isinstance(value, list):
        msg = f"Workflow YAML key '{path}' must be a list of strings."
        raise SchemaValueError(msg, path)
    for index, item in enumerate(value):
        if not isinstance(item, str):
            msg = f"Workflow YAML key '{path}[{index}]' must be a string."
            raise SchemaValueError(msg, f"{path}[{index}]")


def validate_query_builder(value: object) -> None:
    """Validate optional GUI query-builder metadata."""
    if value is not None and not isinstance(value, dict):
        msg = "Workflow YAML key 'query.builder' must be a mapping."
        raise SchemaTypeError(msg, "query.builder")


def validate_query_composition(value: object) -> None:
    """Validate optional GUI query-composition metadata."""
    if value is None:
        return
    if not isinstance(value, list):
        msg = "Workflow YAML key 'query.composition' must be a list of mappings."
        raise SchemaTypeError(msg, "query.composition")
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            msg = f"Workflow YAML key 'query.composition[{index}]' must be a mapping."
            raise SchemaTypeError(msg, f"query.composition[{index}]")
        for required_key in ("label", "value"):
            required_value = item.get(required_key)
            if not isinstance(required_value, str) or not required_value.strip():
                msg = (
                    f"Workflow YAML key 'query.composition[{index}].{required_key}' "
                    "must be a non-empty string."
                )
                raise SchemaValueError(msg, f"query.composition[{index}].{required_key}")
        description = item.get("description")
        if "description" in item and description is not None and not isinstance(description, str):
            msg = f"Workflow YAML key 'query.composition[{index}].description' must be a string or null."
            raise SchemaValueError(msg, f"query.composition[{index}].description")
        builder = item.get("builder")
        if "builder" in item and not isinstance(builder, dict):
            msg = f"Workflow YAML key 'query.composition[{index}].builder' must be a mapping."
            raise SchemaTypeError(msg, f"query.composition[{index}].builder")


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
        raise SchemaValueError(msg, "query.composition")
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
    composition_pair_set = {
        (item["value"].strip(), item["label"].strip()) for item in cast("list[dict[str, str]]", composition)
    }
    if composition_pair_set != executable_pair_set:
        msg = "query.composition does not match executable query.value."
        raise SchemaValueError(msg, "query.composition")


def normalize_optional_field_list(section_name: str, key: str, value: object) -> str | None:
    """Normalize null, comma-separated string, or string-list fields for workflow calls."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    path = f"{section_name}.{key}"
    if isinstance(value, list):
        for index, item in enumerate(value):
            if not isinstance(item, str):
                msg = f"Workflow YAML key '{path}[{index}]' must be a string."
                raise SchemaValueError(msg, f"{path}[{index}]")
        cleaned = [item.strip() for item in value if item.strip()]
        return ",".join(cleaned) if cleaned else None
    msg = f"Workflow YAML key '{path}' must be null, a string, or a list of strings."
    raise SchemaValueError(msg, path)


def is_reporting_value_allowed(value: object) -> bool:
    """Return whether a reporting value is YAML-descriptor safe."""
    if value is None or isinstance(value, (str, int, float, bool, dt.date, dt.datetime)):
        return True
    if isinstance(value, list):
        return all(is_reporting_value_allowed(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and is_reporting_value_allowed(item) for key, item in value.items())
    return False


def validate_reporting_section(
    reporting: dict[str, object], errors: list[tuple[str, str]] | None = None
) -> None:
    """Validate free-form reporting metrics."""
    for key, value in reporting.items():
        if not is_reporting_value_allowed(value):
            msg = f"Workflow YAML key 'reporting.{key}' has an unsupported value type."
            _check(errors, _raise_value, f"reporting.{key}", msg)


def _validate_modality(dataset: dict[str, object]) -> None:
    modality = dataset.get("modality")
    if modality not in MODALITIES:
        supported_modalities = ", ".join(MODALITIES)
        msg = f"Unsupported dataset.modality '{modality}'. Supported modalities are: {supported_modalities}."
        raise SchemaValueError(msg, "dataset.modality")


def _validate_mode(dataset: dict[str, object]) -> None:
    mode = dataset.get("mode")
    if mode not in MODES:
        msg = f"Unsupported dataset.mode '{mode}'. Supported modes are: {', '.join(MODES)}."
        raise SchemaValueError(msg, "dataset.mode")


def _validate_interaction_type(dataset: dict[str, object]) -> None:
    interaction_type = dataset.get("interaction_type")
    if dataset.get("modality") == "interaction" and not interaction_type:
        msg = "dataset.interaction_type is required when dataset.modality is 'interaction'."
        raise SchemaValueError(msg, "dataset.interaction_type")
    if interaction_type is not None and interaction_type not in INTERACTION_TYPES:
        msg = (
            f"Unsupported dataset.interaction_type '{interaction_type}'. "
            f"Supported interaction types are: {', '.join(INTERACTION_TYPES)}."
        )
        raise SchemaValueError(msg, "dataset.interaction_type")


def _validate_dataset_name(dataset: dict[str, object], export_section: dict[str, object]) -> None:
    if not export_section.get("output_dir") and not dataset.get("name"):
        msg = "dataset.name is required when export.output_dir is not provided."
        raise SchemaValueError(msg, "dataset.name")


def validate_dataset_section(
    dataset: dict[str, object],
    export_section: dict[str, object],
    errors: list[tuple[str, str]] | None = None,
) -> dict[str, object]:
    """Validate and return the dataset descriptor section."""
    validate_allowed_section_keys("dataset", dataset, DATASET_KEYS, errors=errors)
    validate_required_section_keys("dataset", dataset, {"modality", "mode"}, errors=errors)
    if dataset.get("modality") is not None:
        _check(errors, _validate_modality, dataset)
    if dataset.get("mode") is not None:
        _check(errors, _validate_mode, dataset)
    for key in ("name", "description", "primary_data_source", "interaction_type"):
        _check(errors, validate_optional_string, "dataset", key, dataset.get(key))
    _check(errors, _validate_interaction_type, dataset)
    _check(errors, _validate_dataset_name, dataset, export_section)
    return dict(dataset)


def _validate_query_value(query_section: dict[str, object]) -> None:
    query_value = query_section.get("value")
    if not isinstance(query_value, str) or not query_value.strip():
        msg = "Workflow YAML key 'query.value' must be a non-empty string."
        raise SchemaValueError(msg, "query.value")


def validate_query_section(
    query_section: dict[str, object], errors: list[tuple[str, str]] | None = None
) -> dict[str, object]:
    """Validate and return the query descriptor section."""
    validate_allowed_section_keys(
        "query", query_section, QUERY_KEYS, special_errors=QUERY_KEY_ERRORS, errors=errors
    )
    validate_required_section_keys("query", query_section, {"value"}, errors=errors)
    if query_section.get("value") is not None:
        _check(errors, _validate_query_value, query_section)
    for key in ("description", "filtering_strategy"):
        _check(errors, validate_optional_string, "query", key, query_section.get(key))
    _check(errors, validate_query_builder, query_section.get("builder"))
    _check(errors, validate_query_composition, query_section.get("composition"))
    if "include_isoform" in query_section:
        _check(errors, validate_bool, "query", "include_isoform", query_section["include_isoform"])
    for key in ("fields", "crossref_fields"):
        _check(errors, normalize_optional_field_list, "query", key, query_section.get(key))
    return dict(query_section)


def validate_resources_section(
    resources: dict[str, object], errors: list[tuple[str, str]] | None = None
) -> dict[str, object]:
    """Validate and return resource descriptors."""
    validate_allowed_section_keys("resources", resources, RESOURCES_KEYS, errors=errors)
    for key in ("primary", "integration"):
        if key in resources:
            _check(errors, validate_string_list, "resources", key, resources[key])
    return dict(resources)


def validate_execution_section(
    execution: dict[str, object], errors: list[tuple[str, str]] | None = None
) -> dict[str, object]:
    """Validate and return executable workflow controls."""
    validate_allowed_section_keys("execution", execution, EXECUTION_KEYS, errors=errors)
    checks: list[tuple[Callable[..., object], tuple[str, ...]]] = [
        (
            validate_bool,
            ("enrich", "download_alphafold_structures", "download_pdb_structures", "merge_results"),
        ),
        (validate_int, ("max_workers", "total_retries")),
        (validate_pages_to_fetch, ("chembl_pages_to_fetch",)),
        (validate_numeric_or_null, ("uniprot_timeout",)),
        (validate_bool, ("debug",)),
    ]
    for validator, keys in checks:
        for key in keys:
            if key in execution:
                _check(errors, validator, "execution", key, execution[key])
    return dict(execution)


def validate_structure_download_controls(dataset: dict[str, object], execution: dict[str, object]) -> None:
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
        msg = f"{keys} may be true only for protein workflows with no interaction_type."
        raise ValueError(msg)

    if execution.get("enrich") is not True:
        keys = ", ".join(f"execution.{key}" for key in active_keys)
        msg = f"{keys} require execution.enrich: true."
        raise ValueError(msg)


def _validate_id_column(harmonization: dict[str, object]) -> None:
    value = harmonization.get("id_column")
    if value is not None and (not isinstance(value, str) or not value.strip()):
        msg = "Workflow YAML key 'harmonization.id_column' must be a non-empty string or null."
        raise SchemaValueError(msg, "harmonization.id_column")


def validate_harmonization_section(
    harmonization: dict[str, object], errors: list[tuple[str, str]] | None = None
) -> dict[str, object]:
    """Validate and return harmonization descriptors."""
    validate_allowed_section_keys("harmonization", harmonization, HARMONIZATION_KEYS, errors=errors)
    _check(errors, _validate_id_column, harmonization)
    _check(
        errors,
        validate_optional_string,
        "harmonization",
        "sequence_column",
        harmonization.get("sequence_column"),
    )
    return dict(harmonization)


def normalize_workflow_export_format(output_format: object) -> str | None:
    """Normalize a workflow-v1 user-facing export format."""
    if output_format is None:
        return None
    normalized = str(output_format).lower().lstrip(".")
    if normalized == "dataframe":
        raise SchemaValueError(DATAFRAME_EXPORT_FORMAT_ERROR, "export.format")
    if normalized in FORMATS:
        return normalized
    return None


def _validate_export_format(export_section: dict[str, object]) -> str:
    export_format = normalize_workflow_export_format(export_section.get("format", "csv"))
    if export_format is None:
        raw_format = export_section.get("format", "csv")
        msg = f"Unsupported export format '{raw_format}'. Supported formats are: {', '.join(FORMATS)}."
        raise SchemaValueError(msg, "export.format")
    return export_format


def _normalize_export_format(export_section: dict[str, object]) -> None:
    export_section["format"] = _validate_export_format(export_section)


def validate_export_section(
    export_section: dict[str, object], errors: list[tuple[str, str]] | None = None
) -> dict[str, object]:
    """Validate and return export controls."""
    validate_allowed_section_keys("export", export_section, EXPORT_KEYS, errors=errors)
    for key in ("output_dir", "manifest_file", "summary_file"):
        _check(errors, validate_optional_string, "export", key, export_section.get(key))
    normalized_export = dict(export_section)
    _check(errors, _normalize_export_format, normalized_export)
    for key in ("include_metadata", "include_summary"):
        if key in export_section:
            _check(errors, validate_bool, "export", key, export_section[key])
    return normalized_export


def _collect_sections(
    descriptor: dict[str, object], errors: list[tuple[str, str]]
) -> dict[str, dict[str, object]]:
    """Validate every present section, appending all problems to ``errors``.

    Returns the sections that were found valid, for the cross-section checks.
    """
    valid: dict[str, dict[str, object]] = {}
    export_section: dict[str, object] = {}
    validators: dict[str, Callable[[dict[str, object], list[tuple[str, str]]], object]] = {
        "export": validate_export_section,
        "dataset": lambda section, errs: validate_dataset_section(section, export_section, errs),
        "query": validate_query_section,
        "execution": validate_execution_section,
        "resources": validate_resources_section,
        "harmonization": validate_harmonization_section,
        "reporting": validate_reporting_section,
    }
    for name, validator in validators.items():
        if name not in descriptor:
            continue
        before = len(errors)
        try:
            section = require_mapping(name, descriptor[name])
        except TypeError as exc:
            errors.append((name, str(exc)))
            continue
        validator(section, errors)
        if len(errors) == before:
            valid[name] = section
            if name == "export":
                export_section = validate_export_section(section)
    return valid


def collect_workflow_v1_descriptor_errors(recipe: object) -> list[tuple[str, str]]:
    """Return every ``(dotted path, message)`` workflow-v1 validation error found."""
    if not isinstance(recipe, Mapping):
        return [("", "Workflow YAML root must be a mapping.")]

    errors: list[tuple[str, str]] = []
    descriptor = {str(key): value for key, value in recipe.items()}
    check_forbidden_workflow_recipe_keys(descriptor, errors=errors)
    validate_descriptor_section_names(descriptor, errors)
    _check(errors, validate_schema_version, descriptor)
    for name in sorted(REQUIRED_DESCRIPTOR_SECTIONS - set(descriptor)):
        msg = f"Workflow YAML is missing required top-level section(s): {name}."
        errors.append((name, msg))

    valid = _collect_sections(descriptor, errors)
    if {"dataset", "query"} <= valid.keys():
        mode = valid["dataset"].get("mode")
        _check(errors, validate_query_composition_matches_query_value, valid["query"], mode)
    if {"dataset", "execution"} <= valid.keys():
        _check(errors, validate_structure_download_controls, valid["dataset"], valid["execution"])
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
