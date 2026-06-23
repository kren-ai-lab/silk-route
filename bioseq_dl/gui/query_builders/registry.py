"""Registry for database-specific query builder foundations."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING

from bioseq_dl.core.workflow.chembl_query_catalog import get_chembl_query_builder_field_catalog
from bioseq_dl.core.workflow.query_field_catalog import get_uniprot_query_builder_field_catalog
from bioseq_dl.gui.query_builders.chembl import (
    build_chembl_friendly_query,
    build_chembl_interpreted_query,
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

