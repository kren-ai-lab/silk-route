"""CLI commands for running multi-step download workflows."""

from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd
import typer
import yaml

from bioseq_dl._version import build_tool_identity
from bioseq_dl.core.export import (
    export_dataframe,
    normalize_export_format,
    normalize_user_export_format,
)
from bioseq_dl.core.interfaces.uniprot import UniprotInterface
from bioseq_dl.core.workflow.main_workflow import MainWorkflow
from bioseq_dl.logging import configure_logging, get_logger
from bioseq_dl.workflow_schema_definition import (
    ALLOWED_DESCRIPTOR_SECTION_NAMES as WORKFLOW_ALLOWED_DESCRIPTOR_SECTION_NAMES,
)
from bioseq_dl.workflow_schema_definition import (
    DESCRIPTIVE_DESCRIPTOR_SECTIONS,
    FORMATS,
    GRAPH_PAYLOAD_COMPRESSION_OPTIONS,
    GRAPH_PAYLOAD_STORAGE_OPTIONS,
    INTERACTION_TYPES,
    MODALITIES,
    MODES,
    normalize_optional_field_list,
    validate_workflow_v1_descriptor,
)
from bioseq_dl.workflow_schema_definition import (
    WORKFLOW_SCHEMA_VERSION as WORKFLOW_V1_SCHEMA_VERSION,
)

app = typer.Typer(name="workflow", help="Run predefined data collection workflows.")
log = get_logger("bioseq_dl.cli.workflows")

ALLOWED_DESCRIPTOR_SECTION_NAMES = WORKFLOW_ALLOWED_DESCRIPTOR_SECTION_NAMES
WORKFLOW_SCHEMA_VERSION = WORKFLOW_V1_SCHEMA_VERSION

QUERY_COMPOSITION_LABEL_COLUMN = "_label"
PRIMARY_RESULT_LABELS = {
    "protein": "uniprot",
    "compound": "chembl",
    "interaction": "data",
}
GRAPH_JSON_COLUMN = "graph_json"
GRAPH_FILE_COLUMNS = ("graph_file", "graph_file_size_bytes", "graph_sha256")


def build_default_workflow_values() -> dict:
    """Return fresh workflow defaults for CLI-only and descriptor-backed runs."""
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
        "enrich": False,
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
        "download_alphafold_structures": True,
        "download_pdb_structures": True,
        "id_column": None,
        "include_metadata": True,
        "include_summary": True,
        "manifest_file": "metadata.json",
        "summary_file": "run_summary.yml",
        "graph_payload_storage": "inline",
        "graph_payload_compression": "gzip",
    }


def collect_descriptor_sections(values: dict) -> dict:
    """Collect current descriptor sections from normalized workflow values."""
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
    """Apply effective executable values back into descriptor-shaped metadata."""
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
    execution["max_workers"] = synced.get("workers")
    execution["total_retries"] = synced.get("retries")
    execution["chembl_pages_to_fetch"] = synced.get("chembl_pages_to_fetch")
    execution["merge_results"] = synced.get("merge_results")
    if synced.get("uniprot_timeout") is not None:
        execution["uniprot_timeout"] = synced["uniprot_timeout"]
    execution["debug"] = synced.get("debug")
    execution["download_alphafold_structures"] = synced.get("download_alphafold_structures")
    execution["download_pdb_structures"] = synced.get("download_pdb_structures")
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
    export_section["graph_payload_storage"] = synced.get("graph_payload_storage")
    export_section["graph_payload_compression"] = synced.get("graph_payload_compression")
    synced["export"] = export_section
    return synced


def normalize_graph_payload_storage(value: object) -> str:
    """Normalize graph payload storage mode."""
    normalized = str(value or "inline").strip().lower()
    if normalized not in GRAPH_PAYLOAD_STORAGE_OPTIONS:
        allowed = ", ".join(GRAPH_PAYLOAD_STORAGE_OPTIONS)
        msg = f"Unsupported graph_payload_storage '{value}'. Supported values are: {allowed}."
        raise ValueError(msg)
    return normalized


def normalize_graph_payload_compression(value: object, _storage_mode: str) -> str:
    """Normalize graph payload compression mode for the selected storage mode."""
    default = "gzip"
    normalized = str(default if value is None else value).strip().lower()
    if normalized not in GRAPH_PAYLOAD_COMPRESSION_OPTIONS:
        allowed = ", ".join(GRAPH_PAYLOAD_COMPRESSION_OPTIONS)
        msg = f"Unsupported graph_payload_compression '{value}'. Supported values are: {allowed}."
        raise ValueError(msg)
    return normalized


