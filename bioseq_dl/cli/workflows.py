"""CLI commands for running multi-step download workflows."""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import logging
import math
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any

import polars as pl
import typer
import yaml

from bioseq_dl import __version__
from bioseq_dl.core.export import (
    export_dataframe,
    normalize_export_format,
    normalize_user_export_format,
)
from bioseq_dl.core.interfaces.uniprot import UniprotInterface
from bioseq_dl.core.workflow import schema as workflow_schema
from bioseq_dl.core.workflow.main_workflow import MainWorkflow
from bioseq_dl.logging import configure_logging, get_logger

log = get_logger("bioseq_dl.cli.workflows")


WORKFLOW_SCHEMA_VERSION = workflow_schema.WORKFLOW_SCHEMA_VERSION
MODALITIES = workflow_schema.MODALITIES
MODES = workflow_schema.MODES
INTERACTION_TYPES = workflow_schema.INTERACTION_TYPES
FORMATS = workflow_schema.FORMATS
REQUIRED_DESCRIPTOR_SECTIONS = workflow_schema.REQUIRED_DESCRIPTOR_SECTIONS
ALLOWED_DESCRIPTOR_SECTION_NAMES = workflow_schema.ALLOWED_DESCRIPTOR_SECTION_NAMES
KNOWN_DESCRIPTOR_SECTIONS = workflow_schema.KNOWN_DESCRIPTOR_SECTIONS
QUERY_COMPOSITION_LABEL_COLUMN = "_label"
PRIMARY_RESULT_LABELS = {
    "protein": "uniprot",
    "compound": "chembl",
    "interaction": "data",
}
GRAPH_JSON_COLUMN = "graph_json"
GRAPH_FILE_COLUMNS = ("graph_file", "graph_file_size_bytes", "graph_sha256")
GRAPH_RAW_OUTPUT_KIND = "raw_graph"
GRAPH_ENRICHMENT_OUTPUTS = {
    ("pathwaycommons", "fetch"),
    ("pathwaycommons", "neighborhood"),
}
WINDOWS_RESERVED_FILENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}

check_forbidden_workflow_recipe_keys = workflow_schema.check_forbidden_workflow_recipe_keys
require_mapping = workflow_schema.require_mapping
validate_allowed_section_keys = workflow_schema.validate_allowed_section_keys
validate_descriptor_section_names = workflow_schema.validate_descriptor_section_names
validate_schema_version = workflow_schema.validate_schema_version
validate_required_section_keys = workflow_schema.validate_required_section_keys
validate_optional_string = workflow_schema.validate_optional_string
validate_bool = workflow_schema.validate_bool
validate_int = workflow_schema.validate_int
validate_numeric_or_null = workflow_schema.validate_numeric_or_null
validate_pages_to_fetch = workflow_schema.validate_pages_to_fetch
validate_string_list = workflow_schema.validate_string_list
validate_query_builder = workflow_schema.validate_query_builder
validate_query_composition = workflow_schema.validate_query_composition
parse_query_composition_value = workflow_schema.parse_query_composition_value
validate_query_composition_matches_query_value = (
    workflow_schema.validate_query_composition_matches_query_value
)
normalize_optional_field_list = workflow_schema.normalize_optional_field_list
is_reporting_value_allowed = workflow_schema.is_reporting_value_allowed
validate_reporting_section = workflow_schema.validate_reporting_section
validate_resources_section = workflow_schema.validate_resources_section
validate_execution_section = workflow_schema.validate_execution_section
validate_structure_download_controls = workflow_schema.validate_structure_download_controls
validate_harmonization_section = workflow_schema.validate_harmonization_section
validate_export_section = workflow_schema.validate_export_section


def validate_interaction_type(
    modality: object,
    interaction_type: object,
    field_label: str,
    modality_label: str,
) -> None:
    """Validate CLI/runtime interaction-type values."""
    if modality == "interaction" and not interaction_type:
        msg = f"{field_label} is required when {modality_label} is 'interaction'."
        raise ValueError(msg)
    if interaction_type is not None and interaction_type not in INTERACTION_TYPES:
        msg = (
            f"Unsupported {field_label} '{interaction_type}'. "
            f"Supported interaction types are: {', '.join(INTERACTION_TYPES)}."
        )
        raise ValueError(msg)


def validate_dataset_section(dataset: dict, export_section: dict) -> dict:
    """Validate and return the dataset descriptor section."""
    return workflow_schema.validate_dataset_section(dataset, export_section)


def validate_query_section(query_section: dict) -> tuple[dict, str | None, str | None]:
    """Validate query metadata and return CLI-normalized field options."""
    validated = workflow_schema.validate_query_section(query_section)
    fields = workflow_schema.normalize_optional_field_list("query", "fields", validated.get("fields"))
    crossref_fields = workflow_schema.normalize_optional_field_list(
        "query", "crossref_fields", validated.get("crossref_fields")
    )
    return validated, fields, crossref_fields


def build_default_workflow_values() -> dict:
    """Return fresh workflow defaults for CLI-only and descriptor-backed runs.

    Returns:
        dict: A new mapping of default descriptor sections and executable values.

    """
    return {
        "dataset": {},
        "query_descriptor": {},
        "resources": {},
        "execution": {},
        "harmonization": {},
        "export": {},
        "reporting": {},
        "extra_descriptor_sections": {},
        "original_descriptor": {},
        "schema_version": None,
        "output": None,
        "query": None,
        "modality": None,
        "mode": None,
        "export_format": "csv",
        "enrich": True,
        "download_alphafold_structures": False,
        "download_pdb_structures": False,
        "workers": 5,
        "retries": 3,
        "chembl_pages_to_fetch": -1,
        "merge_results": False,
        "fields": None,
        "crossref_fields": None,
        "interaction_type": None,
        "include_isoform": False,
        "uniprot_timeout": None,
        "debug": False,
        "id_column": None,
        "include_metadata": True,
        "include_summary": True,
        "manifest_file": "metadata.json",
        "summary_file": "run_summary.yml",
    }


def collect_descriptor_sections(values: dict) -> dict:
    """Collect current descriptor sections from normalized workflow values.

    Includes optional ``resources``, ``harmonization``, and ``reporting`` sections only
    when present, then merges any extra descriptive sections.

    Args:
        values (dict): Normalized workflow values.

    Returns:
        dict: The descriptor-shaped section mapping.

    """
    descriptor = {}
    if values.get("schema_version"):
        descriptor["schema_version"] = values["schema_version"]
    descriptor.update(
        {
            "dataset": values.get("dataset", {}),
            "query": values.get("query_descriptor", {}),
        }
    )
    if values.get("resources"):
        descriptor["resources"] = values["resources"]
    descriptor["execution"] = values.get("execution", {})
    if values.get("harmonization"):
        descriptor["harmonization"] = values["harmonization"]
    descriptor["export"] = values.get("export", {})
    if values.get("reporting"):
        descriptor["reporting"] = values["reporting"]
    descriptor.update(values.get("extra_descriptor_sections", {}))
    return descriptor


def sync_descriptor_from_workflow_values(values: dict) -> dict:
    """Apply effective executable values back into descriptor-shaped metadata.

    Copies executable values (modality, query, execution controls, export options, etc.)
    into their corresponding descriptor sections so metadata reflects the effective run.

    Args:
        values (dict): Workflow values to synchronize.

    Returns:
        dict: A copy of the values with descriptor sections updated.

    """
    synced = dict(values)

    dataset = dict(synced.get("dataset") or {})
    if synced.get("modality") is not None:
        dataset["modality"] = synced["modality"]
    if synced.get("mode") is not None:
        dataset["mode"] = synced["mode"]
    if synced.get("interaction_type") is not None:
        dataset["interaction_type"] = synced["interaction_type"]
    synced["dataset"] = dataset

    query_descriptor = dict(synced.get("query_descriptor") or {})
    if synced.get("query") is not None:
        query_descriptor["value"] = synced["query"]
    if synced.get("fields") is not None:
        query_descriptor["fields"] = synced["fields"]
    if synced.get("crossref_fields") is not None:
        query_descriptor["crossref_fields"] = synced["crossref_fields"]
    if synced.get("include_isoform") is not None:
        query_descriptor["include_isoform"] = synced["include_isoform"]
    synced["query_descriptor"] = query_descriptor

    execution = dict(synced.get("execution") or {})
    execution["enrich"] = synced.get("enrich")
    execution["download_alphafold_structures"] = synced.get("download_alphafold_structures", False)
    execution["download_pdb_structures"] = synced.get("download_pdb_structures", False)
    execution["max_workers"] = synced.get("workers")
    execution["total_retries"] = synced.get("retries")
    execution["chembl_pages_to_fetch"] = synced.get("chembl_pages_to_fetch")
    execution["merge_results"] = synced.get("merge_results")
    if synced.get("uniprot_timeout") is not None:
        execution["uniprot_timeout"] = synced["uniprot_timeout"]
    execution["debug"] = synced.get("debug")
    synced["execution"] = execution

    harmonization = dict(synced.get("harmonization") or {})
    if synced.get("id_column") is not None:
        harmonization["id_column"] = synced["id_column"]
    synced["harmonization"] = harmonization

    export_section = dict(synced.get("export") or {})
    if synced.get("output") is not None:
        export_section["output_dir"] = synced["output"]
    export_section["format"] = synced.get("export_format")
    export_section["include_metadata"] = synced.get("include_metadata")
    export_section["include_summary"] = synced.get("include_summary")
    export_section["manifest_file"] = synced.get("manifest_file")
    export_section["summary_file"] = synced.get("summary_file")
    synced["export"] = export_section
    return synced


