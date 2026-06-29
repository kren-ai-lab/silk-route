"""Shared PubChem query catalog for compound query-builder foundations."""

from __future__ import annotations

from dataclasses import dataclass

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


def make_pubchem_field(
    *,
    key: str,
    label: str,
    description: str,
    placeholder: str,
    examples: tuple[str, ...],
    supported_modes: tuple[str, ...],
    native_input_kind: str,
    resolver_kind: str,
    query_builder_visible: bool = True,
    notes: str | None = None,
) -> PubChemQueryFieldCatalogEntry:
    """Create one PubChem field catalog entry."""
    return PubChemQueryFieldCatalogEntry(
        key=key,
        label=label,
        description=description,
        placeholder=placeholder,
        examples=examples,
        supported_modes=supported_modes,
        native_input_kind=native_input_kind,
        resolver_kind=resolver_kind,
        query_builder_visible=query_builder_visible,
        notes=notes,
    )


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


def get_pubchem_query_resource_catalog() -> dict[str, PubChemQueryResourceCatalogEntry]:
    """Return the first-pass PubChem query resource catalog."""
    resources = [
        build_pubchem_resource(
            key="compound",
            label="PubChem compound",
            description="Compound lookup by native PubChem CID, name, InChI, or InChIKey.",
            query_model=COMPOUND_LOOKUP_MODEL,
            fields=(
                make_pubchem_field(
                    key="cid",
                    label="CID",
                    description="PubChem compound identifier.",
                    placeholder="2244",
                    examples=("2244", "5793"),
                    supported_modes=("exact",),
                    native_input_kind="cid",
                    resolver_kind="compound_identifier",
                    notes="CID is the primary PubChem compound key used by this builder.",
                ),
                make_pubchem_field(
                    key="name",
                    label="Name or synonym",
                    description="Compound name or synonym resolved by PubChem.",
                    placeholder="glucose",
                    examples=("glucose", "aspirin"),
                    supported_modes=("lookup",),
                    native_input_kind="text",
                    resolver_kind="name_lookup",
                ),
                make_pubchem_field(
                    key="inchikey",
                    label="InChIKey",
                    description="Standard InChIKey used for compound lookup.",
                    placeholder="BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
                    examples=("BSYNRYMUTXBXSQ-UHFFFAOYSA-N",),
                    supported_modes=("exact",),
                    native_input_kind="inchikey",
                    resolver_kind="inchikey_lookup",
                ),
                make_pubchem_field(
                    key="inchi",
                    label="InChI",
                    description="InChI string used for compound lookup.",
                    placeholder="InChI=1S/C6H12O6/c7-1-2-3-4-5-6",
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
            description="Structure lookup and search query generation for PubChem.",
            query_model=STRUCTURE_SEARCH_MODEL,
            fields=(
                make_pubchem_field(
                    key="smiles_identity",
                    label="SMILES identity",
                    description="Canonical or isomeric SMILES identity lookup.",
                    placeholder="CC(=O)Oc1ccccc1C(=O)O",
                    examples=("CC(=O)Oc1ccccc1C(=O)O",),
                    supported_modes=("identity",),
                    native_input_kind="smiles",
                    resolver_kind="smiles_identity",
                ),
                make_pubchem_field(
                    key="smiles_substructure",
                    label="SMILES substructure",
                    description="SMILES pattern used for substructure search.",
                    placeholder="c1ccccc1",
                    examples=("c1ccccc1",),
                    supported_modes=("substructure",),
                    native_input_kind="smiles",
                    resolver_kind="smiles_substructure",
                ),
                make_pubchem_field(
                    key="similarity_2d",
                    label="2-D similarity",
                    description="2-D similarity search using a reference PubChem CID and threshold.",
                    placeholder="446157",
                    examples=("446157",),
                    supported_modes=("similarity_2d",),
                    native_input_kind="cid",
                    resolver_kind="cid_similarity_2d",
                    notes=(
                        "The GUI field maps to the executable similarity_2d_cid parameter. "
                        "Threshold is an integer percentage from 0 to 100."
                    ),
                ),
            ),
        ),
    ]
    return {resource.key: resource for resource in resources}


def get_pubchem_query_builder_resource_catalog() -> dict[str, PubChemQueryResourceCatalogEntry]:
    """Return PubChem resources enabled for GUI query builders."""
    return {
        key: resource
        for key, resource in get_pubchem_query_resource_catalog().items()
        if resource.query_builder_visible
    }


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