def load_workflow_recipe(config_path: str | Path) -> dict:
    """Load a workflow descriptor from a YAML file."""
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
    """Validate and normalize a structured workflow descriptor."""
    validated_descriptor = validate_workflow_v1_descriptor(recipe)
    workflow_descriptor = {str(key): value for key, value in recipe.items()}
    schema_version = validated_descriptor["schema_version"]
    dataset = dict(validated_descriptor["dataset"])
    query_descriptor = dict(validated_descriptor["query"])
    execution = dict(validated_descriptor["execution"])
    export_section = dict(validated_descriptor["export"])
    resources = dict(validated_descriptor.get("resources", {}))
    harmonization = dict(validated_descriptor.get("harmonization", {}))
    reporting = dict(validated_descriptor.get("reporting", {}))
    fields = normalize_optional_field_list("query", "fields", query_descriptor.get("fields"))
    crossref_fields = normalize_optional_field_list(
        "query",
        "crossref_fields",
        query_descriptor.get("crossref_fields"),
    )

    extra_descriptor_sections = {
        key: value for key, value in workflow_descriptor.items() if key in DESCRIPTIVE_DESCRIPTOR_SECTIONS
    }

    output_dir = export_section.get("output_dir")
    if not output_dir and dataset.get("name"):
        output_dir = f"results/{dataset['name']}"

    normalized = build_default_workflow_values()
    manifest_file = export_section.get("manifest_file") or "metadata.json"
    summary_file = export_section.get("summary_file") or "run_summary.yml"
    graph_payload_storage = normalize_graph_payload_storage(
        export_section.get("graph_payload_storage", "inline")
    )
    graph_payload_compression = normalize_graph_payload_compression(
        export_section.get("graph_payload_compression"),
        graph_payload_storage,
    )

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
            "enrich": execution.get("enrich", False),
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
            "download_alphafold_structures": execution.get("download_alphafold_structures", True),
            "download_pdb_structures": execution.get("download_pdb_structures", True),
            "id_column": harmonization.get("id_column"),
            "include_metadata": export_section.get("include_metadata", True),
            "include_summary": export_section.get("include_summary", True),
            "manifest_file": manifest_file,
            "summary_file": summary_file,
            "graph_payload_storage": graph_payload_storage,
            "graph_payload_compression": graph_payload_compression,
        }
    )
    return sync_descriptor_from_workflow_values(normalized)


def merge_workflow_recipe(cli_values: dict, recipe_values: dict) -> dict:
    """Merge explicit CLI values with YAML descriptor values."""
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
    """Return workflow values explicitly provided through CLI options."""
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
    """Validate merged workflow CLI and descriptor values."""
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

    interaction_type = values.get("interaction_type")
    if values["modality"] == "interaction" and not interaction_type:
        msg = "interaction_type is required when modality is 'interaction'."
        raise ValueError(msg)
    if interaction_type is not None and interaction_type not in INTERACTION_TYPES:
        msg = (
            f"Unsupported interaction_type '{interaction_type}'. "
            f"Supported interaction types are: {', '.join(INTERACTION_TYPES)}."
        )
        raise ValueError(msg)

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
    graph_payload_storage = normalize_graph_payload_storage(values.get("graph_payload_storage", "inline"))
    values["graph_payload_storage"] = graph_payload_storage
    values["graph_payload_compression"] = normalize_graph_payload_compression(
        values.get("graph_payload_compression"),
        graph_payload_storage,
    )


def is_valid_export_label(label: object) -> bool:
    """Return whether a result label should be exported as a file."""
    if label is None:
        return False
    normalized = str(label).strip()
    if not normalized:
        return False
    return normalized.lower() not in {"none", "null"}


def is_empty_export_content(content: object) -> bool:
    """Return whether export content is empty."""
    if content is None:
        return True
    if isinstance(content, pd.DataFrame):
        return content.empty
    if isinstance(content, str):
        return content.strip() == ""
    if isinstance(content, bytes):
        return content == b""
    if isinstance(content, (dict, list, tuple, set)):
        return len(content) == 0
    return False