def load_workflow_recipe(config_path: str | Path) -> dict:
    """Load a workflow descriptor from a YAML file.

    Args:
        config_path (str | Path): Path to the YAML descriptor file.

    Returns:
        dict: The parsed descriptor, or an empty dict if the file is empty.

    Raises:
        ValueError: If the file does not exist or cannot be read or parsed.
        TypeError: If the YAML root is not a mapping.

    """
    path = Path(config_path)
    if not path.exists():
        msg = f"Workflow YAML file does not exist: {path}"
        raise ValueError(msg)

    try:
        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        msg = f"Invalid workflow YAML in {path}: {exc}"
        raise ValueError(msg) from exc
    except OSError as exc:
        msg = f"Could not read workflow YAML {path}: {exc}"
        raise ValueError(msg) from exc

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        msg = "Workflow YAML root must be a mapping."
        raise TypeError(msg)
    return loaded


def validate_workflow_recipe(recipe: dict) -> dict:
    """Validate and normalize a structured workflow descriptor.

    Delegates workflow-v1 descriptor validation to
    :func:`bioseq_dl.core.workflow.schema.validate_workflow_v1_descriptor`, then derives
    executable CLI/runtime values (output directory, query, modality, execution
    controls, etc.) and syncs them back into descriptor metadata.

    Args:
        recipe (dict): The raw descriptor mapping to validate.

    Returns:
        dict: Normalized workflow values ready for execution.

    Raises:
        ValueError: If sections, keys, or values fail validation.
        TypeError: If the root or a section is not a mapping.

    """
    validated_descriptor = workflow_schema.validate_workflow_v1_descriptor(recipe)
    workflow_descriptor = {str(key): value for key, value in recipe.items()}
    schema_version = str(validated_descriptor["schema_version"])
    dataset = dict(validated_descriptor["dataset"])
    query_descriptor = dict(validated_descriptor["query"])
    fields = workflow_schema.normalize_optional_field_list("query", "fields", query_descriptor.get("fields"))
    crossref_fields = workflow_schema.normalize_optional_field_list(
        "query", "crossref_fields", query_descriptor.get("crossref_fields")
    )
    execution = dict(validated_descriptor["execution"])
    resources = dict(validated_descriptor.get("resources", {}))
    harmonization = dict(validated_descriptor.get("harmonization", {}))
    export_section = dict(validated_descriptor["export"])
    reporting = dict(validated_descriptor.get("reporting", {}))
    extra_descriptor_sections = {
        key: value
        for key, value in validated_descriptor.items()
        if key in workflow_schema.DESCRIPTIVE_DESCRIPTOR_SECTIONS
    }

    output_dir = export_section.get("output_dir")
    if not output_dir and dataset.get("name"):
        output_dir = f"results/{dataset['name']}"

    normalized = build_default_workflow_values()
    manifest_file = export_section.get("manifest_file") or "metadata.json"
    summary_file = export_section.get("summary_file") or "run_summary.yml"

    normalized.update(
        {
            "dataset": dataset,
            "query_descriptor": query_descriptor,
            "resources": resources,
            "execution": execution,
            "harmonization": harmonization,
            "export": export_section,
            "reporting": reporting,
            "extra_descriptor_sections": extra_descriptor_sections,
            "original_descriptor": workflow_descriptor,
            "schema_version": schema_version,
            "output": output_dir,
            "query": query_descriptor["value"],
            "modality": dataset["modality"],
            "mode": dataset["mode"],
            "export_format": export_section.get("format", "csv"),
            "enrich": execution.get("enrich", True),
            "download_alphafold_structures": execution.get("download_alphafold_structures", False),
            "download_pdb_structures": execution.get("download_pdb_structures", False),
            "workers": execution.get("max_workers", 5),
            "retries": execution.get("total_retries", 3),
            "chembl_pages_to_fetch": execution.get("chembl_pages_to_fetch", -1),
            "merge_results": execution.get("merge_results", False),
            "fields": fields,
            "crossref_fields": crossref_fields,
            "interaction_type": dataset.get("interaction_type"),
            "include_isoform": query_descriptor.get("include_isoform", False),
            "uniprot_timeout": execution.get("uniprot_timeout"),
            "debug": execution.get("debug", False),
            "id_column": harmonization.get("id_column"),
            "include_metadata": export_section.get("include_metadata", True),
            "include_summary": export_section.get("include_summary", True),
            "manifest_file": manifest_file,
            "summary_file": summary_file,
        }
    )
    return sync_descriptor_from_workflow_values(normalized)


def collect_workflow_recipe_errors(recipe: object) -> list[str]:
    """Return every section-level validation error found in a descriptor.

    Delegates to the shared workflow-v1 schema collector so CLI validation reports use
    the same rules as runtime descriptor validation.

    Args:
        recipe (object): The raw descriptor mapping to validate.

    Returns:
        list[str]: Human-readable error messages; empty when the descriptor is valid.

    """
    return workflow_schema.collect_workflow_v1_descriptor_errors(recipe)


def merge_workflow_recipe(cli_values: dict, recipe_values: dict) -> dict:
    """Merge explicit CLI values with YAML descriptor values.

    Descriptor values override defaults, and explicit (non-``None``) CLI values
    override both, then the descriptor metadata is re-synced.

    Args:
        cli_values (dict): Values provided through CLI options.
        recipe_values (dict): Normalized values from a YAML descriptor.

    Returns:
        dict: The merged and synchronized workflow values.

    """
    merged = build_default_workflow_values()
    merged.update(recipe_values)
    explicit_cli_values = {key: value for key, value in cli_values.items() if value is not None}
    merged.update(explicit_cli_values)
    return sync_descriptor_from_workflow_values(merged)


def collect_cli_workflow_values(
    output: str | None,
    modality: str | None,
    mode: str | None,
    query: str | None,
    fields: str | None,
    crossref_fields: str | None,
    export_format: str | None,
    enrich: bool | None,
    max_workers: int | None,
    total_retries: int | None,
    uniprot_timeout: float | None,
    debug: bool | None,
    include_isoform: bool | None,
    interaction_type: str | None,
    chembl_pages_to_fetch: int | None = None,
) -> dict:
    """Return workflow values explicitly provided through CLI options.

    Args:
        output (str | None): Output directory for results.
        modality (str | None): Biological modality to run.
        mode (str | None): Workflow execution mode.
        query (str | None): Executable query string.
        fields (str | None): Comma-separated UniProt fields to fetch.
        crossref_fields (str | None): Comma-separated cross-reference fields.
        export_format (str | None): Result export format.
        enrich (bool | None): Whether to perform data enrichment.
        max_workers (int | None): Maximum worker threads for API calls.
        total_retries (int | None): Total retries for failed API calls.
        uniprot_timeout (float | None): Timeout in seconds for UniProt requests.
        debug (bool | None): Whether to enable debug logging.
        include_isoform (bool | None): Whether to include UniProt isoforms.
        interaction_type (str | None): Interaction workflow type.
        chembl_pages_to_fetch (int | None): ChEMBL pages to fetch (-1 for all).

    Returns:
        dict: Workflow values keyed by their executable names.

    """
    return {
        "output": output,
        "modality": modality,
        "mode": mode,
        "query": query,
        "fields": fields,
        "crossref_fields": crossref_fields,
        "export_format": export_format,
        "enrich": enrich,
        "workers": max_workers,
        "retries": total_retries,
        "chembl_pages_to_fetch": chembl_pages_to_fetch,
        "uniprot_timeout": uniprot_timeout,
        "debug": debug,
        "include_isoform": include_isoform,
        "interaction_type": interaction_type,
    }


