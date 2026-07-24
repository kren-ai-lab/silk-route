"""Shared PubChem query catalog for compound workflow query planning."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

COMPOUND_LOOKUP_MODEL = "compound_lookup"
STRUCTURE_SEARCH_MODEL = "structure_search"


@dataclass(frozen=True)
class PubChemQueryFieldCatalogEntry:
    """Metadata for one PubChem query-builder field."""

    key: str
    label: str
    description: str
    placeholder: str
    examples: tuple[str, ...]
    supported_modes: tuple[str, ...]
    native_input_kind: str
    resolver_kind: str
    query_builder_visible: bool = True
    notes: str | None = None


@dataclass(frozen=True)
class PubChemQueryResourceCatalogEntry:
    """Metadata for one PubChem query-builder resource."""

    key: str
    label: str
    description: str
    query_model: str
    fields: dict[str, PubChemQueryFieldCatalogEntry]
    query_builder_visible: bool = True


def build_pubchem_resource(
    *,
    key: str,
    label: str,
    description: str,
    query_model: str,
    fields: tuple[PubChemQueryFieldCatalogEntry, ...],
    query_builder_visible: bool = True,
) -> PubChemQueryResourceCatalogEntry:
    """Create one PubChem resource catalog entry."""
    return PubChemQueryResourceCatalogEntry(
        key=key,
        label=label,
        description=description,
        query_model=query_model,
        fields={field.key: field for field in fields},
        query_builder_visible=query_builder_visible,
    )


@cache
def get_pubchem_query_resource_catalog() -> dict[str, PubChemQueryResourceCatalogEntry]:
    """Return the first-pass PubChem query resource catalog."""
    resources = [
        build_pubchem_resource(
            key="compound",
            label="PubChem compound",
            description="Compound lookup by PubChem CID, name, InChI, or InChIKey.",
            query_model=COMPOUND_LOOKUP_MODEL,
            fields=(
                PubChemQueryFieldCatalogEntry(
                    key="cid",
                    label="CID",
                    description="PubChem compound identifier.",
                    placeholder="2244",
                    examples=("2244", "5793"),
                    supported_modes=("exact",),
                    native_input_kind="cid",
                    resolver_kind="compound_identifier",
                ),
                PubChemQueryFieldCatalogEntry(
                    key="name",
                    label="Name",
                    description="Compound name or synonym resolved by PubChem.",
                    placeholder="glucose",
                    examples=("glucose", "aspirin"),
                    supported_modes=("lookup",),
                    native_input_kind="text",
                    resolver_kind="name_lookup",
                ),
                PubChemQueryFieldCatalogEntry(
                    key="inchikey",
                    label="InChIKey",
                    description="Standard InChIKey used for compound lookup.",
                    placeholder="BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
                    examples=("BSYNRYMUTXBXSQ-UHFFFAOYSA-N",),
                    supported_modes=("exact",),
                    native_input_kind="inchikey",
                    resolver_kind="inchikey_lookup",
                ),
                PubChemQueryFieldCatalogEntry(
                    key="inchi",
                    label="InChI",
                    description="InChI string used for compound lookup.",
                    placeholder="InChI=1S/H2O/h1H2",
                    examples=("InChI=1S/H2O/h1H2",),
                    supported_modes=("exact",),
                    native_input_kind="inchi",
                    resolver_kind="inchi_lookup",
                ),
            ),
        ),
        build_pubchem_resource(
            key="structure",
            label="PubChem structure",
            description="Executable PubChem structure lookup and search fields.",
            query_model=STRUCTURE_SEARCH_MODEL,
            fields=(
                PubChemQueryFieldCatalogEntry(
                    key="smiles_identity",
                    label="SMILES identity",
                    description="SMILES identity lookup.",
                    placeholder="CC(=O)Oc1ccccc1C(=O)O",
                    examples=("CC(=O)Oc1ccccc1C(=O)O",),
                    supported_modes=("identity",),
                    native_input_kind="smiles",
                    resolver_kind="smiles_identity",
                ),
                PubChemQueryFieldCatalogEntry(
                    key="smiles_substructure",
                    label="SMILES substructure",
                    description="SMILES pattern used for substructure search.",
                    placeholder="c1ccccc1",
                    examples=("c1ccccc1",),
                    supported_modes=("substructure",),
                    native_input_kind="smiles",
                    resolver_kind="smiles_substructure",
                ),
                PubChemQueryFieldCatalogEntry(
                    key="similarity_2d_cid",
                    label="2-D similarity CID",
                    description="2-D similarity search using a PubChem reference CID.",
                    placeholder="446157",
                    examples=("446157",),
                    supported_modes=("similarity_2d",),
                    native_input_kind="cid",
                    resolver_kind="cid_similarity_2d",
                    notes="Threshold is an integer percentage from 0 to 100.",
                ),
            ),
        ),
    ]
    return {resource.key: resource for resource in resources}


@cache
def get_pubchem_query_builder_resource_catalog() -> dict[str, PubChemQueryResourceCatalogEntry]:
    """Return PubChem resources enabled for query-builder foundations."""
    return {
        key: resource
        for key, resource in get_pubchem_query_resource_catalog().items()
        if resource.query_builder_visible
    }


@cache
def get_pubchem_query_builder_field_catalog(
    resource_key: str,
) -> dict[str, PubChemQueryFieldCatalogEntry]:
    """Return visible PubChem fields for one query-builder resource."""
    resources = get_pubchem_query_builder_resource_catalog()
    if resource_key not in resources:
        msg = f"Unsupported PubChem query resource '{resource_key}'."
        raise ValueError(msg)
    return {
        key: field for key, field in resources[resource_key].fields.items() if field.query_builder_visible
    }
