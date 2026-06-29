"""Shared ChEBI query catalog for compound query-builder foundations."""

from __future__ import annotations

from dataclasses import dataclass

ENTITY_SEARCH_MODEL = "advanced_search"
ONTOLOGY_SEARCH_MODEL = "ontology_search"
STRUCTURE_SEARCH_MODEL = "structure_search"


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
    supports_range: bool = False
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


def make_chebi_field(
    *,
    key: str,
    label: str,
    description: str,
    placeholder: str,
    examples: tuple[str, ...],
    supported_operators: tuple[str, ...],
    resolver_kind: str,
    supports_range: bool = False,
    query_builder_visible: bool = True,
) -> ChEBIQueryFieldCatalogEntry:
    """Create one ChEBI field catalog entry."""
    return ChEBIQueryFieldCatalogEntry(
        key=key,
        label=label,
        description=description,
        placeholder=placeholder,
        examples=examples,
        supported_operators=supported_operators,
        resolver_kind=resolver_kind,
        supports_range=supports_range,
        query_builder_visible=query_builder_visible,
    )


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


def get_chebi_query_resource_catalog() -> dict[str, ChEBIQueryResourceCatalogEntry]:
    """Return the first-pass ChEBI query resource catalog."""
    resources = [
        build_chebi_resource(
            key="entity",
            label="ChEBI entity",
            description="Chemical entity lookup and search fields for ChEBI.",
            query_model=ENTITY_SEARCH_MODEL,
            fields=(
                make_chebi_field(
                    key="chebi_id",
                    label="ChEBI ID",
                    description="Native ChEBI identifier.",
                    placeholder="CHEBI:15377",
                    examples=("CHEBI:15377",),
                    supported_operators=("exact",),
                    resolver_kind="chebi_id",
                ),
                make_chebi_field(
                    key="name",
                    label="Name",
                    description="ChEBI name or text search term.",
                    placeholder="caffeine",
                    examples=("caffeine", "water"),
                    supported_operators=("contains", "exact"),
                    resolver_kind="text_search",
                ),
                make_chebi_field(
                    key="formula",
                    label="Formula",
                    description="Molecular formula.",
                    placeholder="C8H10N4O2",
                    examples=("C8H10N4O2", "H2O"),
                    supported_operators=("exact",),
                    resolver_kind="formula",
                ),
                make_chebi_field(
                    key="average_mass",
                    label="Average mass",
                    description="Average molecular mass range.",
                    placeholder="194.0,195.0",
                    examples=("194.0,195.0",),
                    supported_operators=("range",),
                    resolver_kind="mass_range",
                    supports_range=True,
                ),
                make_chebi_field(
                    key="monoisotopic_mass",
                    label="Monoisotopic mass",
                    description="Monoisotopic molecular mass range.",
                    placeholder="194.0,195.0",
                    examples=("194.0,195.0",),
                    supported_operators=("range",),
                    resolver_kind="mass_range",
                    supports_range=True,
                ),
                make_chebi_field(
                    key="charge",
                    label="Charge",
                    description="Formal charge range.",
                    placeholder="-1,1",
                    examples=("-1,1", "0,1"),
                    supported_operators=("range",),
                    resolver_kind="charge_range",
                    supports_range=True,
                ),
                make_chebi_field(
                    key="database_xref",
                    label="Database cross-reference",
                    description="External database cross-reference source.",
                    placeholder="ChEMBL",
                    examples=("ChEMBL", "PubChem"),
                    supported_operators=("exact",),
                    resolver_kind="database_xref",
                ),
                make_chebi_field(
                    key="star",
                    label="Star rating",
                    description="ChEBI curation star rating.",
                    placeholder="3",
                    examples=("3",),
                    supported_operators=("exact",),
                    resolver_kind="star_rating",
                ),
            ),
        ),
        build_chebi_resource(
            key="ontology",
            label="ChEBI ontology",
            description="Ontology relation and term search fields for ChEBI.",
            query_model=ONTOLOGY_SEARCH_MODEL,
            fields=(
                make_chebi_field(
                    key="ontology_relation",
                    label="Ontology relation",
                    description="Ontology relation type.",
                    placeholder="has_role",
                    examples=("has_role", "is_a"),
                    supported_operators=("exact",),
                    resolver_kind="ontology_relation",
                ),
                make_chebi_field(
                    key="ontology_term",
                    label="Ontology term",
                    description="Ontology term paired with a relation.",
                    placeholder="metabolite",
                    examples=("metabolite", "cofactor"),
                    supported_operators=("exact", "contains"),
                    resolver_kind="ontology_term",
                ),
            ),
        ),
        build_chebi_resource(
            key="structure",
            label="ChEBI structure",
            description="Structure query generation for ChEBI.",
            query_model=STRUCTURE_SEARCH_MODEL,
            fields=(
                make_chebi_field(
                    key="connectivity",
                    label="Connectivity",
                    description="Structure connectivity key or pattern.",
                    placeholder="BSYNRYMUTXBXSQ",
                    examples=("BSYNRYMUTXBXSQ",),
                    supported_operators=("connectivity",),
                    resolver_kind="connectivity",
                ),
                make_chebi_field(
                    key="substructure",
                    label="Substructure",
                    description="Substructure pattern.",
                    placeholder="c1ccccc1",
                    examples=("c1ccccc1",),
                    supported_operators=("substructure",),
                    resolver_kind="substructure",
                ),
                make_chebi_field(
                    key="similarity",
                    label="Similarity",
                    description="Structure similarity search input.",
                    placeholder="c1ccccc1",
                    examples=("c1ccccc1",),
                    supported_operators=("similarity",),
                    resolver_kind="similarity",
                ),
            ),
        ),
    ]
    return {resource.key: resource for resource in resources}


def get_chebi_query_builder_resource_catalog() -> dict[str, ChEBIQueryResourceCatalogEntry]:
    """Return ChEBI resources enabled for GUI query builders."""
    return {
        key: resource
        for key, resource in get_chebi_query_resource_catalog().items()
        if resource.query_builder_visible
    }


def get_chebi_query_builder_field_catalog(
    resource_key: str,
) -> dict[str, ChEBIQueryFieldCatalogEntry]:
    """Return visible ChEBI fields for one query-builder resource."""
    resources = get_chebi_query_builder_resource_catalog()
    if resource_key not in resources:
        msg = f"Unsupported ChEBI query resource '{resource_key}'."
        raise ValueError(msg)
    return {
        key: field for key, field in resources[resource_key].fields.items() if field.query_builder_visible
    }