def validate_merged_workflow_values(values: dict) -> None:
    """Validate merged workflow CLI and descriptor values.

    Checks required values, supported modality and mode, the ChEMBL page count, and
    normalizes the export format in place.

    Args:
        values (dict): Merged workflow values; ``export_format`` is updated in place.

    Raises:
        ValueError: If required values are missing or a value is unsupported.
        TypeError: If ``chembl_pages_to_fetch`` is not an integer.

    """
    missing_keys = [key for key in ("output", "query", "modality", "mode") if not values.get(key)]
    if missing_keys:
        missing = ", ".join(missing_keys)
        msg = f"Missing required workflow value(s): {missing}. Provide them with CLI options or --config."
        raise ValueError(msg)

    if values["modality"] not in MODALITIES:
        supported_modalities = ", ".join(MODALITIES)
        msg = (
            f"Unsupported modality '{values['modality']}'. Supported modalities are: {supported_modalities}."
        )
        raise ValueError(msg)

    if values["mode"] not in MODES:
        msg = f"Unsupported workflow mode '{values['mode']}'. Supported modes are: {', '.join(MODES)}."
        raise ValueError(msg)

    validate_interaction_type(
        values["modality"], values.get("interaction_type"), "interaction_type", "modality"
    )

    chembl_pages_to_fetch = values.get("chembl_pages_to_fetch", -1)
    if not isinstance(chembl_pages_to_fetch, int) or isinstance(chembl_pages_to_fetch, bool):
        msg = "chembl_pages_to_fetch must be -1 or a positive integer."
        raise TypeError(msg)
    if chembl_pages_to_fetch == 0 or chembl_pages_to_fetch < -1:
        msg = "chembl_pages_to_fetch must be -1 or a positive integer."
        raise ValueError(msg)

    export_format = normalize_user_export_format(values["export_format"])
    if export_format is None:
        msg = (
            f"Unsupported export format '{values['export_format']}'. Supported formats are: "
            f"{', '.join(FORMATS)}."
        )
        raise ValueError(msg)
    values["export_format"] = export_format


def is_valid_export_label(label: object) -> bool:
    """Return whether a result label should be exported as a file.

    Args:
        label (object): The candidate result label.

    Returns:
        bool: True unless the label is empty, ``None``, or the strings "none"/"null".

    """
    if label is None:
        return False
    normalized = str(label).strip()
    if not normalized:
        return False
    return normalized.lower() not in {"none", "null"}


def is_empty_export_content(content: object) -> bool:
    """Return whether export content is empty.

    Handles ``None``, empty DataFrames, blank strings, and empty containers.

    Args:
        content (object): The content to check.

    Returns:
        bool: True if the content holds nothing to export.

    """
    if content is None:
        return True
    if isinstance(content, pl.DataFrame):
        return content.is_empty()
    if isinstance(content, str):
        return content.strip() == ""
    if isinstance(content, (bytes, dict, list, tuple, set)):
        return not content
    return False


def add_id_column_for_export(df: pl.DataFrame, result_label: str, id_column: str | None) -> pl.DataFrame:
    """Return a DataFrame copy with deterministic IDs when requested.

    Inserts an ID column of ``<result_label>_<n>`` values; the original frame is
    returned unchanged when no ID column is requested or one already exists.

    Args:
        df (pl.DataFrame): The source DataFrame.
        result_label (str): Label used to prefix generated IDs.
        id_column (str | None): Name of the ID column to insert, if any.

    Returns:
        pl.DataFrame: The original frame or a copy with the ID column inserted.

    """
    if not id_column or id_column in df.columns:
        return df
    id_values = [f"{result_label}_{index}" for index in range(1, df.height + 1)]
    return df.clone().insert_column(0, pl.Series(id_column, id_values))


def to_json_compatible(value: object) -> object:
    """Convert workflow values and metadata into JSON-safe objects.

    Recursively converts DataFrames, Series, mappings, sequences, dates, and paths into
    JSON-serializable equivalents; missing values become ``None`` and other objects fall
    back to their ``__name__`` or string representation.

    Args:
        value (object): The value to convert.

    Returns:
        object: A JSON-serializable representation of the value.

    """
    if isinstance(value, pl.DataFrame):
        return value.to_dicts()
    if isinstance(value, pl.Series):
        return value.to_list()
    if isinstance(value, dict):
        return {str(key): to_json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_json_compatible(item) for item in value]
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "__name__"):
        return value.__name__
    return str(value)


def write_json_file(path: Path, content: object) -> None:
    """Write JSON content with stable formatting.

    Creates parent directories and serializes the content through ``to_json_compatible``.

    Args:
        path (Path): Destination file path.
        content (object): Content to serialize as JSON.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(to_json_compatible(content), handle, ensure_ascii=False, indent=2)


def write_yaml_file(path: Path, content: object) -> None:
    """Write YAML content with stable formatting.

    Creates parent directories and serializes the content through ``to_json_compatible``.

    Args:
        path (Path): Destination file path.
        content (object): Content to serialize as YAML.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(to_json_compatible(content), handle, sort_keys=False, allow_unicode=True)