def add_id_column_for_export(df: pd.DataFrame, result_label: str, id_column: str | None) -> pd.DataFrame:
    """Return a DataFrame copy with deterministic IDs when requested."""
    if not id_column or id_column in df.columns:
        return df
    export_df = df.copy()
    id_values = [f"{result_label}_{index}" for index in range(1, len(export_df) + 1)]
    # pandas accepts a list for the insert value at runtime; the stub types it as scalar/array-like only.
    export_df.insert(0, id_column, id_values)  # ty: ignore[invalid-argument-type]
    return export_df


def to_json_compatible(value: object) -> object:
    """Convert workflow values and metadata into JSON-safe objects."""
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")
    if isinstance(value, pd.Series):
        return value.tolist()
    if isinstance(value, dict):
        return {str(key): to_json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_json_compatible(item) for item in value]
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    try:
        missing = pd.isna(value)  # type: ignore[no-matching-overload]  # pandas stub: object arg
    except (TypeError, ValueError):
        missing = False
    if isinstance(missing, bool) and missing:
        return None
    if hasattr(value, "__name__"):
        return value.__name__
    return str(value)


def write_json_file(path: Path, content: object) -> None:
    """Write JSON content with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(to_json_compatible(content), handle, ensure_ascii=False, indent=2)


def write_yaml_file(path: Path, content: object) -> None:
    """Write YAML content with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(to_json_compatible(content), handle, sort_keys=False, allow_unicode=True)


def write_text_file(path: Path, content: object) -> None:
    """Write text output content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(str(content))


def has_externalizable_graph_payloads(content: object) -> bool:
    """Return whether tabular content contains raw graph payloads."""
    return isinstance(content, pd.DataFrame) and GRAPH_JSON_COLUMN in content.columns


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
    if isinstance(value, float) and pd.isna(value):
        return True
    text = str(value).strip()
    if not text or text in {"[]", "{}"}:
        return True
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return False
    return payload in ({}, [])


def normalize_graph_payload_text(value: object) -> str:
    """Return a JSON text representation for a graph payload."""
    if isinstance(value, str):
        try:
            payload = json.loads(value)
        except json.JSONDecodeError:
            return json.dumps(value, ensure_ascii=False)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return json.dumps(to_json_compatible(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def safe_graph_filename_part(value: object) -> str:
    """Return a filesystem-safe filename component."""
    text = str(value or "").strip()
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    text = text.strip("._-")
    return text[:120]


def graph_payload_stem(row: pd.Series, export_label: str) -> str:
    """Return a deterministic graph payload filename stem for one row."""
    source_accession = row.get("source_accession")
    accession_part = safe_graph_filename_part(source_accession)
    if accession_part:
        return f"{accession_part}__{export_label}"
    source_query = row.get("source_query")
    source_query_text = json.dumps(to_json_compatible(source_query), sort_keys=True, default=str)
    query_hash = hashlib.sha256(source_query_text.encode("utf-8")).hexdigest()[:16]
    return f"query_{query_hash}__{export_label}"


def graph_payload_suffix(compression: str) -> str:
    """Return the file suffix for graph payload storage."""
    return ".json.gz" if compression == "gzip" else ".json"


def write_graph_payload_bytes(path: Path, payload_bytes: bytes, compression: str) -> None:
    """Write graph payload bytes with optional gzip compression."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if compression == "gzip":
        with (
            path.open("wb") as raw_handle,
            gzip.GzipFile(filename="", mode="wb", fileobj=raw_handle, mtime=0) as gzip_handle,
        ):
            gzip_handle.write(payload_bytes)
        return
    path.write_bytes(payload_bytes)


