"""Pure helpers for generating validated workflow-v1 YAML descriptors."""

from __future__ import annotations

import re
from collections.abc import Mapping
from copy import deepcopy
from pathlib import PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING, cast

import yaml

from silkroute.constants.uniprot import (
    XREF_MAPPING,
    get_default_uniprot_return_fields,
    get_effective_uniprot_return_fields,
    get_required_uniprot_fields_for_enrichment,
)
from silkroute.core.workflow.schema import (
    WORKFLOW_SCHEMA_VERSION,
    get_workflow_v1_schema_definition,
    parse_query_composition_value,
    validate_workflow_v1_descriptor,
)
from silkroute.gui.uniprot_return_fields import (
    return_fields_from_selection,
    split_known_and_custom_return_fields,
)

if TYPE_CHECKING:
    # Type-only imports; the builders are imported lazily inside functions at runtime
    # to keep the module free of the query_builders package on import.
    from silkroute.gui.query_builders.chebi import ChEBIQueryBuilderRow
    from silkroute.gui.query_builders.chembl import ChEMBLIC50QueryBuilderRow
    from silkroute.gui.query_builders.pubchem import PubChemQueryBuilderRow

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
QUERY_BUILDER_NOT_EDITABLE_WARNING = (
    "This file includes query.builder metadata. It is kept with the descriptor and "
    "shown as read-only in this GUI version."
)
QUERY_COMPOSITION_NOT_EDITABLE_WARNING = (
    "This file includes query.composition metadata. It is kept with the descriptor "
    "and shown as read-only in this GUI version."
)
QUERY_BUILDER_MISMATCH_WARNING = (
    "query.builder metadata did not match query.value. The saved query text was "
    "loaded in Manual query mode and the original metadata was preserved."
)
QUERY_BUILDER_MODE_WARNING = (
    "query.builder metadata is restored only for Query First workflows. The saved "
    "query text was loaded in Manual query mode and the original metadata was preserved."
)
QUERY_COMPOSITION_VALUE_PARSED_NOTE = (
    "Loaded query_composition entries from query.value. Add descriptions or builders if needed before saving."
)
QUERY_COMPOSITION_PARSE_ERROR_NOTE = (
    "This query_composition value could not be split into labeled query entries. "
    "The saved query text was loaded for manual review."
)
QUERY_COMPOSITION_BUILDER_RESTORE_NOTE = (
    "Composition entry {index} ('{label}') has builder metadata that could not be restored. "
    "Only that entry was loaded as a manual query."
)
UNSUPPORTED_ENRICHMENT_SOURCE_WARNING = (
    "This file includes cross-reference fields that are not shown as selectable enrichment "
    "sources in this GUI version. They are preserved in the advanced cross-reference field."
)
STRUCTURE_DOWNLOAD_NORMALIZED_WARNING = (
    "One or more structure-download flags were disabled because the workflow context, "
    "enrichment setting, or matching enrichment source did not make them executable."
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

# Top-level descriptor sections the GUI cannot edit but must carry through a
# load -> regenerate -> save round-trip unchanged (kept in sync with the
# read-only warnings above).
PRESERVED_TOP_LEVEL_SECTIONS = tuple(NON_EDITABLE_METADATA_WARNINGS)
# Non-widget slot in the form-values dict that carries the preserved sections.
PRESERVED_SECTIONS_FORM_KEY = "__preserved_sections__"
LOADED_INCOMPATIBLE_ENRICHMENT_PASSTHROUGH_FORM_KEY = "__loaded_incompatible_enrichment_passthrough__"

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
CHEMBL_IC50_BUILDER_KEY = "chembl_ic50"
PUBCHEM_BUILDER_RESOURCE_BY_KEY = {
    "pubchem_compound": "compound",
    "pubchem_structure": "structure",
}
CHEBI_BUILDER_RESOURCE_BY_KEY = {
    "chebi_entity": "entity",
}
ENRICHMENT_SOURCE_OPTIONS: dict[str, str] = {
    "AlphaFold": XREF_MAPPING["AlphaFold"][1],
    "BioGRID": XREF_MAPPING["BioGRID"][1],
    "ChEMBL": XREF_MAPPING["ChEMBL"][1],
    "ChEBI": XREF_MAPPING["ChEBI"][1],
    "GO": XREF_MAPPING["GO"][1],
    "InterPro": XREF_MAPPING["InterPro"][1],
    "KEGG": XREF_MAPPING["KEGG"][1],
    "PDB": XREF_MAPPING["PDB"][1],
    "Reactome": XREF_MAPPING["Reactome"][1],
    "RefSeq": XREF_MAPPING["RefSeq"][1],
    "Rhea": XREF_MAPPING["Rhea"][1],
    "SABIO-RK": XREF_MAPPING["SABIO-RK"][1],
    "STRING": XREF_MAPPING["StringDB"][1],
    "PathwayCommons Fetch": "pathwaycommons_fetch",
    "PathwayCommons Top Pathways": "pathwaycommons_top_pathways",
    "PathwayCommons Neighborhood": "pathwaycommons_neighborhood",
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
    "query.chembl_ic50_builder.row": {
        "condition": "range",
        "minimum": 0,
        "maximum": 10,
        "value": None,
        "unit": "nM",
    },
    "query.pubchem_builder.row": {
        "field": "name",
        "value": "",
        "threshold": None,
    },
    "query.chebi_builder.row": {
        "field": "name_contains",
        "value": "",
    },
    "query.composition.entries": [
        {
            "label": "",
            "value": "",
            "description": "",
            "query_input_mode": "manual",
            "query_builder_key": "uniprot",
            "uniprot_builder_rows": [],
            "chembl_builder_rows": [],
            "chembl_ic50_builder_row": {
                "condition": "range",
                "minimum": 0,
                "maximum": 10,
                "value": None,
                "unit": "nM",
            },
            "pubchem_builder_row": {
                "field": "name",
                "value": "",
                "threshold": None,
            },
            "chebi_builder_row": {
                "field": "name_contains",
                "value": "",
            },
        }
    ],
    "query.fields": ", ".join(get_default_uniprot_return_fields()),
    "query.return_field_selections": get_default_uniprot_return_fields(),
    "query.return_field_custom": "",
    "query.crossref_fields": "",
    "query.include_isoform": False,
    "execution.enrich": False,
    "execution.enrichment_sources": [],
    "execution.download_alphafold_structures": False,
    "execution.download_pdb_structures": False,
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


def form_value_alias(field_name: str) -> str:
    """Return the legacy underscore form key for a canonical dotted field name."""
    return field_name.replace(".", "_")


def workflow_yaml_form_defaults() -> dict[str, object]:
    """Return mutable default form values for GUI binding."""
    schema = get_workflow_v1_schema_definition()
    defaults = deepcopy(DEFAULT_FORM_VALUES)
    gui_controlled_defaults = {
        "execution.download_alphafold_structures",
        "execution.download_pdb_structures",
    }
    for field_name in defaults:
        if field_name in gui_controlled_defaults:
            continue
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
    defaults[PRESERVED_SECTIONS_FORM_KEY] = {}
    return defaults


def get_form_value(form_values: Mapping[str, object], field_name: str) -> object:
    """Return a form value using canonical dotted names with legacy aliases."""
    if field_name in form_values:
        return form_values[field_name]
    alias = form_value_alias(field_name)
    if alias in form_values:
        return form_values[alias]
    return workflow_yaml_form_defaults()[field_name]


def has_form_value(form_values: Mapping[str, object], field_name: str) -> bool:
    """Return whether canonical or legacy form data explicitly contains a field."""
    if field_name in form_values:
        return True
    return form_value_alias(field_name) in form_values


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
    dataset = get_mapping_section(descriptor, "dataset")
    query = get_mapping_section(descriptor, "query")
    query_value = str(query.get("value") or "").strip()
    if dataset.get("modality") == "protein" and query_value.lower().startswith("chembl."):
        warnings.append(PROTEIN_CHEMBL_QUERY_WARNING)
    if dataset.get("mode") != "query_composition" and "composition" in query:
        warnings.append(QUERY_COMPOSITION_NOT_EDITABLE_WARNING)
    for section_name, warning in NON_EDITABLE_METADATA_WARNINGS.items():
        if section_name in descriptor:
            warnings.append(warning)
    if has_unsupported_enrichment_sources(query.get("crossref_fields")):
        warnings.append(UNSUPPORTED_ENRICHMENT_SOURCE_WARNING)
    return warnings


def extract_preserved_workflow_sections(descriptor: Mapping[str, object]) -> dict[str, object]:
    """Capture descriptor sections the GUI must carry through load/save.

    ``query.composition`` is regenerated from editable composition entries in
    query_composition mode. ``query.builder`` is preserved when it cannot be restored
    into editable builder state; successfully restored builder metadata is regenerated
    from the form instead.
    """
    preserved: dict[str, object] = {
        key: deepcopy(descriptor[key]) for key in PRESERVED_TOP_LEVEL_SECTIONS if key in descriptor
    }
    query = get_mapping_section(descriptor, "query")
    query_preserved = {key: deepcopy(query[key]) for key in ("builder", "composition") if key in query}
    if query_preserved:
        preserved["query"] = query_preserved
    return preserved


def merge_preserved_workflow_sections(
    descriptor: dict[str, object], preserved: Mapping[str, object]
) -> dict[str, object]:
    """Re-attach preserved read-only sections onto a regenerated descriptor."""
    query_mode_keys = ("builder", "composition")
    for key, value in preserved.items():
        if key == "query" and isinstance(value, Mapping):
            query = descriptor.get("query")
            if not isinstance(query, dict):
                query = {}
                descriptor["query"] = query
            # A form-regenerated builder/composition owns the query's mode: the
            # preserved one never overwrites it or cross-injects the other mode.
            form_owns_mode = any(mode_key in query for mode_key in query_mode_keys)
            for sub_key, sub_value in value.items():
                if sub_key in query_mode_keys and form_owns_mode:
                    continue
                query.setdefault(sub_key, deepcopy(sub_value))
        else:
            descriptor[key] = deepcopy(value)
    return descriptor


def remove_preserved_query_builder(form_values: dict[str, object]) -> None:
    """Drop preserved read-only query.builder metadata after editable restoration."""
    preserved = form_values.get(PRESERVED_SECTIONS_FORM_KEY)
    if not isinstance(preserved, dict):
        return
    query = preserved.get("query")
    if not isinstance(query, dict):
        return
    query.pop("builder", None)
    if not query:
        preserved.pop("query", None)


def remove_preserved_query_composition(form_values: dict[str, object]) -> None:
    """Drop preserved read-only query.composition metadata after editable restoration."""
    preserved = form_values.get(PRESERVED_SECTIONS_FORM_KEY)
    if not isinstance(preserved, dict):
        return
    query = preserved.get("query")
    if not isinstance(query, dict):
        return
    query.pop("composition", None)
    if not query:
        preserved.pop("query", None)


def make_query_composition_entry() -> dict[str, object]:
    """Return one empty mutable query-composition form entry."""
    return deepcopy(cast("list[dict[str, object]]", DEFAULT_FORM_VALUES["query.composition.entries"]))[0]


def build_query_composition_entry_form_values(entry: Mapping[str, object]) -> dict[str, object]:
    """Adapt entry-local builder state to existing single-query helper inputs."""
    return {
        "dataset.mode": "query_first",
        "query.input_mode": entry.get("query_input_mode", "manual"),
        "query.value": entry.get("value", ""),
        "query.builder.key": entry.get("query_builder_key", "uniprot"),
        "query.uniprot_builder.rows": entry.get("uniprot_builder_rows", []),
        "query.chembl_builder.rows": entry.get("chembl_builder_rows", []),
        "query.chembl_ic50_builder.row": entry.get("chembl_ic50_builder_row", {}),
        "query.pubchem_builder.row": entry.get("pubchem_builder_row", {}),
        "query.chebi_builder.row": entry.get("chebi_builder_row", {}),
    }


def validate_query_composition_entry_builder_compatibility(
    entry: Mapping[str, object],
    *,
    modality: str,
    interaction_type: str | None,
) -> None:
    """Validate one advanced composition-entry builder against the dataset context."""
    if normalize_query_input_mode(entry.get("query_input_mode", "manual")) == "manual":
        return
    from silkroute.gui.query_builders.registry import (  # noqa: PLC0415
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
    """Resolve one query-composition entry to an executable query string."""
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
    """Build or preserve optional query-builder metadata for one composition entry."""
    if normalize_query_input_mode(entry.get("query_input_mode", "manual")) == "manual":
        preserved_builder = entry.get("preserved_builder")
        return deepcopy(preserved_builder) if isinstance(preserved_builder, dict) else None
    validate_query_composition_entry_builder_compatibility(
        entry,
        modality=modality,
        interaction_type=interaction_type,
    )
    return build_query_builder_metadata_from_form(build_query_composition_entry_form_values(entry))


def build_query_composition_metadata(
    entries: object,
    *,
    modality: str,
    interaction_type: str | None,
) -> list[dict[str, object]]:
    """Build validated editable query.composition metadata from form entries."""
    if not isinstance(entries, list) or not entries:
        msg = "Add at least one labeled query."
        raise ValueError(msg)

    metadata: list[dict[str, object]] = []
    seen_labels: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, Mapping):
            msg = f"Entry {index}: labeled query must be a mapping."
            raise TypeError(msg)
        label = str(entry.get("label") or "").strip()
        description = str(entry.get("description") or "").strip()
        value = resolve_query_composition_entry_value(
            entry,
            modality=modality,
            interaction_type=interaction_type,
        ).strip()
        if not label:
            msg = f"Entry {index}: label is required."
            raise ValueError(msg)
        if not value:
            msg = f"Entry {index}: value is required."
            raise ValueError(msg)
        if "," in label:
            msg = f"Entry {index}: label cannot contain commas."
            raise ValueError(msg)
        if "=" in label:
            msg = f"Entry {index}: label cannot contain equals signs."
            raise ValueError(msg)
        if "," in value:
            msg = f"Entry {index}: query value cannot contain commas in query_composition mode."
            raise ValueError(msg)
        if label in seen_labels:
            msg = f"Entry {index}: label '{label}' is duplicated."
            raise ValueError(msg)
        seen_labels.add(label)
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


def build_query_composition_value(composition: list[dict[str, object]]) -> str:
    """Build the executable comma-separated query=label representation."""
    return ",".join(f"{entry['value']}={entry['label']}" for entry in composition)


def build_query_composition_builder_restore_note(
    entry: Mapping[str, object],
    index: int,
) -> str:
    """Build a load warning for one composition entry with non-restorable metadata."""
    label = str(entry.get("label") or "unlabeled").strip()
    return QUERY_COMPOSITION_BUILDER_RESTORE_NOTE.format(
        index=index,
        label=label or "unlabeled",
    )


def fallback_query_composition_entry_to_manual(
    entry: dict[str, object],
    builder_metadata: object,
) -> None:
    """Convert one restored composition entry to manual mode, preserving metadata if possible."""
    entry["query_input_mode"] = "manual"
    if isinstance(builder_metadata, dict):
        entry["preserved_builder"] = deepcopy(builder_metadata)
    else:
        entry.pop("preserved_builder", None)


def validate_restored_query_composition_entry_builder(
    entry: dict[str, object],
    builder_metadata: object,
    *,
    index: int,
    modality: str,
    interaction_type: str | None,
) -> str | None:
    """Fallback one entry if restored builder state cannot be regenerated."""
    if normalize_query_input_mode(entry.get("query_input_mode", "manual")) == "manual":
        return None
    try:
        resolve_query_composition_entry_value(
            entry,
            modality=modality,
            interaction_type=interaction_type,
        )
        build_query_composition_entry_builder_metadata(
            entry,
            modality=modality,
            interaction_type=interaction_type,
        )
    except (TypeError, ValueError):
        fallback_query_composition_entry_to_manual(entry, builder_metadata)
        return build_query_composition_builder_restore_note(entry, index)
    return None


def restore_query_composition_entry_builder_state(
    entry: dict[str, object],
    builder_metadata: object,
    *,
    index: int,
    modality: str,
    interaction_type: str | None,
) -> str | None:
    """Restore one composition entry builder or preserve it for manual fallback."""
    try:
        from silkroute.gui.query_builders.metadata import (  # noqa: PLC0415
            restore_query_builder_metadata,
        )

        restoration = restore_query_builder_metadata(
            builder_metadata,
            entry.get("value", ""),
            modality,
            interaction_type,
        )
    except (TypeError, ValueError):
        fallback_query_composition_entry_to_manual(entry, builder_metadata)
        return build_query_composition_builder_restore_note(entry, index)

    entry["query_input_mode"] = "advanced_builder"
    entry["query_builder_key"] = restoration.builder_key
    if restoration.builder_key == "uniprot":
        entry["uniprot_builder_rows"] = [dict(row) for row in restoration.form_rows]
    elif restoration.builder_key == CHEMBL_IC50_BUILDER_KEY:
        entry["chembl_ic50_builder_row"] = dict(restoration.form_rows[0])
    elif restoration.builder_key in CHEMBL_BUILDER_RESOURCE_BY_KEY:
        entry["chembl_builder_rows"] = [dict(row) for row in restoration.form_rows]
    elif restoration.builder_key in PUBCHEM_BUILDER_RESOURCE_BY_KEY:
        entry["pubchem_builder_row"] = dict(restoration.form_rows[0])
    elif restoration.builder_key in CHEBI_BUILDER_RESOURCE_BY_KEY:
        entry["chebi_builder_row"] = dict(restoration.form_rows[0])
    return validate_restored_query_composition_entry_builder(
        entry,
        builder_metadata,
        index=index,
        modality=modality,
        interaction_type=interaction_type,
    )


def load_query_composition_entries(
    query_section: Mapping[str, object],
    *,
    modality: str,
    interaction_type: str | None,
) -> tuple[list[dict[str, object]], list[str]]:
    """Restore query-composition form entries and soft per-entry warnings."""
    composition = query_section.get("composition")
    if composition is not None:
        if not isinstance(composition, list):
            msg = "query.composition must be a list of mappings."
            raise TypeError(msg)
        entries: list[dict[str, object]] = []
        notes: list[str] = []
        for index, item in enumerate(composition, start=1):
            if not isinstance(item, Mapping):
                msg = f"query.composition[{index}] must be a mapping."
                raise TypeError(msg)
            entry = make_query_composition_entry()
            entry["label"] = str(item.get("label") or "").strip()
            entry["value"] = str(item.get("value") or "").strip()
            entry["description"] = str(item.get("description") or "").strip()
            builder_metadata = item.get("builder")
            if builder_metadata is not None:
                note = restore_query_composition_entry_builder_state(
                    entry,
                    builder_metadata,
                    index=index,
                    modality=modality,
                    interaction_type=interaction_type,
                )
                if note:
                    notes.append(note)
            entries.append(entry)
        build_query_composition_metadata(entries, modality=modality, interaction_type=interaction_type)
        return entries, notes

    entries = []
    for value, label in parse_query_composition_value(str(query_section.get("value") or "")):
        entry = make_query_composition_entry()
        entry["label"] = label
        entry["value"] = value
        entries.append(entry)
    build_query_composition_metadata(entries, modality=modality, interaction_type=interaction_type)
    return entries, [QUERY_COMPOSITION_VALUE_PARSED_NOTE]


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


def is_structure_download_descriptor_context_valid(
    descriptor: Mapping[str, object],
    source: str,
) -> bool:
    """Return whether a loaded descriptor may keep an active structure-download flag."""
    dataset = get_mapping_section(descriptor, "dataset")
    query = get_mapping_section(descriptor, "query")
    execution = get_mapping_section(descriptor, "execution")
    interaction_type = dataset.get("interaction_type")
    no_interaction = interaction_type in {None, "", "no_interaction", "no-interaction", "no interaction"}
    if dataset.get("modality") != "protein" or not no_interaction:
        return False
    if execution.get("enrich") is not True:
        return False
    source_keys = {field.casefold() for field in parse_csv_list(query.get("crossref_fields"))}
    return source.casefold() in source_keys


def normalize_loaded_structure_download_flags(
    descriptor: Mapping[str, object],
) -> tuple[dict[str, object], list[str]]:
    """Disable loaded active structure-download flags that the GUI cannot regenerate validly."""
    normalized_descriptor = deepcopy(dict(descriptor))
    execution = normalized_descriptor.get("execution")
    if not isinstance(execution, dict):
        return normalized_descriptor, []

    normalized_any = False
    flag_sources = {
        "download_alphafold_structures": "alphafold",
        "download_pdb_structures": "pdb",
    }
    for flag_name, source in flag_sources.items():
        if execution.get(flag_name) is True and not is_structure_download_descriptor_context_valid(
            normalized_descriptor,
            source,
        ):
            execution[flag_name] = False
            normalized_any = True
    return normalized_descriptor, [STRUCTURE_DOWNLOAD_NORMALIZED_WARNING] if normalized_any else []


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
    query_fields = csv_text_from_value(query.get("fields"))
    form_values["query.fields"] = query_fields
    return_field_selections, return_field_custom = split_known_and_custom_return_fields(query_fields)
    form_values["query.return_field_selections"] = return_field_selections
    form_values["query.return_field_custom"] = ", ".join(return_field_custom)
    form_values["query.crossref_fields"] = csv_text_from_value(query.get("crossref_fields"))
    form_values["execution.enrichment_sources"] = enrichment_sources_from_crossref_fields(
        query.get("crossref_fields")
    )
    form_values["query.include_isoform"] = parse_bool(query.get("include_isoform", False))

    for key in (
        "enrich",
        "max_workers",
        "total_retries",
        "chembl_pages_to_fetch",
        "uniprot_timeout",
        "debug",
        "download_alphafold_structures",
        "download_pdb_structures",
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

    form_values[PRESERVED_SECTIONS_FORM_KEY] = extract_preserved_workflow_sections(descriptor)
    if query.get("crossref_fields") is not None and not is_enrichment_workflow_compatible(form_values):
        form_values[LOADED_INCOMPATIBLE_ENRICHMENT_PASSTHROUGH_FORM_KEY] = True
    return form_values


def restore_loaded_query_builder_form_values(
    descriptor: Mapping[str, object],
    form_values: dict[str, object],
) -> str | None:
    """Restore advanced query-builder form values or return a manual-mode load note."""
    query = get_mapping_section(descriptor, "query")
    metadata = query.get("builder")
    if metadata is None:
        return LOADED_QUERY_VALUE_WARNING if str(query.get("value") or "").strip() else None

    dataset = get_mapping_section(descriptor, "dataset")
    if dataset.get("mode") != "query_first":
        return QUERY_BUILDER_MODE_WARNING

    modality = str(dataset.get("modality") or "")
    interaction_type_value = dataset.get("interaction_type")
    interaction_type = str(interaction_type_value) if interaction_type_value else None
    try:
        from silkroute.gui.query_builders.metadata import (  # noqa: PLC0415
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
        return QUERY_BUILDER_NOT_EDITABLE_WARNING

    form_values["query.input_mode"] = get_labeled_option_default(
        "advanced_builder",
        QUERY_INPUT_MODE_LABEL_TO_VALUE,
    )
    form_values["query.builder.key"] = restoration.builder_key
    if restoration.builder_key == "uniprot":
        form_values["query.uniprot_builder.rows"] = [dict(row) for row in restoration.form_rows]
    elif restoration.builder_key == CHEMBL_IC50_BUILDER_KEY:
        form_values["query.chembl_ic50_builder.row"] = dict(restoration.form_rows[0])
    elif restoration.builder_key in CHEMBL_BUILDER_RESOURCE_BY_KEY:
        form_values["query.chembl_builder.rows"] = [dict(row) for row in restoration.form_rows]
    elif restoration.builder_key in PUBCHEM_BUILDER_RESOURCE_BY_KEY:
        form_values["query.pubchem_builder.row"] = dict(restoration.form_rows[0])
    elif restoration.builder_key in CHEBI_BUILDER_RESOURCE_BY_KEY:
        form_values["query.chebi_builder.row"] = dict(restoration.form_rows[0])
    remove_preserved_query_builder(form_values)
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
        if query.get("composition") is not None:
            raise
        entry = make_query_composition_entry()
        entry["value"] = str(query.get("value") or "").strip()
        form_values["query.composition.entries"] = [entry]
        return [QUERY_COMPOSITION_PARSE_ERROR_NOTE]

    form_values["query.composition.entries"] = entries
    remove_preserved_query_composition(form_values)
    return notes


def load_workflow_yaml_to_form_values(yaml_text: str) -> tuple[dict[str, object], list[str]]:
    """Parse, validate, and convert workflow YAML text to form values and warnings."""
    descriptor = load_workflow_yaml_text(yaml_text)
    descriptor, structure_download_warnings = normalize_loaded_structure_download_flags(descriptor)
    validated_descriptor = validate_workflow_v1_descriptor(descriptor)
    form_values = descriptor_to_form_values(validated_descriptor)
    warnings = structure_download_warnings + collect_load_warnings(validated_descriptor)
    dataset = get_mapping_section(validated_descriptor, "dataset")
    if dataset.get("mode") == "query_composition":
        warnings.extend(restore_loaded_query_composition_form_values(validated_descriptor, form_values))
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
    from silkroute.gui.query_builders.registry import get_query_builder_choices  # noqa: PLC0415

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
    from silkroute.gui.query_builders.uniprot import UniProtQueryBuilderRow  # noqa: PLC0415

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
    from silkroute.gui.query_builders.chembl import ChEMBLFilterQueryBuilderRow  # noqa: PLC0415

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


def build_chembl_ic50_builder_row_from_form(form_values: Mapping[str, object]) -> ChEMBLIC50QueryBuilderRow:
    """Build a pure ChEMBL IC50 query builder row from GUI form values."""
    from silkroute.gui.query_builders.chembl import ChEMBLIC50QueryBuilderRow  # noqa: PLC0415

    builder_key = normalize_query_builder_key(get_form_value(form_values, "query.builder.key"))
    if builder_key != CHEMBL_IC50_BUILDER_KEY:
        msg = f"Query builder '{builder_key}' is not the ChEMBL IC50 builder."
        raise ValueError(msg)

    raw_row = get_form_value(form_values, "query.chembl_ic50_builder.row")
    if not isinstance(raw_row, Mapping):
        msg = "Advanced ChEMBL IC50 builder row must be a mapping."
        raise TypeError(msg)

    return ChEMBLIC50QueryBuilderRow(
        condition=str(get_builder_row_value(raw_row, "condition", "range")),
        minimum=get_builder_row_value(raw_row, "minimum", None),
        maximum=get_builder_row_value(raw_row, "maximum", None),
        value=get_builder_row_value(raw_row, "value", None),
        unit=str(get_builder_row_value(raw_row, "unit", "nM")),
    )


def build_pubchem_builder_row_from_form(form_values: Mapping[str, object]) -> PubChemQueryBuilderRow:
    """Build a pure PubChem query builder row from GUI form values."""
    from silkroute.gui.query_builders.pubchem import (  # noqa: PLC0415
        PubChemQueryBuilderRow,
        normalize_pubchem_builder_threshold_state,
    )

    builder_key = normalize_query_builder_key(get_form_value(form_values, "query.builder.key"))
    if builder_key not in PUBCHEM_BUILDER_RESOURCE_BY_KEY:
        msg = f"Query builder '{builder_key}' is not a PubChem builder."
        raise ValueError(msg)

    raw_row = get_form_value(form_values, "query.pubchem_builder.row")
    if not isinstance(raw_row, Mapping):
        msg = "Advanced PubChem builder row must be a mapping."
        raise TypeError(msg)

    field = str(get_builder_row_value(raw_row, "field", ""))
    return PubChemQueryBuilderRow(
        resource=PUBCHEM_BUILDER_RESOURCE_BY_KEY[builder_key],
        field=field,
        value=str(get_builder_row_value(raw_row, "value", "")),
        threshold=normalize_pubchem_builder_threshold_state(
            field,
            get_builder_row_value(raw_row, "threshold", None),
        ),
    )


def build_chebi_builder_row_from_form(form_values: Mapping[str, object]) -> ChEBIQueryBuilderRow:
    """Build a pure ChEBI query builder row from GUI form values."""
    from silkroute.gui.query_builders.chebi import ChEBIQueryBuilderRow  # noqa: PLC0415

    builder_key = normalize_query_builder_key(get_form_value(form_values, "query.builder.key"))
    if builder_key not in CHEBI_BUILDER_RESOURCE_BY_KEY:
        msg = f"Query builder '{builder_key}' is not a ChEBI builder."
        raise ValueError(msg)

    raw_row = get_form_value(form_values, "query.chebi_builder.row")
    if not isinstance(raw_row, Mapping):
        msg = "Advanced ChEBI builder row must be a mapping."
        raise TypeError(msg)

    return ChEBIQueryBuilderRow(
        resource=CHEBI_BUILDER_RESOURCE_BY_KEY[builder_key],
        field=str(get_builder_row_value(raw_row, "field", "")),
        value=str(get_builder_row_value(raw_row, "value", "")),
    )


def resolve_query_value_from_form(form_values: Mapping[str, object]) -> str:
    """Resolve the executable query.value from manual or advanced query form values."""
    mode = normalize_query_input_mode(get_form_value(form_values, "query.input_mode"))
    if mode == "manual":
        return str(get_form_value(form_values, "query.value") or "").strip()

    builder_key = normalize_query_builder_key(get_form_value(form_values, "query.builder.key"))
    if builder_key == "uniprot":
        from silkroute.gui.query_builders.uniprot import build_uniprot_interpreted_query  # noqa: PLC0415

        rows = build_uniprot_builder_rows_from_form(form_values)
        if not rows:
            msg = "Advanced UniProt builder requires at least one condition."
            raise ValueError(msg)
        return build_uniprot_interpreted_query(rows)

    if builder_key in CHEMBL_BUILDER_RESOURCE_BY_KEY:
        from silkroute.gui.query_builders.chembl import build_chembl_interpreted_query  # noqa: PLC0415

        rows = build_chembl_builder_rows_from_form(form_values)
        if not rows:
            msg = "Advanced ChEMBL builder requires at least one condition."
            raise ValueError(msg)
        return build_chembl_interpreted_query(rows)

    if builder_key == CHEMBL_IC50_BUILDER_KEY:
        from silkroute.gui.query_builders.chembl import build_chembl_ic50_interpreted_query  # noqa: PLC0415

        return build_chembl_ic50_interpreted_query(build_chembl_ic50_builder_row_from_form(form_values))

    if builder_key in PUBCHEM_BUILDER_RESOURCE_BY_KEY:
        from silkroute.gui.query_builders.pubchem import build_pubchem_interpreted_query  # noqa: PLC0415

        row = build_pubchem_builder_row_from_form(form_values)
        return build_pubchem_interpreted_query(row)

    if builder_key in CHEBI_BUILDER_RESOURCE_BY_KEY:
        from silkroute.gui.query_builders.chebi import build_chebi_interpreted_query  # noqa: PLC0415

        row = build_chebi_builder_row_from_form(form_values)
        return build_chebi_interpreted_query(row)

    msg = f"Unsupported query builder '{builder_key}'."
    raise ValueError(msg)


def build_query_builder_metadata_from_form(form_values: Mapping[str, object]) -> dict[str, object] | None:
    """Build optional neutral metadata for the selected advanced query builder."""
    workflow_mode = normalize_labeled_value(
        get_form_value(form_values, "dataset.mode"),
        WORKFLOW_MODE_LABEL_TO_VALUE,
    )
    if workflow_mode != "query_first":
        return None

    mode = normalize_query_input_mode(get_form_value(form_values, "query.input_mode"))
    if mode == "manual":
        return None

    builder_key = normalize_query_builder_key(get_form_value(form_values, "query.builder.key"))
    if builder_key == "uniprot":
        from silkroute.gui.query_builders.metadata import (  # noqa: PLC0415
            build_uniprot_query_builder_metadata,
        )

        return build_uniprot_query_builder_metadata(build_uniprot_builder_rows_from_form(form_values))

    if builder_key in CHEMBL_BUILDER_RESOURCE_BY_KEY:
        from silkroute.gui.query_builders.metadata import (  # noqa: PLC0415
            build_chembl_query_builder_metadata,
        )

        return build_chembl_query_builder_metadata(
            builder_key,
            build_chembl_builder_rows_from_form(form_values),
        )

    if builder_key == CHEMBL_IC50_BUILDER_KEY:
        from silkroute.gui.query_builders.metadata import (  # noqa: PLC0415
            build_chembl_ic50_query_builder_metadata,
        )

        return build_chembl_ic50_query_builder_metadata(build_chembl_ic50_builder_row_from_form(form_values))

    if builder_key in PUBCHEM_BUILDER_RESOURCE_BY_KEY:
        from silkroute.gui.query_builders.metadata import (  # noqa: PLC0415
            build_pubchem_query_builder_metadata,
        )

        return build_pubchem_query_builder_metadata(
            builder_key,
            build_pubchem_builder_row_from_form(form_values),
        )

    if builder_key in CHEBI_BUILDER_RESOURCE_BY_KEY:
        from silkroute.gui.query_builders.metadata import (  # noqa: PLC0415
            build_chebi_query_builder_metadata,
        )

        return build_chebi_query_builder_metadata(
            builder_key,
            build_chebi_builder_row_from_form(form_values),
        )

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


def get_enrichment_source_options() -> dict[str, str]:
    """Return GUI labels mapped to executable enrichment source keys."""
    return dict(ENRICHMENT_SOURCE_OPTIONS)


def normalize_enrichment_sources(value: object) -> list[str]:
    """Normalize GUI enrichment source selections to executable source keys."""
    raw_values = (
        [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, (list, tuple, set))
        else parse_csv_list(value)
    )
    options = get_enrichment_source_options()
    label_to_key = {label.casefold(): key for label, key in options.items()}
    key_lookup = {key.casefold(): key for key in options.values()}
    normalized: list[str] = []
    for raw_value in raw_values:
        lookup_value = raw_value.casefold()
        source_key = label_to_key.get(lookup_value) or key_lookup.get(lookup_value)
        if source_key and source_key not in normalized:
            normalized.append(source_key)
    return normalized


def enrichment_sources_from_crossref_fields(value: object) -> list[str]:
    """Infer selectable GUI enrichment sources from cross-reference fields."""
    options = get_enrichment_source_options()
    source_keys = {key.casefold(): key for key in options.values()}
    sources: list[str] = []
    for field in parse_csv_list(value):
        lookup_value = field.casefold()
        source_key = source_keys.get(lookup_value)
        if source_key and source_key not in sources:
            sources.append(source_key)
    return sources


def selected_enrichment_source_keys(form_values: Mapping[str, object]) -> set[str]:
    """Return canonical selected enrichment source keys from visible and advanced state."""
    selected_sources = set(
        normalize_enrichment_sources(get_form_value(form_values, "execution.enrichment_sources"))
    )
    selected_sources.update(
        enrichment_sources_from_crossref_fields(get_form_value(form_values, "query.crossref_fields"))
    )
    return selected_sources


def is_structure_download_source_selected(form_values: Mapping[str, object], source: str) -> bool:
    """Return whether a canonical structure source is selected for enrichment."""
    return source in selected_enrichment_source_keys(form_values)


def can_enable_structure_download(form_values: Mapping[str, object], source: str) -> bool:
    """Return whether a structure-download flag may serialize as true."""
    return (
        is_enrichment_workflow_compatible(form_values)
        and parse_bool(get_form_value(form_values, "execution.enrich"))
        and is_structure_download_source_selected(form_values, source)
    )


def has_unsupported_enrichment_sources(value: object) -> bool:
    """Return whether cross-reference fields include values outside GUI source choices."""
    fields = parse_csv_list(value)
    if not fields:
        return False
    known_keys = {key.casefold() for key in get_enrichment_source_options().values()}
    return any(field.casefold() not in known_keys for field in fields)


def crossref_fields_from_enrichment_sources(
    sources: object,
    *,
    existing_crossref_fields: object = None,
    preserve_known_existing: bool = True,
) -> str:
    """Return cross-reference field text synchronized with GUI source selections."""
    selected_sources = normalize_enrichment_sources(sources)
    fields = list(selected_sources)
    for field in parse_csv_list(existing_crossref_fields):
        if field in fields:
            continue
        mapped_sources = enrichment_sources_from_crossref_fields([field])
        if mapped_sources and (
            not preserve_known_existing or any(source in selected_sources for source in mapped_sources)
        ):
            continue
        fields.append(field)
    return ", ".join(fields)


def crossref_fields_without_selectable_sources(value: object) -> str:
    """Return cross-reference fields after removing GUI-selectable enrichment sources."""
    fields = [
        field for field in parse_csv_list(value) if not enrichment_sources_from_crossref_fields([field])
    ]
    return ", ".join(fields)


def return_fields_for_yaml(form_values: Mapping[str, object]) -> str:
    """Resolve GUI return-field selector state to the canonical query.fields text."""
    explicit_fields = csv_text_from_value(get_form_value(form_values, "query.fields"))
    if explicit_fields:
        return explicit_fields
    if has_form_value(form_values, "query.return_field_selections") or has_form_value(
        form_values, "query.return_field_custom"
    ):
        return return_fields_from_selection(
            get_form_value(form_values, "query.return_field_selections"),
            get_form_value(form_values, "query.return_field_custom"),
        )
    return explicit_fields


def get_effective_uniprot_return_field_text(
    fields: object,
    crossref_fields: object = None,
) -> str:
    """Return comma-separated UniProt fields after default and enrichment-field resolution."""
    return ", ".join(get_effective_uniprot_return_fields(fields, crossref_fields))


def get_required_uniprot_return_field_text(crossref_fields: object) -> str:
    """Return comma-separated UniProt fields required by enrichment selections."""
    return ", ".join(get_required_uniprot_fields_for_enrichment(crossref_fields))


def is_enrichment_workflow_compatible(form_values: Mapping[str, object]) -> bool:
    """Return whether protein cross-reference enrichment can execute for this workflow."""
    modality = normalize_labeled_value(
        get_form_value(form_values, "dataset.modality"),
        MODALITY_LABEL_TO_VALUE,
    )
    interaction_type = normalize_labeled_value(
        get_form_value(form_values, "dataset.interaction_type"),
        INTERACTION_TYPE_LABEL_TO_VALUE,
    )
    return modality == "protein" and interaction_type is None


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
    workflow_mode = normalize_labeled_value(
        get_form_value(form_values, "dataset.mode"),
        WORKFLOW_MODE_LABEL_TO_VALUE,
    )
    if workflow_mode == "query_composition":
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
        composition = build_query_composition_metadata(
            get_form_value(form_values, "query.composition.entries"),
            modality=modality,
            interaction_type=interaction_type,
        )
        query: dict[str, object] = {
            "value": build_query_composition_value(composition),
            "include_isoform": parse_bool(get_form_value(form_values, "query.include_isoform")),
        }
    else:
        query = {
            "value": resolve_query_value_from_form(form_values),
            "include_isoform": parse_bool(get_form_value(form_values, "query.include_isoform")),
        }
    add_optional_list(query, "fields", return_fields_for_yaml(form_values))
    crossref_fields = get_form_value(form_values, "query.crossref_fields")
    enrichment_compatible = is_enrichment_workflow_compatible(form_values)
    if (
        enrichment_compatible
        and parse_bool(get_form_value(form_values, "execution.enrich"))
        and has_form_value(form_values, "execution.enrichment_sources")
    ):
        crossref_fields = crossref_fields_from_enrichment_sources(
            get_form_value(form_values, "execution.enrichment_sources"),
            existing_crossref_fields=crossref_fields,
        )
    elif not enrichment_compatible and not parse_bool(
        form_values.get(LOADED_INCOMPATIBLE_ENRICHMENT_PASSTHROUGH_FORM_KEY)
    ):
        crossref_fields = crossref_fields_without_selectable_sources(crossref_fields)
    add_optional_list(query, "crossref_fields", crossref_fields)
    cleaned_query = cast("dict[str, object]", remove_empty_values(query))
    if workflow_mode == "query_composition":
        cleaned_query["composition"] = composition
    else:
        builder_metadata = build_query_builder_metadata_from_form(form_values)
        if builder_metadata is not None:
            cleaned_query["builder"] = builder_metadata
    return cleaned_query


def build_execution_section(form_values: Mapping[str, object]) -> dict[str, object]:
    """Build the workflow execution section."""
    download_alphafold_structures = can_enable_structure_download(form_values, "alphafold") and parse_bool(
        get_form_value(form_values, "execution.download_alphafold_structures")
    )
    download_pdb_structures = can_enable_structure_download(form_values, "pdb") and parse_bool(
        get_form_value(form_values, "execution.download_pdb_structures")
    )
    execution: dict[str, object] = {
        "enrich": is_enrichment_workflow_compatible(form_values)
        and parse_bool(get_form_value(form_values, "execution.enrich")),
        "download_alphafold_structures": download_alphafold_structures,
        "download_pdb_structures": download_pdb_structures,
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
    preserved = form_values.get(PRESERVED_SECTIONS_FORM_KEY)
    if isinstance(preserved, Mapping) and preserved:
        merge_preserved_workflow_sections(descriptor, preserved)
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
