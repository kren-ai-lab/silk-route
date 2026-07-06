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
    parse_query_composition_value,
    validate_workflow_v1_descriptor,
)

DEFAULT_MAX_WORKERS = 5
DEFAULT_TOTAL_RETRIES = 3
DEFAULT_CHEMBL_PAGES_TO_FETCH = -1
DEFAULT_WORKFLOW_FILENAME = "workflow-v1.yml"
DEFAULT_OUTPUT_DIRECTORY_NAME_ERROR = (
    "Dataset name is required because the default output folder is generated as results/{dataset.name}."
)
LEGACY_OUTPUT_DIRECTORY_NAME_ERROR = "dataset.name is required when export.output_dir is not provided."
LOADED_QUERY_VALUE_WARNING = (
    "Loaded the saved query text in Manual query mode. Visual builder reconstruction "
    "is available for YAML files saved with query.builder metadata."
)
QUERY_BUILDER_RESTORE_ERROR_WARNING = (
    "query.builder metadata could not be restored. The saved query text was loaded "
    "in Manual query mode."
)
QUERY_BUILDER_MISMATCH_WARNING = (
    "query.builder metadata did not match query.value. The saved query text was "
    "loaded in Manual query mode."
)
QUERY_COMPOSITION_VALUE_PARSED_NOTE = (
    "Loaded query_composition entries from query.value. Add descriptions if needed "
    "before saving."
)
QUERY_COMPOSITION_PARSE_ERROR_NOTE = (
    "This query_composition value could not be split into labeled query entries. "
    "The saved query text was kept for manual review."
)
QUERY_COMPOSITION_BUILDER_RESTORE_NOTE = (
    "Composition entry '{label}' has builder metadata that could not be restored. "
    "The entry was loaded as a manual query."
)
PROTEIN_CHEMBL_QUERY_WARNING = (
    "The loaded query looks like a ChEMBL query while the dataset is set to Protein. "
    "Protein workflows use UniProt; choose Compound or Protein-ligand interaction "
    "for ChEMBL queries."
)
NON_EDITABLE_METADATA_WARNINGS = {
    "resources": (
        "This file includes resources metadata. It is kept with the descriptor and "
        "shown as read-only in this GUI version."
    ),
    "reporting": (
        "This file includes reporting metadata. It is kept with the descriptor and "
        "shown as read-only in this GUI version."
    ),
    "interaction_retrieval": (
        "This file includes interaction_retrieval metadata. It is kept with the "
        "descriptor and shown as read-only in this GUI version."
    ),
    "activity_retrieval": (
        "This file includes activity_retrieval metadata. It is kept with the "
        "descriptor and shown as read-only in this GUI version."
    ),
    "chemical_metadata_integration": (
        "This file includes chemical_metadata_integration metadata. It is kept with "
        "the descriptor and shown as read-only in this GUI version."
    ),
    "protein_target_integration": (
        "This file includes protein_target_integration metadata. It is kept with the "
        "descriptor and shown as read-only in this GUI version."
    ),
    "temperature_enrichment": (
        "This file includes temperature_enrichment metadata. It is kept with the "
        "descriptor and shown as read-only in this GUI version."
    ),
    "cross_source_integration": (
        "This file includes cross_source_integration metadata. It is kept with the "
        "descriptor and shown as read-only in this GUI version."
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
PUBCHEM_BUILDER_RESOURCE_BY_KEY = {
    "pubchem_compound": "compound",
    "pubchem_structure": "structure",
}
CHEBI_BUILDER_RESOURCE_BY_KEY = {
    "chebi_entity": "entity",
    "chebi_ontology": "ontology",
    "chebi_structure": "structure",
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
    "query.pubchem_builder.row": {
        "field": "name",
        "value": "",
        "threshold": "",
    },
    "query.chebi_builder.rows": [
        {
            "field": "name",
            "operator": "contains",
            "value": "",
            "secondary_value": "",
        }
    ],
    "query.composition.entries": [
        {
            "label": "",
            "value": "",
            "description": "",
            "query_input_mode": "Manual query",
            "query_builder_key": "uniprot",
            "uniprot_builder_rows": [],
            "chembl_builder_rows": [],
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
    "query.pubchem_builder.row": ("query_pubchem_builder_row",),
    "query.chebi_builder.rows": ("query_chebi_builder_rows",),
    "query.composition.entries": ("query_composition_entries",),
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


def make_query_composition_entry() -> dict[str, object]:
    """Return one empty mutable GUI query-composition entry."""
    return {
        "label": "",
        "value": "",
        "description": "",
        "query_input_mode": "Manual query",
        "query_builder_key": "uniprot",
        "uniprot_builder_rows": [],
        "chembl_builder_rows": [],
    }


def build_query_composition_entry_form_values(
    entry: Mapping[str, object],
) -> dict[str, object]:
    """Adapt entry-local builder state to the existing pure query helpers."""
    return {
        "query.input_mode": entry.get("query_input_mode", "manual"),
        "query.value": entry.get("value", ""),
        "query.builder.key": entry.get("query_builder_key", "uniprot"),
        "query.uniprot_builder.rows": entry.get("uniprot_builder_rows", []),
        "query.chembl_builder.rows": entry.get("chembl_builder_rows", []),
    }


def validate_query_composition_entry_builder_compatibility(
    entry: Mapping[str, object],
    *,
    modality: str,
    interaction_type: str | None,
) -> None:
    """Validate an advanced entry builder against its dataset context."""
    if normalize_query_input_mode(entry.get("query_input_mode", "manual")) == "manual":
        return
    from bioseq_dl.gui.query_builders.registry import (  # noqa: PLC0415
        get_query_builder_spec,
        is_query_builder_compatible,
    )

    builder_key = normalize_query_builder_key(entry.get("query_builder_key", "uniprot"))
    spec = get_query_builder_spec(builder_key)
    if not is_query_builder_compatible(spec, modality, interaction_type):
        msg = f"Query builder '{builder_key}' is not compatible with this dataset."
        raise ValueError(msg)


def resolve_query_composition_entry_value(
    entry: Mapping[str, object],
    *,
    modality: str,
    interaction_type: str | None,
) -> str:
    """Resolve one query_composition entry query value."""
    validate_query_composition_entry_builder_compatibility(
        entry,
        modality=modality,
        interaction_type=interaction_type,
    )
    return resolve_query_value_from_form(build_query_composition_entry_form_values(entry))


def build_query_composition_entry_builder_metadata(
    entry: Mapping[str, object],
    *,
    modality: str,
    interaction_type: str | None,
) -> dict[str, object] | None:
    """Build optional query.builder metadata for one composition entry."""
    validate_query_composition_entry_builder_compatibility(
        entry,
        modality=modality,
        interaction_type=interaction_type,
    )
    return build_query_builder_metadata_from_form(
        build_query_composition_entry_form_values(entry)
    )


def build_query_composition_metadata(
    entries: object,
    *,
    modality: str = "protein",
    interaction_type: str | None = None,
) -> list[dict[str, object]]:
    """Build validated query.composition metadata from GUI entries."""
    if not isinstance(entries, list) or not entries:
        msg = "Add at least one labeled query."
        raise ValueError(msg)

    metadata = []
    labels = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            msg = "Each labeled query must be a mapping."
            raise TypeError(msg)
        label = str(entry.get("label") or "").strip()
        value = resolve_query_composition_entry_value(
            entry,
            modality=modality,
            interaction_type=interaction_type,
        ).strip()
        description = str(entry.get("description") or "").strip()
        if not label:
            msg = "Each labeled query needs a label."
            raise ValueError(msg)
        if not value:
            msg = "Each labeled query needs a query value."
            raise ValueError(msg)
        if "=" in label:
            msg = (
                "Labels cannot contain equals signs because equals separates each query "
                "from its label."
            )
            raise ValueError(msg)
        if "," in label:
            msg = "Labels cannot contain commas because commas separate labeled query entries."
            raise ValueError(msg)
        if "," in value:
            msg = (
                "Query-composition values cannot contain commas in this GUI version "
                "because commas separate labeled query entries."
            )
            raise ValueError(msg)
        if label in labels:
            msg = "Labels must be unique."
            raise ValueError(msg)
        labels.add(label)
        item: dict[str, object] = {"label": label, "value": value}
        if description:
            item["description"] = description
        builder_metadata = build_query_composition_entry_builder_metadata(
            entry,
            modality=modality,
            interaction_type=interaction_type,
        )
        if builder_metadata is not None:
            item["builder"] = builder_metadata
        metadata.append(item)
    return metadata


def build_query_composition_value(
    entries: object,
    *,
    modality: str = "protein",
    interaction_type: str | None = None,
) -> str:
    """Build the executable comma-separated query=label string."""
    metadata = build_query_composition_metadata(
        entries,
        modality=modality,
        interaction_type=interaction_type,
    )
    return ",".join(f"{entry['value']}={entry['label']}" for entry in metadata)


def load_query_composition_entries(
    query_section: Mapping[str, object],
    *,
    modality: str = "protein",
    interaction_type: str | None = None,
) -> tuple[list[dict[str, object]], list[str]]:
    """Load GUI composition entries and soft builder-restoration notes."""
    composition = query_section.get("composition")
    if composition is not None:
        entries = []
        notes = []
        for item in cast("list[Mapping[str, object]]", composition):
            entry = make_query_composition_entry()
            entry.update(
                {
                    "label": str(item.get("label") or "").strip(),
                    "value": str(item.get("value") or "").strip(),
                    "description": str(item.get("description") or "").strip(),
                }
            )
            builder_metadata = item.get("builder")
            if builder_metadata is not None:
                note = restore_query_composition_entry_builder_state(
                    entry,
                    builder_metadata,
                    modality=modality,
                    interaction_type=interaction_type,
                )
                if note:
                    notes.append(note)
            entries.append(entry)
        build_query_composition_metadata(
            entries,
            modality=modality,
            interaction_type=interaction_type,
        )
        return entries, notes

    pairs = parse_query_composition_value(str(query_section.get("value") or ""))
    entries = []
    for query_value, label in pairs:
        entry = make_query_composition_entry()
        entry.update({"label": label, "value": query_value})
        entries.append(entry)
    build_query_composition_metadata(
        entries,
        modality=modality,
        interaction_type=interaction_type,
    )
    return entries, []


def restore_query_composition_entry_builder_state(
    entry: dict[str, object],
    metadata: object,
    *,
    modality: str,
    interaction_type: str | None,
) -> str | None:
    """Restore one entry-local builder or return a manual fallback note."""
    label = str(entry.get("label") or "").strip()
    try:
        from bioseq_dl.gui.query_builders.metadata import (  # noqa: PLC0415
            restore_query_builder_metadata,
        )

        restoration = restore_query_builder_metadata(
            metadata,
            entry.get("value"),
            modality,
            interaction_type,
        )
    except (TypeError, ValueError):
        return QUERY_COMPOSITION_BUILDER_RESTORE_NOTE.format(label=label)

    entry["query_input_mode"] = "Advanced builder"
    entry["query_builder_key"] = restoration.builder_key
    entry["builder"] = metadata
    if restoration.builder_key == "uniprot":
        entry["uniprot_builder_rows"] = [
            {
                "connector": row.connector,
                "field": row.field,
                "match_mode": row.match_mode,
                "values": row.values,
            }
            for row in restoration.rows
        ]
    else:
        entry["chembl_builder_rows"] = [
            {
                "field": row.field,
                "filter_type": row.filter_type,
                "value": row.value,
            }
            for row in restoration.rows
        ]
    return None


def collect_load_warnings(descriptor: Mapping[str, object]) -> list[str]:
    """Return warnings for loaded metadata the GUI cannot edit."""
    warnings = []
    dataset = get_mapping_section(descriptor, "dataset")
    query = get_mapping_section(descriptor, "query")
    query_value = str(query.get("value") or "").strip()
    if dataset.get("modality") == "protein" and query_value.lower().startswith("chembl."):
        warnings.append(PROTEIN_CHEMBL_QUERY_WARNING)
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
    form_values["harmonization.metadata_fields"] = csv_text_from_value(harmonization.get("metadata_fields"))

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


def restore_loaded_query_builder_form_values(
    descriptor: Mapping[str, object],
    form_values: dict[str, object],
) -> str | None:
    """Restore advanced query-builder form values or return a manual-mode load note."""
    query = get_mapping_section(descriptor, "query")
    metadata = query.get("builder")
    if metadata is None:
        return LOADED_QUERY_VALUE_WARNING

    dataset = get_mapping_section(descriptor, "dataset")
    modality = str(dataset.get("modality") or "")
    interaction_type_value = dataset.get("interaction_type")
    interaction_type = str(interaction_type_value) if interaction_type_value else None
    try:
        from bioseq_dl.gui.query_builders.metadata import (  # noqa: PLC0415
            QueryBuilderMetadataMismatchError,
            restore_query_builder_metadata,
        )

        restoration = restore_query_builder_metadata(
            metadata,
            query.get("value"),
            modality,
            interaction_type,
        )
    except QueryBuilderMetadataMismatchError:
        return QUERY_BUILDER_MISMATCH_WARNING
    except (TypeError, ValueError):
        return QUERY_BUILDER_RESTORE_ERROR_WARNING

    form_values["query.input_mode"] = get_labeled_option_default(
        "advanced_builder",
        QUERY_INPUT_MODE_LABEL_TO_VALUE,
    )
    form_values["query.builder.key"] = restoration.builder_key
    if restoration.builder_key == "uniprot":
        form_values["query.uniprot_builder.rows"] = [
            {
                "connector": row.connector,
                "field": row.field,
                "match_mode": row.match_mode,
                "values": row.values,
            }
            for row in restoration.rows
        ]
    else:
        form_values["query.chembl_builder.rows"] = [
            {
                "field": row.field,
                "filter_type": row.filter_type,
                "value": row.value,
            }
            for row in restoration.rows
        ]
    return None


def restore_loaded_query_composition_form_values(
    descriptor: Mapping[str, object],
    form_values: dict[str, object],
) -> list[str]:
    """Restore editable query-composition entries and return soft load notes."""
    query = get_mapping_section(descriptor, "query")
    dataset = get_mapping_section(descriptor, "dataset")
    modality = str(dataset.get("modality") or "")
    interaction_type_value = dataset.get("interaction_type")
    interaction_type = str(interaction_type_value) if interaction_type_value else None
    try:
        entries, notes = load_query_composition_entries(
            query,
            modality=modality,
            interaction_type=interaction_type,
        )
    except (TypeError, ValueError):
        entry = make_query_composition_entry()
        entry["value"] = str(query.get("value") or "").strip()
        form_values["query.composition.entries"] = [entry]
        return [QUERY_COMPOSITION_PARSE_ERROR_NOTE]
    form_values["query.composition.entries"] = entries
    if "composition" not in query:
        notes.append(QUERY_COMPOSITION_VALUE_PARSED_NOTE)
    return notes


def load_workflow_yaml_to_form_values(yaml_text: str) -> tuple[dict[str, object], list[str]]:
    """Parse, validate, and convert workflow YAML text to form values and warnings."""
    descriptor = load_workflow_yaml_text(yaml_text)
    validated_descriptor = validate_workflow_v1_descriptor(descriptor)
    form_values = descriptor_to_form_values(validated_descriptor)
    warnings = collect_load_warnings(validated_descriptor)
    dataset = get_mapping_section(validated_descriptor, "dataset")
    if dataset.get("mode") == "query_composition":
        query_composition_notes = restore_loaded_query_composition_form_values(
            validated_descriptor,
            form_values,
        )
        warnings.extend(query_composition_notes)
    else:
        query_builder_note = restore_loaded_query_builder_form_values(
            validated_descriptor,
            form_values,
        )
        if query_builder_note:
            warnings.append(query_builder_note)
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
        match_mode = normalize_uniprot_builder_match_mode(get_builder_row_value(raw_row, "match_mode", "any"))
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


def build_pubchem_builder_row_from_form(form_values: Mapping[str, object]) -> object:
    """Build a pure PubChem query builder row from GUI form values."""
    from bioseq_dl.gui.query_builders.pubchem import PubChemQueryBuilderRow  # noqa: PLC0415

    builder_key = normalize_query_builder_key(get_form_value(form_values, "query.builder.key"))
    if builder_key not in PUBCHEM_BUILDER_RESOURCE_BY_KEY:
        msg = f"Query builder '{builder_key}' is not a PubChem builder."
        raise ValueError(msg)

    raw_row = get_form_value(form_values, "query.pubchem_builder.row")
    if not isinstance(raw_row, Mapping):
        msg = "Advanced PubChem builder row must be a mapping."
        raise TypeError(msg)

    return PubChemQueryBuilderRow(
        resource=PUBCHEM_BUILDER_RESOURCE_BY_KEY[builder_key],
        field=str(get_builder_row_value(raw_row, "field", "")),
        value=str(get_builder_row_value(raw_row, "value", "")),
        threshold=get_builder_row_value(raw_row, "threshold", None),
    )


def build_chebi_builder_rows_from_form(form_values: Mapping[str, object]) -> list[object]:
    """Build pure ChEBI query builder rows from GUI form values."""
    from bioseq_dl.gui.query_builders.chebi import ChEBIQueryBuilderRow  # noqa: PLC0415

    builder_key = normalize_query_builder_key(get_form_value(form_values, "query.builder.key"))
    if builder_key not in CHEBI_BUILDER_RESOURCE_BY_KEY:
        msg = f"Query builder '{builder_key}' is not a ChEBI builder."
        raise ValueError(msg)

    raw_rows = get_form_value(form_values, "query.chebi_builder.rows")
    if not isinstance(raw_rows, list):
        msg = "Advanced ChEBI builder rows must be a list."
        raise TypeError(msg)

    resource = CHEBI_BUILDER_RESOURCE_BY_KEY[builder_key]
    return [
        ChEBIQueryBuilderRow(
            resource=resource,
            field=str(get_builder_row_value(raw_row, "field", "")),
            operator=str(get_builder_row_value(raw_row, "operator", "")),
            value=str(get_builder_row_value(raw_row, "value", "")),
            secondary_value=str(get_builder_row_value(raw_row, "secondary_value", "")),
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

    if builder_key in PUBCHEM_BUILDER_RESOURCE_BY_KEY:
        from bioseq_dl.gui.query_builders.pubchem import build_pubchem_interpreted_query  # noqa: PLC0415

        row = build_pubchem_builder_row_from_form(form_values)
        return build_pubchem_interpreted_query(row)

    if builder_key in CHEBI_BUILDER_RESOURCE_BY_KEY:
        from bioseq_dl.gui.query_builders.chebi import build_chebi_interpreted_query  # noqa: PLC0415

        rows = build_chebi_builder_rows_from_form(form_values)
        if not rows:
            msg = "Advanced ChEBI builder requires at least one condition."
            raise ValueError(msg)
        return build_chebi_interpreted_query(rows)

    msg = f"Unsupported query builder '{builder_key}'."
    raise ValueError(msg)


def build_query_builder_metadata_from_form(
    form_values: Mapping[str, object],
) -> dict[str, object] | None:
    """Build optional neutral metadata for the selected advanced query builder."""
    mode = normalize_query_input_mode(get_form_value(form_values, "query.input_mode"))
    if mode == "manual":
        return None

    builder_key = normalize_query_builder_key(get_form_value(form_values, "query.builder.key"))
    if builder_key == "uniprot":
        from bioseq_dl.gui.query_builders.metadata import (  # noqa: PLC0415
            build_uniprot_query_builder_metadata,
        )

        return build_uniprot_query_builder_metadata(
            build_uniprot_builder_rows_from_form(form_values)
        )

    if builder_key in CHEMBL_BUILDER_RESOURCE_BY_KEY:
        from bioseq_dl.gui.query_builders.metadata import (  # noqa: PLC0415
            build_chembl_query_builder_metadata,
        )

        return build_chembl_query_builder_metadata(
            builder_key,
            build_chembl_builder_rows_from_form(form_values),
        )

    if builder_key in PUBCHEM_BUILDER_RESOURCE_BY_KEY or builder_key in CHEBI_BUILDER_RESOURCE_BY_KEY:
        return None

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


def parse_required_int(value: object, field_name: str) -> int:
    """Parse a required integer GUI value."""
    if isinstance(value, bool):
        msg = f"{field_name} must be an integer."
        raise TypeError(msg)
    if value is None:
        msg = f"{field_name} is required and must be an integer."
        raise ValueError(msg)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        msg = f"{field_name} must be an integer."
        raise ValueError(msg)
    normalized = str(value).strip()
    if not normalized:
        msg = f"{field_name} is required and must be an integer."
        raise ValueError(msg)
    if not re.fullmatch(r"[+-]?\d+", normalized):
        msg = f"{field_name} must be an integer."
        raise ValueError(msg)
    return int(normalized)


def parse_optional_number(value: object, field_name: str) -> float | int | None:
    """Parse an optional integer or float form value."""
    if value is None:
        return None
    if isinstance(value, bool):
        msg = f"{field_name} must be numeric."
        raise TypeError(msg)
    if isinstance(value, int | float):
        return value
    normalized = str(value).strip()
    if not normalized:
        return None
    try:
        parsed = float(normalized)
    except ValueError as exc:
        msg = f"{field_name} must be numeric."
        raise TypeError(msg) from exc
    if parsed.is_integer():
        return int(parsed)
    return parsed


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
    workflow_mode = normalize_labeled_value(
        get_form_value(form_values, "dataset.mode"),
        WORKFLOW_MODE_LABEL_TO_VALUE,
    )
    if workflow_mode == "query_composition":
        entries = get_form_value(form_values, "query.composition.entries")
        modality = str(
            normalize_labeled_value(
                get_form_value(form_values, "dataset.modality"),
                MODALITY_LABEL_TO_VALUE,
            )
        )
        interaction_type_value = normalize_labeled_value(
            get_form_value(form_values, "dataset.interaction_type"),
            INTERACTION_TYPE_LABEL_TO_VALUE,
        )
        interaction_type = str(interaction_type_value) if interaction_type_value else None
        composition_metadata = build_query_composition_metadata(
            entries,
            modality=modality,
            interaction_type=interaction_type,
        )
        query: dict[str, object] = {
            "value": build_query_composition_value(
                entries,
                modality=modality,
                interaction_type=interaction_type,
            ),
            "include_isoform": parse_bool(get_form_value(form_values, "query.include_isoform")),
        }
    else:
        query = {
            "value": resolve_query_value_from_form(form_values),
            "include_isoform": parse_bool(get_form_value(form_values, "query.include_isoform")),
        }

    add_optional_list(query, "fields", get_form_value(form_values, "query.fields"))
    add_optional_list(query, "crossref_fields", get_form_value(form_values, "query.crossref_fields"))
    cleaned_query = cast("dict[str, object]", remove_empty_values(query))
    if workflow_mode == "query_composition":
        cleaned_query["composition"] = composition_metadata
    else:
        builder_metadata = build_query_builder_metadata_from_form(form_values)
        if builder_metadata is not None:
            cleaned_query["builder"] = builder_metadata
    return cleaned_query


def build_execution_section(form_values: Mapping[str, object]) -> dict[str, object]:
    """Build the workflow execution section."""
    execution: dict[str, object] = {
        "enrich": parse_bool(get_form_value(form_values, "execution.enrich")),
        "max_workers": parse_required_int(
            get_form_value(form_values, "execution.max_workers"),
            "execution.max_workers",
        ),
        "total_retries": parse_required_int(
            get_form_value(form_values, "execution.total_retries"),
            "execution.total_retries",
        ),
        "chembl_pages_to_fetch": parse_required_int(
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
        "metadata_fields": parse_csv_list(get_form_value(form_values, "harmonization.metadata_fields")),
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
            errors.append(DEFAULT_OUTPUT_DIRECTORY_NAME_ERROR)
        if dataset.get("modality") == "interaction" and not dataset.get("interaction_type"):
            errors.append("dataset.interaction_type is required when dataset.modality is 'interaction'.")
    if not isinstance(query, dict) or not query.get("value"):
        errors.append("query.value is required.")
    return errors


def normalize_validation_error_message(message: str) -> str:
    """Normalize workflow validation messages for GUI users."""
    if message == LEGACY_OUTPUT_DIRECTORY_NAME_ERROR:
        return DEFAULT_OUTPUT_DIRECTORY_NAME_ERROR
    return message


def validate_generated_descriptor(descriptor: dict[str, object]) -> list[str]:
    """Validate a generated descriptor and return user-facing error messages."""
    errors = collect_prevalidation_errors(descriptor)
    try:
        validate_workflow_v1_descriptor(descriptor)
    except (TypeError, ValueError) as exc:
        errors.append(normalize_validation_error_message(str(exc)))
    return list(dict.fromkeys(errors))