def write_text_file(path: Path, content: object) -> None:
    """Write text output content.

    Creates parent directories and writes the stringified content.

    Args:
        path (Path): Destination file path.
        content (object): Content to write as text.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(str(content))


def graph_relative_output_path(path: Path, output_dir: Path) -> str:
    """Return a forward-slash graph artifact path relative to ``output_dir``."""
    return path.resolve().relative_to(output_dir.resolve()).as_posix()


def get_output_graph_metadata(workflow_metadata: dict | None, label: str) -> dict[str, Any]:
    """Return enrichment metadata for a graph output label when available."""
    if not isinstance(workflow_metadata, dict):
        return {}
    enrichment_metadata = workflow_metadata.get("uniprot_enrichment")
    if not isinstance(enrichment_metadata, dict):
        return {}
    label_metadata = enrichment_metadata.get(label)
    return label_metadata if isinstance(label_metadata, dict) else {}


def row_is_intended_graph_payload(row: dict[str, Any]) -> bool:
    """Return whether a row carries one of the supported PathwayCommons graph endpoints."""
    return (row.get("source_database"), row.get("source_endpoint")) in GRAPH_ENRICHMENT_OUTPUTS


def has_externalizable_graph_payloads(
    content: object,
    output_metadata: dict[str, Any] | None = None,
) -> bool:
    """Return whether tabular content contains raw graph payloads."""
    if not isinstance(content, pl.DataFrame) or GRAPH_JSON_COLUMN not in content.columns:
        return False
    if not isinstance(output_metadata, dict) or output_metadata.get("output_kind") != GRAPH_RAW_OUTPUT_KIND:
        return False
    if {"source_database", "source_endpoint"}.issubset(set(content.columns)):
        return any(row_is_intended_graph_payload(row) for row in content.to_dicts())
    return True


def is_empty_graph_payload(value: object, graph_record_count: object = None) -> bool:
    """Return whether a raw graph payload should be treated as empty."""
    if (
        isinstance(graph_record_count, (int, float))
        and not isinstance(graph_record_count, bool)
        and int(graph_record_count) == 0
    ):
        return True
    if value is None:
        return True
    text = str(value).strip()
    if not text or text in {"[]", "{}"}:
        return True
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return False
    return payload in ({}, [])


def graph_payload_json_text(value: object) -> tuple[object, str]:
    """Return the graph payload object and deterministic JSON text for writing."""
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError as exc:
            msg = f"Graph payload bytes are not valid UTF-8: {exc}"
            raise ValueError(msg) from exc
    if isinstance(value, str):
        try:
            payload = json.loads(value)
        except json.JSONDecodeError:
            msg = "Graph payload text is not valid JSON."
            raise ValueError(msg) from None
    else:
        payload = to_json_compatible(value)
    text = json.dumps(
        to_json_compatible(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return payload, text


def safe_graph_filename_part(value: object) -> str:
    """Return a deterministic filename component safe for Windows and POSIX."""
    text = str(value or "").strip()
    text = text.replace("/", "_").replace("\\", "_")
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    text = text.strip(" ._-")
    if not text:
        return ""
    text = text[:120].rstrip(" .")
    stem = text.split(".", 1)[0].upper()
    if stem in WINDOWS_RESERVED_FILENAMES:
        text = f"graph_{text}"
    return text


def source_query_for_digest(value: object) -> object:
    """Return the source query as a JSON-native object when possible."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def graph_payload_digest(row: dict[str, Any], payload_text: str) -> str:
    """Return a stable digest for graph identity and canonical payload text."""
    digest_payload = {
        "source_accession": row.get("source_accession"),
        "source_query": source_query_for_digest(row.get("source_query")),
        "source_database": row.get("source_database"),
        "source_endpoint": row.get("source_endpoint"),
        "graph_payload": json.loads(payload_text),
    }
    digest_text = json.dumps(
        to_json_compatible(digest_payload),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(digest_text.encode("utf-8")).hexdigest()


def graph_payload_file_name(row: dict[str, Any], export_label: str, digest: str, digest_length: int) -> str:
    """Return a deterministic graph payload filename for one digest length."""
    accession_part = safe_graph_filename_part(row.get("source_accession"))
    if accession_part:
        return f"{accession_part}__{export_label}__{digest[:digest_length]}.json"
    return f"query_{digest[:digest_length]}__{export_label}.json"


def graph_file_candidates(row: dict[str, Any], export_label: str, digest: str) -> list[str]:
    """Return deterministic filename candidates for existing-file disambiguation."""
    candidates = [
        graph_payload_file_name(row, export_label, digest, length)
        for length in (16, 24, 32, 40, 64)
    ]
    seen: set[str] = set()
    unique_candidates = []
    for candidate in candidates:
        candidate_key = candidate.casefold()
        if candidate_key in seen:
            continue
        seen.add(candidate_key)
        unique_candidates.append(candidate)
    return unique_candidates


def safe_graph_file_path(output_dir: Path, graph_dir: Path, file_name: str) -> Path:
    """Return a resolved graph artifact path guaranteed to stay below graph_dir."""
    if (
        not file_name
        or file_name in {".", ".."}
        or file_name != file_name.rstrip(" .")
        or ":" in file_name
        or "/" in file_name
        or "\\" in file_name
    ):
        msg = f"Unsafe graph payload filename: {file_name}"
        raise ValueError(msg)
    graph_output_dir = (output_dir / graph_dir).resolve()
    file_path = (graph_output_dir / file_name).resolve()
    file_path.relative_to(graph_output_dir)
    return file_path


def existing_file_matches(file_path: Path, payload_bytes: bytes) -> bool:
    """Return whether an existing artifact exactly matches the new payload bytes."""
    try:
        return file_path.read_bytes() == payload_bytes
    except OSError:
        return False


def select_graph_file_path(
    row: dict[str, Any],
    *,
    output_dir: Path,
    graph_dir: Path,
    export_label: str,
    digest: str,
    payload_bytes: bytes,
    used_file_names: set[str],
) -> Path:
    """Return a stable graph artifact path without order-dependent suffixes."""
    for file_name in graph_file_candidates(row, export_label, digest):
        file_name_key = file_name.casefold()
        file_path = safe_graph_file_path(output_dir, graph_dir, file_name)
        if file_name_key in used_file_names:
            if file_path.exists() and existing_file_matches(file_path, payload_bytes):
                return file_path
            continue
        if file_path.exists() and not existing_file_matches(file_path, payload_bytes):
            continue
        used_file_names.add(file_name_key)
        return file_path
    msg = "Could not derive a collision-free deterministic graph artifact filename."
    raise ValueError(msg)


def write_graph_payload_atomically(file_path: Path, payload_bytes: bytes) -> tuple[int, str, bool]:
    """Write a graph payload atomically unless an identical artifact already exists."""
    payload_hash = hashlib.sha256(payload_bytes).hexdigest()
    file_size = len(payload_bytes)
    if file_path.exists():
        existing_bytes = file_path.read_bytes()
        if hashlib.sha256(existing_bytes).hexdigest() == payload_hash and existing_bytes == payload_bytes:
            return file_size, payload_hash, False
        msg = f"Refusing to overwrite existing graph artifact: {file_path}"
        raise FileExistsError(msg)

    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            delete=False,
            dir=file_path.parent,
            prefix=f".{file_path.name}.",
            suffix=".tmp",
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(payload_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(file_path)
    except Exception:
        if temp_path is not None:
            with contextlib.suppress(OSError):
                temp_path.unlink()
        raise
    return file_size, payload_hash, True


def build_graph_artifact_info(
    *,
    export_label: str,
    row: dict,
    file_path: Path,
    relative_path: str,
    file_size: int,
    sha256: str,
) -> dict:
    """Return metadata for one successfully written graph payload artifact."""
    return {
        "label": export_label,
        "file": file_path.name,
        "path": relative_path,
        "category": "graph_payload",
        "source_database": row.get("source_database"),
        "endpoint": row.get("source_endpoint"),
        "graph_format": row.get("graph_format"),
        "graph_record_count": row.get("graph_record_count"),
        "file_size_bytes": file_size,
        "sha256": sha256,
    }


def externalize_graph_payloads(
    content: pl.DataFrame,
    *,
    output_dir: Path,
    export_label: str,
) -> tuple[pl.DataFrame, list[dict], dict[str, object]]:
    """Write graph payload JSON artifacts and return the graph-light export frame."""
    if GRAPH_JSON_COLUMN not in content.columns:
        return content, [], {}

    records = content.to_dicts()
    graph_dir = Path("graphs") / export_label
    used_file_names: set[str] = set()
    artifact_infos_by_path: dict[str, dict] = {}
    artifact_infos: list[dict] = []
    failures: list[dict[str, object]] = []

    for row_index, row in enumerate(records, start=1):
        payload_value = row.get(GRAPH_JSON_COLUMN)
        graph_record_count = row.get("graph_record_count")
        if (
            is_empty_graph_payload(payload_value, graph_record_count)
            or not row_is_intended_graph_payload(row)
        ):
            continue
        try:
            _payload, payload_text = graph_payload_json_text(payload_value)
            payload_bytes = payload_text.encode("utf-8")
            digest = graph_payload_digest(row, payload_text)
            file_path = select_graph_file_path(
                row,
                output_dir=output_dir,
                graph_dir=graph_dir,
                export_label=export_label,
                digest=digest,
                payload_bytes=payload_bytes,
                used_file_names=used_file_names,
            )
            file_size, payload_hash, _was_written = write_graph_payload_atomically(file_path, payload_bytes)
            relative_path = graph_relative_output_path(file_path, output_dir)
        except Exception as exc:  # noqa: BLE001  # preserve payload and continue exporting other rows
            log.warning(
                "Could not write graph payload artifact for %s row %s: %s",
                export_label,
                row_index,
                exc,
            )
            failures.append({"row": row_index, "error": str(exc)})
            continue

        row["graph_file"] = relative_path
        row["graph_file_size_bytes"] = file_size
        row["graph_sha256"] = payload_hash
        row.pop(GRAPH_JSON_COLUMN, None)
        artifact_key = relative_path.casefold()
        if artifact_key not in artifact_infos_by_path:
            artifact_infos_by_path[artifact_key] = build_graph_artifact_info(
                export_label=export_label,
                row=row,
                file_path=file_path,
                relative_path=relative_path,
                file_size=file_size,
                sha256=payload_hash,
            )
            artifact_infos.append(artifact_infos_by_path[artifact_key])

    export_df = pl.DataFrame(records, infer_schema_length=None) if records else content
    for column in GRAPH_FILE_COLUMNS:
        if column in export_df.columns:
            dtype = pl.Int64 if column == "graph_file_size_bytes" else pl.String
            export_df = export_df.with_columns(pl.col(column).cast(dtype))

    graph_metadata: dict[str, object] = {
        "graph_payload_files_written": len(artifact_infos),
    }
    if artifact_infos:
        graph_metadata["graph_payload_directory"] = graph_dir.as_posix()
    if failures:
        graph_metadata["graph_payload_write_failures"] = failures
    return export_df, artifact_infos, graph_metadata


def annotate_graph_payload_metadata(
    workflow_metadata: dict | None,
    label: str,
    graph_metadata: dict[str, object],
) -> None:
    """Annotate enrichment metadata with graph artifact export results."""
    if workflow_metadata is None or not graph_metadata:
        return
    enrichment_metadata = workflow_metadata.get("uniprot_enrichment")
    if not isinstance(enrichment_metadata, dict):
        return
    label_metadata = enrichment_metadata.setdefault(label, {})
    if not isinstance(label_metadata, dict):
        return
    label_metadata.setdefault("output_kind", "raw_graph")
    label_metadata.setdefault("graph_serialization", "json")
    label_metadata.setdefault("graph_tabularization", "one_row_per_source")
    label_metadata.update(graph_metadata)


def build_output_info(
    label: str,
    output_path: Path,
    content: object,
    exported_content: object,
    output_category: str,
) -> dict:
    """Return metadata for an exported output file.

    Adds row/column details for DataFrames or a record count for list/dict content.

    Args:
        label (str): The result label.
        output_path (Path): Path of the written file.
        content (object): The original content before export-time transforms.
        exported_content (object): The content actually written.
        output_category (str): Category of the output (e.g. "result", "enrichment").

    Returns:
        dict: Output-file metadata.

    """
    info: dict[str, Any] = {
        "label": label,
        "file": output_path.name,
        "path": str(output_path),
        "category": output_category,
    }
    if isinstance(exported_content, pl.DataFrame):
        info["rows"] = exported_content.height
        info["columns"] = len(exported_content.columns)
        info["column_names"] = [str(column) for column in exported_content.columns]
    elif isinstance(content, (list, dict)):
        info["records"] = len(content)
    return info


def export_single_result(
    label: object,
    content: object,
    output_dir: Path,
    export_format: str,
    id_column: str | None,
    suffix_results: bool,
    graph_artifact_infos: list[dict] | None = None,
    workflow_metadata: dict | None = None,
) -> dict | None:
    """Export one workflow result and return output metadata.

    Skips invalid labels and empty content, then writes the result in the requested
    format (csv/parquet/json/xml), optionally inserting an ID column.

    Args:
        label (object): The result label.
        content (object): The result content to export.
        output_dir (Path): Directory to write the file into.
        export_format (str): User-facing export format.
        id_column (str | None): Name of an ID column to insert, if any.
        suffix_results (bool): Whether to suffix the file stem with ``_results`` and
            mark the output category as a primary result.
        graph_artifact_infos (list[dict] | None): Collector for graph artifact metadata entries.
        workflow_metadata (dict | None): Workflow metadata to annotate with graph export outcomes.

    Returns:
        dict | None: Output-file metadata, or ``None`` if nothing was exported.

    """
    if not is_valid_export_label(label) or is_empty_export_content(content):
        return None

    export_label = str(label).strip()
    tabular_format = normalize_export_format(export_format)
    file_stem = f"{export_label}_results" if suffix_results else export_label
    output_category = "result" if suffix_results else "enrichment"
    graph_metadata: dict[str, object] = {}
    export_df = content
    graph_output_metadata = get_output_graph_metadata(workflow_metadata, export_label)
    graph_payloads_externalized = False

    if isinstance(content, pl.DataFrame):
        export_df = add_id_column_for_export(content, export_label, id_column)
        if has_externalizable_graph_payloads(export_df, graph_output_metadata):
            export_df, artifact_infos, graph_metadata = externalize_graph_payloads(
                export_df,
                output_dir=output_dir,
                export_label=export_label,
            )
            graph_payloads_externalized = True
            if graph_artifact_infos is not None:
                graph_artifact_infos.extend(artifact_infos)
            annotate_graph_payload_metadata(workflow_metadata, export_label, graph_metadata)

    if isinstance(export_df, pl.DataFrame) and tabular_format in {"csv", "parquet"}:
        output_path = output_dir / f"{file_stem}.{tabular_format}"
        exported_path = export_dataframe(export_df, output_path, output_format=tabular_format)
        info = build_output_info(
            export_label,
            exported_path,
            content,
            export_df,
            output_category,
        )
        info.update(graph_metadata)
        return info

    if export_format == "json":
        output_path = output_dir / f"{file_stem}.json"
        exported_content = export_df
        write_json_file(output_path, exported_content)
        info = build_output_info(
            export_label,
            output_path,
            content,
            exported_content,
            output_category,
        )
        info.update(graph_metadata)
        return info

    if export_format == "xml":
        output_path = output_dir / f"{file_stem}.xml"
        exported_content = export_df if graph_payloads_externalized else content
        write_text_file(output_path, exported_content)
        info = build_output_info(
            export_label,
            output_path,
            content,
            exported_content,
            output_category,
        )
        info.update(graph_metadata)
        return info

    return None


def export_workflow_outputs(
    data: object,
    output_dir: Path,
    export_format: str,
    id_column: str | None,
    workflow_metadata: dict | None = None,
) -> list[dict]:
    """Export workflow outputs and return output-file metadata.

    Exports each primary result, then any nested ``uniprot_enrichment`` outputs.

    Args:
        data (object): The workflow result mapping; non-mappings yield no outputs.
        output_dir (Path): Directory to write files into.
        export_format (str): User-facing export format.
        id_column (str | None): Name of an ID column to insert, if any.
        workflow_metadata (dict | None): Workflow metadata to annotate with graph export outcomes.

    Returns:
        list[dict]: Metadata for each exported file.

    """
    output_dir.mkdir(parents=True, exist_ok=True)
    if not isinstance(data, dict):
        return []

    output_infos: list[dict] = []
    for label, content in data.items():
        if label == "uniprot_enrichment":
            continue
        graph_artifact_infos: list[dict] = []
        info = export_single_result(
            label,
            content,
            output_dir,
            export_format,
            id_column,
            suffix_results=True,
            graph_artifact_infos=graph_artifact_infos,
            workflow_metadata=workflow_metadata,
        )
        if info:
            output_infos.append(info)
            output_infos.extend(graph_artifact_infos)

    enrichment_data = data.get("uniprot_enrichment")
    if isinstance(enrichment_data, dict):
        for label, content in enrichment_data.items():
            graph_artifact_infos = []
            info = export_single_result(
                label,
                content,
                output_dir,
                export_format,
                id_column,
                suffix_results=False,
                graph_artifact_infos=graph_artifact_infos,
                workflow_metadata=workflow_metadata,
            )
            if info:
                output_infos.append(info)
                output_infos.extend(graph_artifact_infos)

    return output_infos


def count_unique_sequences(data: object, sequence_column: str | None) -> int | None:
    """Return the unique sequence count across tabular outputs when available.

    Args:
        data (object): The workflow result mapping.
        sequence_column (str | None): Column holding sequence values.

    Returns:
        int | None: The number of distinct sequences, or ``None`` when unavailable.

    """
    if not sequence_column or not isinstance(data, dict):
        return None

    sequence_values = []
    for label, content in data.items():
        if label == "uniprot_enrichment":
            continue
        if isinstance(content, pl.DataFrame) and sequence_column in content.columns:
            sequence_values.extend(content[sequence_column].drop_nulls().cast(pl.String).to_list())

    if not sequence_values:
        return None
    return len(set(sequence_values))


def is_count_like_reporting_map(value: dict) -> bool:
    """Return whether a nested reporting map can be filled with counts.

    Args:
        value (dict): A nested reporting map.

    Returns:
        bool: True if non-empty and every value is ``None`` or a non-boolean number.

    """
    if not value:
        return False
    return all(
        item is None or (isinstance(item, (int, float)) and not isinstance(item, bool))
        for item in value.values()
    )


def get_exported_result_labels(output_infos: list[dict]) -> set[str]:
    """Return result labels that were exported with the query-composition label column.

    Args:
        output_infos (list[dict]): Metadata for exported files.

    Returns:
        set[str]: Labels of primary results containing the label column.

    """
    return {
        str(info["label"])
        for info in output_infos
        if info.get("category") == "result"
        and info.get("label") is not None
        and QUERY_COMPOSITION_LABEL_COLUMN in info.get("column_names", [])
    }


def get_expected_query_composition_labels(workflow_values: dict) -> list[str]:
    """Return query-composition labels declared in the executable query.

    Parses the comma-separated query, extracting the label from each ``query=label`` pair
    in declaration order without duplicates.

    Args:
        workflow_values (dict): Workflow values containing the ``query`` string.

    Returns:
        list[str]: Declared labels in order of first appearance.

    """
    query_value = workflow_values.get("query")
    if not isinstance(query_value, str):
        return []

    labels = []
    seen = set()
    for raw_part in query_value.split(","):
        query_part = raw_part.strip()
        if not query_part:
            continue
        try:
            _, label = split_pair(query_part)
        except ValueError:
            continue
        if label and label not in seen:
            labels.append(label)
            seen.add(label)
    return labels


def count_query_composition_labels(
    workflow_values: dict,
    data: object,
    output_infos: list[dict],
) -> dict[str, int]:
    """Return row counts by query-composition label from the main exported result.

    Applies only in ``query_composition`` mode, counting label-column values from the
    primary exported result and seeding expected labels with zero.

    Args:
        workflow_values (dict): Workflow values, including mode and modality.
        data (object): The workflow result mapping.
        output_infos (list[dict]): Metadata for exported files.

    Returns:
        dict[str, int]: Row counts keyed by label, or an empty dict when not applicable.

    """
    if workflow_values.get("mode") != "query_composition" or not isinstance(data, dict):
        return {}

    exported_result_labels = get_exported_result_labels(output_infos)
    if not exported_result_labels:
        return {}

    expected_label_counts = dict.fromkeys(get_expected_query_composition_labels(workflow_values), 0)
    primary_label = PRIMARY_RESULT_LABELS.get(str(workflow_values.get("modality")))
    label_order = [primary_label] if primary_label else []
    label_order.extend(label for label in data if label != primary_label)

    for label in label_order:
        if not label or label not in exported_result_labels:
            continue
        content = data.get(label)
        if isinstance(content, pl.DataFrame) and QUERY_COMPOSITION_LABEL_COLUMN in content.columns:
            counts = content[QUERY_COMPOSITION_LABEL_COLUMN].drop_nulls().cast(pl.String).value_counts()
            label_counts = dict(expected_label_counts)
            label_counts.update({str(label_value): int(count) for label_value, count in counts.iter_rows()})
            return label_counts

    return {}


def fill_nested_label_reporting(reporting: dict, label_counts: dict[str, int]) -> dict:
    """Fill nested reporting dictionaries with query-composition label counts.

    Replaces count-like nested maps whose keys overlap the known labels with the
    corresponding counts (defaulting to zero).

    Args:
        reporting (dict): The reporting section to fill.
        label_counts (dict[str, int]): Row counts keyed by label.

    Returns:
        dict: A copy of the reporting section with matching maps filled.

    """
    if not label_counts:
        return reporting

    filled_reporting = dict(reporting)
    label_names = set(label_counts)
    for key, value in reporting.items():
        if not isinstance(value, dict):
            continue
        if not is_count_like_reporting_map(value):
            continue
        if not label_names.intersection(str(label_key) for label_key in value):
            continue
        filled_reporting[key] = {label_key: int(label_counts.get(str(label_key), 0)) for label_key in value}
    return filled_reporting


def calculate_reporting_metrics(
    workflow_values: dict,
    data: object,
    output_infos: list[dict],
    duration_seconds: float,
) -> dict:
    """Fill common reporting metrics from exported outputs when possible.

    Records execution time, retrieved record counts, unique sequence counts, and
    query-composition label counts.

    Args:
        workflow_values (dict): Workflow values, including the base reporting section.
        data (object): The workflow result mapping.
        output_infos (list[dict]): Metadata for exported files.
        duration_seconds (float): Workflow execution time in seconds.

    Returns:
        dict: The reporting section with computed metrics filled in.

    """
    reporting = dict(workflow_values.get("reporting") or {})
    reporting["workflow_execution_time_seconds"] = round(duration_seconds, 3)

    primary_rows = [
        info["rows"] for info in output_infos if "rows" in info and info.get("category") == "result"
    ]
    if primary_rows:
        reporting["retrieved_records"] = int(sum(primary_rows))

    sequence_column = (workflow_values.get("harmonization") or {}).get("sequence_column")
    unique_sequences = count_unique_sequences(data, sequence_column)
    if unique_sequences is not None:
        reporting["unique_sequences"] = unique_sequences

    label_counts = count_query_composition_labels(workflow_values, data, output_infos)
    return fill_nested_label_reporting(reporting, label_counts)


def collect_metadata_errors(value: object, path: tuple[str, ...] = ()) -> list[dict]:
    """Return error messages found in workflow metadata.

    Recursively walks mappings and lists, collecting truthy values under any "error" key.

    Args:
        value (object): The metadata fragment to scan.
        path (tuple[str, ...]): The key path accumulated during recursion.

    Returns:
        list[dict]: Each error as ``{"path": ..., "message": ...}``.

    """
    errors: list[dict] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            current_path = (*path, key_text)
            if key_text.lower() == "error" and item:
                errors.append({"path": ".".join(path), "message": str(item)})
            else:
                errors.extend(collect_metadata_errors(item, current_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(collect_metadata_errors(item, (*path, str(index))))
    return errors


def is_enrichment_error(error_info: dict) -> bool:
    """Return whether an error belongs to enrichment metadata.

    Args:
        error_info (dict): An error entry with a ``path`` field.

    Returns:
        bool: True if the path indicates enrichment metadata.

    """
    path = str(error_info.get("path", "")).lower()
    return "enrichment" in path


def find_primary_fetch_error(workflow_metadata: object) -> str | None:
    """Return the first primary fetch error message, if metadata contains one.

    Args:
        workflow_metadata (object): The workflow metadata to scan.

    Returns:
        str | None: The first non-enrichment fetch error message, or ``None``.

    """
    for error_info in collect_metadata_errors(workflow_metadata):
        path = str(error_info.get("path", "")).lower()
        if "fetch" in path and not is_enrichment_error(error_info):
            return str(error_info.get("message"))
    return None


def has_primary_output(output_infos: list[dict]) -> bool:
    """Return whether exported files include at least one primary result output.

    Args:
        output_infos (list[dict]): Metadata for exported files.

    Returns:
        bool: True if any output has the "result" category.

    """
    return any(info.get("category") == "result" for info in output_infos)


def determine_execution_status(
    workflow_metadata: object,
    output_infos: list[dict],
) -> tuple[str, str | None]:
    """Determine the execution status from exported outputs and metadata errors.

    Returns "failed" when no primary output exists alongside errors, "completed_with_errors"
    when errors exist but a primary output was produced, otherwise "success".

    Args:
        workflow_metadata (object): The workflow metadata to inspect.
        output_infos (list[dict]): Metadata for exported files.

    Returns:
        tuple[str, str | None]: The status string and an optional error message.

    """
    primary_fetch_error = find_primary_fetch_error(workflow_metadata)
    primary_output_exists = has_primary_output(output_infos)
    if primary_fetch_error and not primary_output_exists:
        return "failed", primary_fetch_error

    errors = collect_metadata_errors(workflow_metadata)
    if errors and not primary_output_exists:
        return "failed", str(errors[0].get("message"))
    if errors:
        return "completed_with_errors", str(errors[0].get("message"))
    return "success", None


def build_normalized_workflow_metadata(values: dict) -> dict:
    """Return the executable workflow values for metadata output.

    Args:
        values (dict): Workflow values to extract from.

    Returns:
        dict: The subset of executable values used in metadata.

    """
    metadata_keys = [
        "schema_version",
        "output",
        "query",
        "modality",
        "mode",
        "export_format",
        "enrich",
        "workers",
        "retries",
        "chembl_pages_to_fetch",
        "merge_results",
        "fields",
        "crossref_fields",
        "interaction_type",
        "include_isoform",
        "uniprot_timeout",
        "debug",
        "id_column",
        "include_metadata",
        "include_summary",
        "manifest_file",
        "summary_file",
    ]
    return {key: values.get(key) for key in metadata_keys}


def build_tool_identity() -> dict[str, str]:
    """Return stable tool identity metadata for run provenance."""
    return {
        "tool_name": "BioSeqDownloader",
        "distribution_name": "bioseqdownloader",
        "import_package_name": "bioseq_dl",
        "version": __version__,
    }


def build_metadata_document(
    workflow_metadata: dict,
    workflow_values: dict,
    output_infos: list[dict],
    reporting: dict,
    started_at: str,
    finished_at: str,
    duration_seconds: float,
    status: str = "success",
    error: str | None = None,
) -> dict:
    """Build the detailed workflow metadata document.

    Args:
        workflow_metadata (dict): Metadata returned by the workflow run.
        workflow_values (dict): Normalized workflow values.
        output_infos (list[dict]): Metadata for exported files.
        reporting (dict): Computed reporting metrics.
        started_at (str): ISO timestamp when the run started.
        finished_at (str): ISO timestamp when the run finished.
        duration_seconds (float): Run duration in seconds.
        status (str): Execution status string.
        error (str | None): Error message to include when present.

    Returns:
        dict: The full metadata document.

    """
    execution = {
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round(duration_seconds, 3),
    }
    if error:
        execution["error"] = error

    return {
        "tool": build_tool_identity(),
        "workflow_metadata": workflow_metadata,
        "original_descriptor": workflow_values.get("original_descriptor")
        or collect_descriptor_sections(workflow_values),
        "normalized_descriptor": collect_descriptor_sections(workflow_values),
        "normalized_workflow_values": build_normalized_workflow_metadata(workflow_values),
        "execution": execution,
        "output_files": output_infos,
        "reporting": reporting,
    }


def build_summary_outputs(output_infos: list[dict]) -> dict:
    """Return compact output information for the run summary.

    Args:
        output_infos (list[dict]): Metadata for exported files.

    Returns:
        dict: Per-output summaries keyed by file stem or label.

    """
    outputs = {}
    for info in output_infos:
        label = info.get("label")
        if not label:
            continue
        output_key = Path(str(info.get("file"))).stem if info.get("file") else str(label)
        output_summary = {"file": info.get("file")}
        if "rows" in info:
            output_summary["rows"] = info["rows"]
        if "columns" in info:
            output_summary["columns"] = info["columns"]
        if info.get("category") == "graph_payload":
            output_summary["category"] = "graph_payload"
            if "graph_record_count" in info:
                output_summary["graph_record_count"] = info["graph_record_count"]
        if "graph_payload_files_written" in info:
            output_summary["graph_payload_files_written"] = info["graph_payload_files_written"]
        if "graph_payload_directory" in info:
            output_summary["graph_payload_directory"] = info["graph_payload_directory"]
        outputs[output_key] = output_summary
    return outputs


def build_summary_document(
    workflow_values: dict,
    output_infos: list[dict],
    reporting: dict,
    started_at: str,
    finished_at: str,
    duration_seconds: float,
    metadata_path: Path | None,
    summary_path: Path,
    status: str = "success",
    error: str | None = None,
) -> dict:
    """Build the compact YAML run summary.

    Args:
        workflow_values (dict): Normalized workflow values.
        output_infos (list[dict]): Metadata for exported files.
        reporting (dict): Computed reporting metrics.
        started_at (str): ISO timestamp when the run started.
        finished_at (str): ISO timestamp when the run finished.
        duration_seconds (float): Run duration in seconds.
        metadata_path (Path | None): Path of the metadata file, if written.
        summary_path (Path): Path of the summary file.
        status (str): Execution status string.
        error (str | None): Error message to include when present.

    Returns:
        dict: The compact run summary document.

    """
    query_descriptor = dict(workflow_values.get("query_descriptor") or {})
    query_summary = {"value": workflow_values.get("query")}
    for key in (
        "builder",
        "composition",
        "description",
        "filtering_strategy",
        "fields",
        "crossref_fields",
        "include_isoform",
    ):
        if key in query_descriptor and query_descriptor[key] is not None:
            query_summary[key] = query_descriptor[key]

    execution_summary = {
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round(duration_seconds, 3),
        "enrich": workflow_values.get("enrich"),
        "max_workers": workflow_values.get("workers"),
        "total_retries": workflow_values.get("retries"),
        "chembl_pages_to_fetch": workflow_values.get("chembl_pages_to_fetch"),
    }
    if error:
        execution_summary["error"] = error
    if workflow_values.get("merge_results") is not None:
        execution_summary["merge_results"] = workflow_values.get("merge_results")
    if workflow_values.get("uniprot_timeout") is not None:
        execution_summary["uniprot_timeout"] = workflow_values.get("uniprot_timeout")
    if workflow_values.get("debug"):
        execution_summary["debug"] = workflow_values.get("debug")

    export_summary = {
        "output_dir": workflow_values.get("output"),
        "format": workflow_values.get("export_format"),
        "summary_path": summary_path.name,
    }
    if metadata_path:
        export_summary["metadata_path"] = metadata_path.name

    summary: dict[str, object] = {}
    summary["tool"] = build_tool_identity()
    if workflow_values.get("schema_version"):
        summary["schema_version"] = workflow_values["schema_version"]
    summary["dataset"] = workflow_values.get("dataset") or {}
    summary["query"] = query_summary
    if workflow_values.get("resources"):
        summary["resources"] = workflow_values["resources"]
    summary["execution"] = execution_summary
    if workflow_values.get("harmonization"):
        summary["harmonization"] = workflow_values["harmonization"]
    summary["export"] = export_summary
    summary["outputs"] = build_summary_outputs(output_infos)
    summary["reporting"] = reporting
    summary.update(workflow_values.get("extra_descriptor_sections", {}))
    return summary


def write_failure_reports(
    workflow_values: dict,
    error_message: str,
    started_at: str,
    start_time: float,
) -> None:
    """Write failure metadata and summary reports when an output directory is available.

    No reports are written when no output directory is configured.

    Args:
        workflow_values (dict): Normalized workflow values.
        error_message (str): The failure message to record.
        started_at (str): ISO timestamp when the run started.
        start_time (float): ``perf_counter`` value at the start of the run.

    """
    output = workflow_values.get("output")
    if not output:
        return

    output_dir = Path(output)
    output_infos: list[dict] = []
    finished_at = dt.datetime.now(tz=dt.UTC).replace(microsecond=0).isoformat()
    duration_seconds = time.perf_counter() - start_time
    reporting = calculate_reporting_metrics(workflow_values, {}, output_infos, duration_seconds)
    workflow_metadata = {"error": error_message}

    metadata_path = None
    if workflow_values.get("include_metadata"):
        metadata_path = output_dir / (workflow_values.get("manifest_file") or "metadata.json")
        metadata_document = build_metadata_document(
            workflow_metadata=workflow_metadata,
            workflow_values=workflow_values,
            output_infos=output_infos,
            reporting=reporting,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration_seconds,
            status="failed",
            error=error_message,
        )
        write_json_file(metadata_path, metadata_document)

    if workflow_values.get("include_summary"):
        summary_path = output_dir / (workflow_values.get("summary_file") or "run_summary.yml")
        summary_document = build_summary_document(
            workflow_values=workflow_values,
            output_infos=output_infos,
            reporting=reporting,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration_seconds,
            metadata_path=metadata_path,
            summary_path=summary_path,
            status="failed",
            error=error_message,
        )
        write_yaml_file(summary_path, summary_document)


def split_pair(s: str) -> tuple[str, str]:
    """Split a ``query=label`` or ``query|label`` pair into its parts.

    Args:
        s (str): The pair string to split.

    Returns:
        tuple[str, str]: The stripped query and label.

    Raises:
        ValueError: If the string contains neither ``=`` nor ``|``.

    """
    if "=" in s:
        q, label = s.rsplit("=", 1)
    elif "|" in s:
        q, label = s.split("|", 1)
    else:
        msg = f"Invalid format '{s}'. Use 'query=label' or 'query|label'."
        raise ValueError(msg)
    return q.strip(), label.strip()


def run_workflow(
    config: Path | None = typer.Option(
        None,
        "--config",
        help="Path to a YAML workflow descriptor.",
    ),
    output: str | None = typer.Option(
        None,
        "-o",
        "--output",
        help="Output directory for results.",
    ),
    modality: str | None = typer.Option(
        None,
        "--modality",
        "-m",
        help="Biological modality to run: protein, compound, or interaction.",
    ),
    mode: str | None = typer.Option(
        None,
        "--mode",
        "-d",
        help="Workflow execution mode: query_first or query_composition.",
    ),
    query: str | None = typer.Option(
        None,
        "--query",
        "-q",
        help=(
            "Executable query string. For query_composition, provide labeled pairs such as "
            "query1=label1,query2=label2."
        ),
    ),
    fields: str | None = typer.Option(
        None,
        "--fields",
        help="Comma-separated UniProt fields to fetch. Default is empty (UniProt API defaults).",
    ),
    crossref_fields: str | None = typer.Option(
        None,
        "--crossref-fields",
        help="Comma-separated cross-reference fields for enrichment.",
    ),
    export_format: str | None = typer.Option(
        None,
        "--export-format",
        "-e",
        help="Format to export the results. Options: csv, json, xml, parquet. Default is csv.",
    ),
    enrich: bool | None = typer.Option(
        None,
        "--enrich/--no-enrich",
        help="Whether to perform data enrichment.",
    ),
    max_workers: int | None = typer.Option(
        None,
        "--max-workers",
        "-w",
        help="Maximum number of worker threads to use for API calls.",
    ),
    total_retries: int | None = typer.Option(
        None,
        "--total-retries",
        "-r",
        help="Total number of retries for failed API calls.",
    ),
    chembl_pages_to_fetch: int | None = typer.Option(
        None,
        "--chembl-pages-to-fetch",
        help=(
            "ChEMBL pages to fetch. Use -1 for all pages; positive values cap pages. Limit remains records "
            "per "
            "page."
        ),
    ),
    uniprot_timeout: float | None = typer.Option(
        None,
        "--uniprot-timeout",
        help="Timeout in seconds for UniProt API requests.",
    ),
    debug: bool | None = typer.Option(
        None,
        "--debug/--no-debug",
        help="Enable debug logging.",
    ),
    include_isoform: bool | None = typer.Option(
        None,
        "--include-isoform/--no-include-isoform",
        help="Include isoforms in UniProt results.",
    ),
    interaction_type: str | None = typer.Option(
        None,
        "--interaction-type",
        help="Interaction workflow type, when modality is interaction.",
    ),
) -> None:
    """Run a structured workflow descriptor or CLI-specified workflow."""
    logger = log
    try:
        recipe_values = validate_workflow_recipe(load_workflow_recipe(config)) if config else {}
        cli_values = collect_cli_workflow_values(
            output=output,
            modality=modality,
            mode=mode,
            query=query,
            fields=fields,
            crossref_fields=crossref_fields,
            export_format=export_format,
            enrich=enrich,
            max_workers=max_workers,
            total_retries=total_retries,
            chembl_pages_to_fetch=chembl_pages_to_fetch,
            uniprot_timeout=uniprot_timeout,
            debug=debug,
            include_isoform=include_isoform,
            interaction_type=interaction_type,
        )
        workflow_values = merge_workflow_recipe(cli_values, recipe_values)
        validate_merged_workflow_values(workflow_values)
    except (TypeError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None

    try:
        if workflow_values["debug"]:
            configure_logging(level=logging.DEBUG)
            logger = get_logger("bioseq_dl.cli.workflows")
            logger.debug("Debug logging enabled")
    except Exception as e:  # noqa: BLE001  # defensive catch-all
        logger.warning("Could not configure logging: %s", e)

    wf = MainWorkflow(uniprot_interface=UniprotInterface(total_retries=workflow_values["retries"]))
    started_at = dt.datetime.now(tz=dt.UTC).replace(microsecond=0).isoformat()
    start_time = time.perf_counter()

    try:
        # Both modes call wf.run() with the same kwargs, differing only in how the
        # query is passed (single ``query`` vs labeled ``queries_with_labels``).
        run_kwargs: dict[str, Any] = {
            "mode": workflow_values["mode"],
            "modality": workflow_values["modality"],
            "export_format": workflow_values["export_format"],
            "fields": workflow_values["fields"],
            "enrich": workflow_values["enrich"],
            "download_alphafold_structures": workflow_values["download_alphafold_structures"],
            "download_pdb_structures": workflow_values["download_pdb_structures"],
            "max_workers": workflow_values["workers"],
            "total_retries": workflow_values["retries"],
            "chembl_pages_to_fetch": workflow_values["chembl_pages_to_fetch"],
            "uniprot_timeout": workflow_values["uniprot_timeout"],
            "include_isoform": workflow_values["include_isoform"],
            "interaction_type": workflow_values["interaction_type"],
            "crossref_fields": workflow_values["crossref_fields"],
            "output_dir": workflow_values["output"],
        }
        if workflow_values["mode"] == "query_composition":
            if "," not in workflow_values["query"]:
                msg = "For query_composition, provide multiple queries as 'query1=label1,query2=label2'."
                raise ValueError(msg)  # noqa: TRY301  # validate-then-Exit CLI idiom
            queries = [q.strip() for q in workflow_values["query"].split(",")]
            run_kwargs["queries_with_labels"] = [split_pair(q) for q in queries]
        else:
            run_kwargs["query"] = workflow_values["query"]
        data, meta = wf.run(**run_kwargs)
    except (TimeoutError, RuntimeError, ValueError) as e:
        error_message = str(e)
        logger.exception(error_message)
        write_failure_reports(workflow_values, error_message, started_at, start_time)
        typer.echo(f"Error: {error_message}", err=True)
        raise typer.Exit(code=1) from None
    except Exception as e:
        error_message = str(e)
        logger.exception("Workflow execution failed")
        write_failure_reports(workflow_values, error_message, started_at, start_time)
        typer.echo(f"Error: {error_message}", err=True)
        raise typer.Exit(code=1) from None

    output_dir = Path(workflow_values["output"])
    logger.info("Exporting workflow results to %s", output_dir)
    workflow_metadata = meta if isinstance(meta, dict) else {"metadata": meta}
    output_infos = export_workflow_outputs(
        data=data,
        output_dir=output_dir,
        export_format=workflow_values["export_format"],
        id_column=workflow_values["id_column"],
        workflow_metadata=workflow_metadata,
    )

    finished_at = dt.datetime.now(tz=dt.UTC).replace(microsecond=0).isoformat()
    duration_seconds = time.perf_counter() - start_time
    reporting = calculate_reporting_metrics(workflow_values, data, output_infos, duration_seconds)
    execution_status, execution_error = determine_execution_status(workflow_metadata, output_infos)

    metadata_path = None
    if workflow_values["include_metadata"]:
        metadata_path = output_dir / workflow_values["manifest_file"]
        metadata_document = build_metadata_document(
            workflow_metadata=workflow_metadata,
            workflow_values=workflow_values,
            output_infos=output_infos,
            reporting=reporting,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration_seconds,
            status=execution_status,
            error=execution_error,
        )
        write_json_file(metadata_path, metadata_document)

    if workflow_values["include_summary"]:
        summary_path = output_dir / workflow_values["summary_file"]
        summary_document = build_summary_document(
            workflow_values=workflow_values,
            output_infos=output_infos,
            reporting=reporting,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration_seconds,
            metadata_path=metadata_path,
            summary_path=summary_path,
            status=execution_status,
            error=execution_error,
        )
        write_yaml_file(summary_path, summary_document)

    if execution_status == "failed":
        message = execution_error or "Workflow failed."
        logger.error(message)
        typer.echo(f"Error: {message}", err=True)
        raise typer.Exit(code=1)

    logger.info("Workflow export completed")
    if execution_status == "completed_with_errors":
        typer.echo(f"Workflow completed with errors. Results saved to '{output_dir}'")
    else:
        typer.echo(f"Workflow completed. Results saved to '{output_dir}'")


def validate_workflow(
    config: Path = typer.Argument(
        ...,
        help="Path to the YAML workflow descriptor to validate.",
    ),
) -> None:
    """Validate a workflow YAML descriptor without running it.

    Reports every section-level validation problem at once and exits non-zero, or
    confirms the descriptor is valid and prints the resolved modality/mode/output.
    """
    try:
        recipe = load_workflow_recipe(config)
    except (ValueError, TypeError) as exc:
        typer.echo(f"✗ {exc}", err=True)
        raise typer.Exit(code=1) from None

    errors = collect_workflow_recipe_errors(recipe)
    if errors:
        typer.echo(f"✗ {config} has {len(errors)} validation error(s):", err=True)
        for error in errors:
            typer.echo(f"  - {error}", err=True)
        raise typer.Exit(code=1) from None

    # No errors collected, so this re-derives the normalized values without raising.
    values = validate_workflow_recipe(recipe)
    typer.echo(f"✓ {config} is a valid workflow descriptor.")
    typer.echo(f"  modality: {values['modality']} | mode: {values['mode']}")
    if values.get("output"):
        typer.echo(f"  output: {values['output']}")


workflow_app = typer.Typer(
    name="workflow",
    help="Run or validate data-fetching workflows.",
    no_args_is_help=True,
)
workflow_app.command("run", help="Run a predefined data fetching workflow.")(run_workflow)
workflow_app.command("validate", help="Validate a workflow YAML descriptor without running it.")(
    validate_workflow
)
