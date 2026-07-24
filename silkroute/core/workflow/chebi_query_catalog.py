"""Shared ChEBI query catalog for executable compound workflow query planning."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

ENTITY_QUERY_MODEL = "entity_query"


@dataclass(frozen=True)
class ChEBIQueryFieldCatalogEntry:
    """Metadata for one ChEBI query-builder field."""

    key: str
    label: str
    description: str
    placeholder: str
    examples: tuple[str, ...]
    supported_operators: tuple[str, ...]
    resolver_kind: str
    query_builder_visible: bool = True


@dataclass(frozen=True)
class ChEBIQueryResourceCatalogEntry:
    """Metadata for one ChEBI query-builder resource."""

    key: str
    label: str
    description: str
    query_model: str
    fields: dict[str, ChEBIQueryFieldCatalogEntry]
    query_builder_visible: bool = True


def build_chebi_resource(
    *,
    key: str,
    label: str,
    description: str,
    query_model: str,
    fields: tuple[ChEBIQueryFieldCatalogEntry, ...],
    query_builder_visible: bool = True,
) -> ChEBIQueryResourceCatalogEntry:
    """Create one ChEBI resource catalog entry."""
    return ChEBIQueryResourceCatalogEntry(
        key=key,
        label=label,
        description=description,
        query_model=query_model,
        fields={field.key: field for field in fields},
        query_builder_visible=query_builder_visible,
    )


@cache
def get_chebi_query_resource_catalog() -> dict[str, ChEBIQueryResourceCatalogEntry]:
    """Return the executable ChEBI query resource catalog."""
    resources = [
        build_chebi_resource(
            key="entity",
            label="ChEBI entity",
            description="Executable ChEBI entity lookup and text search fields.",
            query_model=ENTITY_QUERY_MODEL,
            fields=(
                ChEBIQueryFieldCatalogEntry(
                    key="chebi_id",
                    label="ChEBI ID",
                    description="Native ChEBI identifier.",
                    placeholder="CHEBI:15377",
                    examples=("CHEBI:15377",),
                    supported_operators=("exact",),
                    resolver_kind="chebi_id",
                ),
                ChEBIQueryFieldCatalogEntry(
                    key="name",
                    label="Name",
                    description="ChEBI name searched and filtered as an exact entity name.",
                    placeholder="caffeine",
                    examples=("caffeine", "water"),
                    supported_operators=("exact",),
                    resolver_kind="exact_name_search",
                ),
                ChEBIQueryFieldCatalogEntry(
                    key="name_contains",
                    label="Name contains",
                    description="ChEBI name text search.",
                    placeholder="caffeine",
                    examples=("caffeine", "glucose"),
                    supported_operators=("contains",),
                    resolver_kind="name_contains_search",
                ),
            ),
        )
    ]
    return {resource.key: resource for resource in resources}


@cache
def get_chebi_query_builder_resource_catalog() -> dict[str, ChEBIQueryResourceCatalogEntry]:
    """Return ChEBI resources enabled for query-builder foundations."""
    return {
        key: resource
        for key, resource in get_chebi_query_resource_catalog().items()
        if resource.query_builder_visible
    }


@cache
def get_chebi_query_builder_field_catalog(resource_key: str) -> dict[str, ChEBIQueryFieldCatalogEntry]:
    """Return visible ChEBI fields for one query-builder resource."""
    resources = get_chebi_query_builder_resource_catalog()
    if resource_key not in resources:
        msg = f"Unsupported ChEBI query resource '{resource_key}'."
        raise ValueError(msg)
    return {
        key: field for key, field in resources[resource_key].fields.items() if field.query_builder_visible
    }