def externalize_graph_payloads(
    content: pd.DataFrame,
    *,
    output_dir: Path,
    export_label: str,
    graph_payload_storage: str,
    graph_payload_compression: str,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Return a graph-light DataFrame after writing raw graph payload files."""
    if graph_payload_storage in {"inline", "none"} or GRAPH_JSON_COLUMN not in content.columns:
        return content, {}

    export_df = content.copy()
    graph_dir = Path("graphs") / export_label
    graph_output_dir = output_dir / graph_dir
    for column in GRAPH_FILE_COLUMNS:
        if column not in export_df.columns:
            export_df[column] = None

    files_written = 0
    for index, row in export_df.iterrows():
        payload_value = row.get(GRAPH_JSON_COLUMN)
        graph_record_count = row.get("graph_record_count")
        if is_empty_graph_payload(payload_value, graph_record_count):
            continue
        payload_text = normalize_graph_payload_text(payload_value)
        payload_bytes = payload_text.encode("utf-8")
        payload_hash = hashlib.sha256(payload_bytes).hexdigest()
        file_name = (
            f"{graph_payload_stem(row, export_label)}"
            f"{graph_payload_suffix(graph_payload_compression)}"
        )
        file_path = graph_output_dir / file_name
        write_graph_payload_bytes(file_path, payload_bytes, graph_payload_compression)
        export_df.loc[index, "graph_file"] = str((graph_dir / file_name).as_posix())
        export_df.loc[index, "graph_file_size_bytes"] = file_path.stat().st_size
        export_df.loc[index, "graph_sha256"] = payload_hash
        files_written += 1

    if graph_payload_storage == "file":
        export_df = export_df.drop(columns=[GRAPH_JSON_COLUMN])

    return export_df, {
        "graph_payload_directory": str(graph_dir.as_posix()),
        "graph_payload_files_written": files_written,
    }


def build_output_info(
    label: str,
    output_path: Path,
    content: object,
    exported_content: object,
    output_category: str,
) -> dict:
    """Return metadata for an exported output file."""
    info: dict[str, Any] = {
        "label": label,
        "file": output_path.name,
        "path": str(output_path),
        "category": output_category,
    }
    if isinstance(exported_content, pd.DataFrame):
        info["rows"] = len(exported_content)
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
    graph_payload_storage: str = "inline",
    graph_payload_compression: str = "gzip",
) -> dict | None:
    """Export one workflow result and return output metadata."""
    if not is_valid_export_label(label) or is_empty_export_content(content):
        return None

    export_label = str(label).strip()
    tabular_format = normalize_export_format(export_format)
    file_stem = f"{export_label}_results" if suffix_results else export_label
    output_category = "result" if suffix_results else "enrichment"

    if isinstance(content, pd.DataFrame) and tabular_format in {"csv", "parquet"}:
        export_df = add_id_column_for_export(content, export_label, id_column)
        graph_metadata = {}
        if has_externalizable_graph_payloads(export_df):
            graph_metadata = {
                "graph_payload_storage": graph_payload_storage,
                "graph_payload_compression": graph_payload_compression,
            }
            if graph_payload_storage == "none":
                export_df = export_df.drop(columns=[GRAPH_JSON_COLUMN])
            elif graph_payload_storage != "inline":
                export_df, file_graph_metadata = externalize_graph_payloads(
                    export_df,
                    output_dir=output_dir,
                    export_label=export_label,
                    graph_payload_storage=graph_payload_storage,
                    graph_payload_compression=graph_payload_compression,
                )
                graph_metadata.update(file_graph_metadata)
        output_path = output_dir / f"{file_stem}.{tabular_format}"
        exported_path = export_dataframe(export_df, output_path, output_format=tabular_format)
        info = build_output_info(export_label, exported_path, content, export_df, output_category)
        info.update(graph_metadata)
        return info

    if export_format == "json":
        output_path = output_dir / f"{file_stem}.json"
        exported_content = content
        if isinstance(content, pd.DataFrame):
            exported_content = add_id_column_for_export(content, export_label, id_column)
        write_json_file(output_path, exported_content)
        return build_output_info(export_label, output_path, content, exported_content, output_category)

    if export_format == "xml":
        output_path = output_dir / f"{file_stem}.xml"
        write_text_file(output_path, content)
        return build_output_info(export_label, output_path, content, content, output_category)

    return None


def export_workflow_outputs(
    data: object,
    output_dir: Path,
    export_format: str,
    id_column: str | None,
    *,
    graph_payload_storage: str = "inline",
    graph_payload_compression: str = "gzip",
    workflow_metadata: dict | None = None,
) -> list[dict]:
    """Export workflow outputs and return output-file metadata."""
    output_dir.mkdir(parents=True, exist_ok=True)
    if not isinstance(data, dict):
        return []

    output_infos: list[dict] = []
    for label, content in data.items():
        if label == "uniprot_enrichment":
            continue
        info = export_single_result(
            label,
            content,
            output_dir,
            export_format,
            id_column,
            suffix_results=True,
            graph_payload_storage=graph_payload_storage,
            graph_payload_compression=graph_payload_compression,
        )
        if info:
            output_infos.append(info)

    enrichment_data = data.get("uniprot_enrichment")
    if isinstance(enrichment_data, dict):
        for label, content in enrichment_data.items():
            info = export_single_result(
                label,
                content,
                output_dir,
                export_format,
                id_column,
                suffix_results=False,
                graph_payload_storage=graph_payload_storage,
                graph_payload_compression=graph_payload_compression,
            )
            if info:
                annotate_graph_payload_metadata(
                    workflow_metadata,
                    label,
                    info,
                    graph_payload_storage=graph_payload_storage,
                    graph_payload_compression=graph_payload_compression,
                )
                output_infos.append(info)

    return output_infos


def annotate_graph_payload_metadata(
    workflow_metadata: dict | None,
    label: str,
    output_info: dict,
    *,
    graph_payload_storage: str,
    graph_payload_compression: str,
) -> None:
    """Annotate raw-graph enrichment metadata with graph payload export policy."""
    if workflow_metadata is None or "graph_payload_storage" not in output_info:
        return
    enrichment_metadata = workflow_metadata.get("uniprot_enrichment")
    if not isinstance(enrichment_metadata, dict):
        return
    label_metadata = enrichment_metadata.setdefault(label, {})
    if not isinstance(label_metadata, dict):
        return
    label_metadata.update(
        {
            "graph_payload_storage": graph_payload_storage,
            "graph_payload_compression": graph_payload_compression,
        }
    )
    if output_info.get("graph_payload_directory") is not None:
        label_metadata["graph_payload_directory"] = output_info.get("graph_payload_directory")


def count_unique_sequences(data: object, sequence_column: str | None) -> int | None:
    """Return the unique sequence count across tabular outputs when available."""
    if not sequence_column or not isinstance(data, dict):
        return None

    sequence_values = []
    for label, content in data.items():
        if label == "uniprot_enrichment":
            continue
        if isinstance(content, pd.DataFrame) and sequence_column in content.columns:
            sequence_values.extend(content[sequence_column].dropna().astype(str).tolist())

    if not sequence_values:
        return None
    return len(set(sequence_values))


def is_count_like_reporting_map(value: dict) -> bool:
    """Return whether a nested reporting map can be filled with counts."""
    if not value:
        return False
    return all(
        item is None or (isinstance(item, (int, float)) and not isinstance(item, bool))
        for item in value.values()
    )


def get_exported_result_labels(output_infos: list[dict]) -> set[str]:
    """Return result labels that were exported with the query-composition label column."""
    return {
        str(info["label"])
        for info in output_infos
        if info.get("category") == "result"
        and info.get("label") is not None
        and QUERY_COMPOSITION_LABEL_COLUMN in info.get("column_names", [])
    }


def get_expected_query_composition_labels(workflow_values: dict) -> list[str]:
    """Return query-composition labels declared in the executable query."""
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
    """Return row counts by query-composition label from the main exported result."""
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
        if isinstance(content, pd.DataFrame) and QUERY_COMPOSITION_LABEL_COLUMN in content.columns:
            counts = content[QUERY_COMPOSITION_LABEL_COLUMN].dropna().astype(str).value_counts()
            label_counts = dict(expected_label_counts)
            label_counts.update({str(label_value): int(count) for label_value, count in counts.items()})
            return label_counts

    return {}


def fill_nested_label_reporting(reporting: dict, label_counts: dict[str, int]) -> dict:
    """Fill nested reporting dictionaries with query-composition label counts."""
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
    """Fill common reporting metrics from exported outputs when possible."""
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
    """Return error messages found in workflow metadata."""
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
    """Return whether an error belongs to enrichment metadata."""
    path = str(error_info.get("path", "")).lower()
    return "enrichment" in path


def find_primary_fetch_error(workflow_metadata: object) -> str | None:
    """Return the first primary fetch error message, if metadata contains one."""
    for error_info in collect_metadata_errors(workflow_metadata):
        path = str(error_info.get("path", "")).lower()
        if "fetch" in path and not is_enrichment_error(error_info):
            return str(error_info.get("message"))
    return None


def has_primary_output(output_infos: list[dict]) -> bool:
    """Return whether exported files include at least one primary result output."""
    return any(info.get("category") == "result" for info in output_infos)


def determine_execution_status(
    workflow_metadata: object,
    output_infos: list[dict],
) -> tuple[str, str | None]:
    """Determine the execution status from exported outputs and metadata errors."""
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
    """Return the executable workflow values for metadata output."""
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
        "download_alphafold_structures",
        "download_pdb_structures",
        "id_column",
        "include_metadata",
        "include_summary",
        "manifest_file",
        "summary_file",
        "graph_payload_storage",
        "graph_payload_compression",
    ]
    return {key: values.get(key) for key in metadata_keys}


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
    """Build the detailed workflow metadata document."""
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
    """Return compact output information for the run summary."""
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
    workflow_metadata: dict | None = None,
) -> dict:
    """Build the compact YAML run summary."""
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
    source_metadata = workflow_metadata or {}
    for metadata_key, summary_key in (
        ("query_source", "source"),
        ("query_resource", "resource"),
        ("query_model", "model"),
        ("request_plan", "request_plan"),
    ):
        if source_metadata.get(metadata_key) is not None:
            query_summary[summary_key] = source_metadata[metadata_key]

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
    execution_summary["download_alphafold_structures"] = workflow_values.get(
        "download_alphafold_structures"
    )
    execution_summary["download_pdb_structures"] = workflow_values.get("download_pdb_structures")
    if source_metadata.get("number_of_records") is not None:
        execution_summary["number_of_records"] = source_metadata["number_of_records"]

    export_summary = {
        "output_dir": workflow_values.get("output"),
        "format": workflow_values.get("export_format"),
        "graph_payload_storage": workflow_values.get("graph_payload_storage"),
        "graph_payload_compression": workflow_values.get("graph_payload_compression"),
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
    """Write failure metadata and summary reports when an output directory is available."""
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
            workflow_metadata=workflow_metadata,
        )
        write_yaml_file(summary_path, summary_document)


def split_pair(s: str) -> tuple[str, str]:
    """Parse one query_composition pair into query text and label."""
    if "=" in s:
        q, label = s.rsplit("=", 1)
    elif "|" in s:
        q, label = s.split("|", 1)
    else:
        msg = f"Invalid format '{s}'. Use 'query=label' or 'query|label'."
        raise ValueError(msg)
    return q.strip(), label.strip()


@app.command(name="run")
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
        help=(
            "Comma-separated UniProt fields to fetch. Empty values use BioSeqDownloader's "
            "default UniProt return fields."
        ),
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
        if workflow_values["mode"] == "query_first":
            data, meta = wf.run(
                mode=workflow_values["mode"],
                modality=workflow_values["modality"],
                export_format=workflow_values["export_format"],
                query=workflow_values["query"],
                fields=workflow_values["fields"],
                enrich=workflow_values["enrich"],
                max_workers=workflow_values["workers"],
                total_retries=workflow_values["retries"],
                chembl_pages_to_fetch=workflow_values["chembl_pages_to_fetch"],
                uniprot_timeout=workflow_values["uniprot_timeout"],
                include_isoform=workflow_values["include_isoform"],
                interaction_type=workflow_values["interaction_type"],
                crossref_fields=workflow_values["crossref_fields"],
                download_alphafold_structures=workflow_values["download_alphafold_structures"],
                download_pdb_structures=workflow_values["download_pdb_structures"],
                output_dir=workflow_values["output"],
            )
        elif workflow_values["mode"] == "query_composition":
            if "," not in workflow_values["query"]:
                msg = "For query_composition, provide multiple queries as 'query1=label1,query2=label2'."
                raise ValueError(msg)  # noqa: TRY301  # validate-then-Exit CLI idiom
            queries = [q.strip() for q in workflow_values["query"].split(",")]
            queries_with_labels = [split_pair(q) for q in queries]
            data, meta = wf.run(
                mode=workflow_values["mode"],
                modality=workflow_values["modality"],
                export_format=workflow_values["export_format"],
                queries_with_labels=queries_with_labels,
                fields=workflow_values["fields"],
                enrich=workflow_values["enrich"],
                max_workers=workflow_values["workers"],
                total_retries=workflow_values["retries"],
                chembl_pages_to_fetch=workflow_values["chembl_pages_to_fetch"],
                uniprot_timeout=workflow_values["uniprot_timeout"],
                include_isoform=workflow_values["include_isoform"],
                interaction_type=workflow_values["interaction_type"],
                crossref_fields=workflow_values["crossref_fields"],
                download_alphafold_structures=workflow_values["download_alphafold_structures"],
                download_pdb_structures=workflow_values["download_pdb_structures"],
                output_dir=workflow_values["output"],
            )
        else:
            msg = f"Unsupported workflow mode '{workflow_values['mode']}'."
            raise ValueError(msg)  # noqa: TRY301  # validate-then-Exit CLI idiom
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
                graph_payload_storage=workflow_values["graph_payload_storage"],
                graph_payload_compression=workflow_values["graph_payload_compression"],
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
            workflow_metadata=workflow_metadata,
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
