"""Registry for database-specific query builder foundations."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING

from bioseq_dl.core.workflow.chebi_query_catalog import get_chebi_query_builder_field_catalog
from bioseq_dl.core.workflow.chembl_query_catalog import get_chembl_query_builder_field_catalog
from bioseq_dl.core.workflow.pubchem_query_catalog import get_pubchem_query_builder_field_catalog
from bioseq_dl.core.workflow.query_field_catalog import get_uniprot_query_builder_field_catalog
from bioseq_dl.gui.query_builders.chebi import (
    build_chebi_friendly_query,
    build_chebi_interpreted_query,
)
from bioseq_dl.gui.query_builders.chembl import (
    build_chembl_friendly_query,
    build_chembl_ic50_friendly_query,
    build_chembl_ic50_interpreted_query,
    build_chembl_interpreted_query,
    get_chembl_ic50_query_builder_field_catalog,
)
from bioseq_dl.gui.query_builders.pubchem import (
    build_pubchem_friendly_query,
    build_pubchem_interpreted_query,
)
from bioseq_dl.gui.query_builders.uniprot import (
    build_uniprot_friendly_query,
    build_uniprot_interpreted_query,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping


@dataclass(frozen=True)
class QueryBuilderSpec:
    """Metadata and hooks for one database/resource-specific query builder."""

    key: str
    label: str
    description: str
    database: str
    builder_type: str
    build_friendly_query: Callable[..., str]
    build_interpreted_query: Callable[..., str]
    get_field_catalog: Callable[[], Mapping[str, object]]
    compatible_modalities: tuple[str, ...]
    compatible_interaction_types: tuple[str | None, ...] = (None,)


def get_query_builder_specs() -> dict[str, QueryBuilderSpec]:
    """Return all registered query-builder specs."""
    specs = [
        QueryBuilderSpec(
            key="uniprot",
            label="UniProt query builder",
            description="UniProt field/boolean builder with match modes.",
            database="uniprot",
            builder_type="field_boolean",
            build_friendly_query=build_uniprot_friendly_query,
            build_interpreted_query=build_uniprot_interpreted_query,
            get_field_catalog=get_uniprot_query_builder_field_catalog,
            compatible_modalities=("protein", "interaction"),
            compatible_interaction_types=(None, "protein-protein"),
        ),
        QueryBuilderSpec(
            key="chembl_target",
            label="ChEMBL target filter builder",
            description="ChEMBL target filter-list builder.",
            database="chembl",
            builder_type="resource_filter",
            build_friendly_query=build_chembl_friendly_query,
            build_interpreted_query=build_chembl_interpreted_query,
            get_field_catalog=partial(get_chembl_query_builder_field_catalog, "target"),
            compatible_modalities=("interaction",),
            compatible_interaction_types=("protein-ligand",),
        ),
        QueryBuilderSpec(
            key="chembl_assay",
            label="ChEMBL assay filter builder",
            description="ChEMBL assay filter-list builder.",
            database="chembl",
            builder_type="resource_filter",
            build_friendly_query=build_chembl_friendly_query,
            build_interpreted_query=build_chembl_interpreted_query,
            get_field_catalog=partial(get_chembl_query_builder_field_catalog, "assay"),
            compatible_modalities=("interaction",),
            compatible_interaction_types=("protein-ligand",),
        ),
        QueryBuilderSpec(
            key="chembl_cell_line",
            label="ChEMBL cell line filter builder",
            description="ChEMBL cell line filter-list builder.",
            database="chembl",
            builder_type="resource_filter",
            build_friendly_query=build_chembl_friendly_query,
            build_interpreted_query=build_chembl_interpreted_query,
            get_field_catalog=partial(get_chembl_query_builder_field_catalog, "cell_line"),
            # Intentionally not GUI-selectable: usable via the parser/YAML map, but kept
            # out of the builder menu (empty compatibility tuples).
            compatible_modalities=(),
            compatible_interaction_types=(),
        ),
        QueryBuilderSpec(
            key="chembl_molecule",
            label="ChEMBL molecule filter builder",
            description="ChEMBL molecule filter-list builder.",
            database="chembl",
            builder_type="resource_filter",
            build_friendly_query=build_chembl_friendly_query,
            build_interpreted_query=build_chembl_interpreted_query,
            get_field_catalog=partial(get_chembl_query_builder_field_catalog, "molecule"),
            compatible_modalities=("compound",),
            compatible_interaction_types=(None,),
        ),
        QueryBuilderSpec(
            key="chembl_activity",
            label="ChEMBL activity parameter builder",
            description="ChEMBL activity flat-parameter builder.",
            database="chembl",
            builder_type="flat_parameters",
            build_friendly_query=build_chembl_friendly_query,
            build_interpreted_query=build_chembl_interpreted_query,
            get_field_catalog=partial(get_chembl_query_builder_field_catalog, "activity"),
            compatible_modalities=("compound", "interaction"),
            compatible_interaction_types=(None, "protein-ligand"),
        ),
        QueryBuilderSpec(
            key="chembl_ic50",
            label="ChEMBL IC50 activity",
            description="ChEMBL IC50 activity macro builder with required standard unit.",
            database="chembl",
            builder_type="ic50_activity",
            build_friendly_query=build_chembl_ic50_friendly_query,
            build_interpreted_query=build_chembl_ic50_interpreted_query,
            get_field_catalog=get_chembl_ic50_query_builder_field_catalog,
            compatible_modalities=("compound",),
            compatible_interaction_types=(None,),
        ),
        QueryBuilderSpec(
            key="pubchem_compound",
            label="PubChem compound lookup builder",
            description="PubChem CID, name, InChI, and InChIKey lookup builder.",
            database="pubchem",
            builder_type="single_lookup",
            build_friendly_query=build_pubchem_friendly_query,
            build_interpreted_query=build_pubchem_interpreted_query,
            get_field_catalog=partial(get_pubchem_query_builder_field_catalog, "compound"),
            compatible_modalities=("compound",),
            compatible_interaction_types=(None,),
        ),
        QueryBuilderSpec(
            key="pubchem_structure",
            label="PubChem structure search builder",
            description="PubChem SMILES identity, substructure, and 2-D similarity builder.",
            database="pubchem",
            builder_type="structure_search",
            build_friendly_query=build_pubchem_friendly_query,
            build_interpreted_query=build_pubchem_interpreted_query,
            get_field_catalog=partial(get_pubchem_query_builder_field_catalog, "structure"),
            compatible_modalities=("compound",),
            compatible_interaction_types=(None,),
        ),
        QueryBuilderSpec(
            key="chebi_entity",
            label="ChEBI entity search builder",
            description="ChEBI ID, exact name, and name-contains entity builder.",
            database="chebi",
            builder_type="single_lookup",
            build_friendly_query=build_chebi_friendly_query,
            build_interpreted_query=build_chebi_interpreted_query,
            get_field_catalog=partial(get_chebi_query_builder_field_catalog, "entity"),
            compatible_modalities=("compound",),
            compatible_interaction_types=(None,),
        ),
    ]
    return {spec.key: spec for spec in specs}


def get_query_builder_spec(key: str) -> QueryBuilderSpec:
    """Return one query-builder spec by key."""
    specs = get_query_builder_specs()
    if key not in specs:
        msg = f"Unknown query builder '{key}'."
        raise ValueError(msg)
    return specs[key]


def get_query_builder_choices() -> dict[str, str]:
    """Return query-builder choices as key-to-label mappings."""
    return {key: spec.label for key, spec in get_query_builder_specs().items()}


def is_query_builder_compatible(
    spec: QueryBuilderSpec,
    modality: str,
    interaction_type: str | None,
) -> bool:
    """Return whether a builder is compatible with selected dataset settings."""
    normalized_modality = str(modality or "").strip()
    normalized_interaction_type = interaction_type or None
    if normalized_modality not in spec.compatible_modalities:
        return False
    if normalized_modality != "interaction":
        return None in spec.compatible_interaction_types
    if normalized_interaction_type is None:
        return False
    return normalized_interaction_type in spec.compatible_interaction_types


def get_compatible_query_builder_specs(
    modality: str,
    interaction_type: str | None,
) -> tuple[QueryBuilderSpec, ...]:
    """Return query builder specs compatible with the selected dataset settings."""
    return tuple(
        spec
        for spec in get_query_builder_specs().values()
        if is_query_builder_compatible(spec, modality, interaction_type)
    )


def get_compatible_query_builder_choices(
    modality: str,
    interaction_type: str | None,
) -> dict[str, str]:
    """Return compatible query-builder choices as key-to-label mappings."""
    return {spec.key: spec.label for spec in get_compatible_query_builder_specs(modality, interaction_type)}
