"""Shared ChEMBL query catalog for query-builder foundations."""

from __future__ import annotations

from dataclasses import dataclass

FILTER_LIST_MODEL = "filter_list"
FLAT_PARAMETERS_MODEL = "flat_parameters"
SINGLE_STRUCTURE_QUERY_MODEL = "single_structure_query"

OPERATOR_SUFFIXES = {
    "exact": "",
    "iexact": "__iexact",
    "icontains": "__icontains",
    "contains": "__contains",
    "istartswith": "__istartswith",
    "startswith": "__startswith",
    "in": "__in",
    "gt": "__gt",
    "gte": "__gte",
    "lt": "__lt",
    "lte": "__lte",
    "range": "__range",
}


@dataclass(frozen=True)
class ChEMBLQueryFieldCatalogEntry:
    """Metadata for one ChEMBL query-builder field."""

    key: str
    label: str
    description: str
    placeholder: str
    examples: tuple[str, ...]
    allowed_operators: tuple[str, ...]
    value_type: str
    query_builder_visible: bool = True


@dataclass(frozen=True)
class ChEMBLQueryResourceCatalogEntry:
    """Metadata for one ChEMBL query-builder resource."""

    key: str
    label: str
    description: str
    query_model: str
    fields: dict[str, ChEMBLQueryFieldCatalogEntry]
    query_builder_visible: bool = True


def make_chembl_field(
    *,
    key: str,
    label: str,
    description: str,
    placeholder: str,
    examples: tuple[str, ...],
    allowed_operators: tuple[str, ...],
    value_type: str = "string",
    query_builder_visible: bool = True,
) -> ChEMBLQueryFieldCatalogEntry:
    """Create one ChEMBL field catalog entry."""
    return ChEMBLQueryFieldCatalogEntry(
        key=key,
        label=label,
        description=description,
        placeholder=placeholder,
        examples=examples,
        allowed_operators=allowed_operators,
        value_type=value_type,
        query_builder_visible=query_builder_visible,
    )


def build_chembl_resource(
    *,
    key: str,
    label: str,
    description: str,
    query_model: str,
    fields: tuple[ChEMBLQueryFieldCatalogEntry, ...] = (),
    query_builder_visible: bool = True,
) -> ChEMBLQueryResourceCatalogEntry:
    """Create one ChEMBL resource catalog entry."""
    return ChEMBLQueryResourceCatalogEntry(
        key=key,
        label=label,
        description=description,
        query_model=query_model,
        fields={field.key: field for field in fields},
        query_builder_visible=query_builder_visible,
    )


def get_chembl_query_resource_catalog() -> dict[str, ChEMBLQueryResourceCatalogEntry]:
    """Return the conservative ChEMBL query resource catalog."""
    text_operators = ("iexact", "icontains", "istartswith", "exact", "contains", "startswith", "in")
    filter_text_operators = ("iexact", "icontains", "istartswith", "exact", "contains", "in")
    numeric_operators = ("exact", "in", "gt", "gte", "lt", "lte", "range")
    activity_text_operators = ("exact", "in", "contains")

    resources = [
        build_chembl_resource(
            key="target",
            label="ChEMBL target",
            description="Protein and non-protein target metadata queried with ChEMBL filters.",
            query_model=FILTER_LIST_MODEL,
            fields=(
                make_chembl_field(
                    key="type",
                    label="Target type",
                    description="Target type, such as protein.",
                    placeholder="protein",
                    examples=("protein", "single protein"),
                    allowed_operators=text_operators,
                    value_type="enum_like",
                ),
                make_chembl_field(
                    key="gene_symbol",
                    label="Gene symbol",
                    description="Target gene symbol.",
                    placeholder="EGFR",
                    examples=("EGFR", "BRCA1"),
                    allowed_operators=text_operators,
                ),
                make_chembl_field(
                    key="pref_name",
                    label="Preferred name",
                    description="Preferred target name.",
                    placeholder="epidermal growth factor receptor",
                    examples=("EGFR", "kinase"),
                    allowed_operators=text_operators,
                ),
                make_chembl_field(
                    key="organism",
                    label="Organism",
                    description="Target organism name.",
                    placeholder="Homo sapiens",
                    examples=("Homo sapiens", "Mus musculus"),
                    allowed_operators=text_operators,
                ),
            ),
        ),
        build_chembl_resource(
            key="assay",
            label="ChEMBL assay",
            description="Assay metadata queried with ChEMBL filters.",
            query_model=FILTER_LIST_MODEL,
            fields=(
                make_chembl_field(
                    key="label_type",
                    label="Label type",
                    description="Assay label type.",
                    placeholder="functional",
                    examples=("functional", "binding"),
                    allowed_operators=filter_text_operators,
                    value_type="enum_like",
                ),
                make_chembl_field(
                    key="organism",
                    label="Organism",
                    description="Assay organism.",
                    placeholder="virus",
                    examples=("virus", "Homo sapiens"),
                    allowed_operators=filter_text_operators,
                ),
                make_chembl_field(
                    key="taxonomy_organism",
                    label="Taxonomy organism",
                    description="Assay taxonomy organism.",
                    placeholder="Homo sapiens",
                    examples=("Homo sapiens", "Mus musculus"),
                    allowed_operators=filter_text_operators,
                ),
                make_chembl_field(
                    key="assay_type",
                    label="Assay type",
                    description="ChEMBL assay type.",
                    placeholder="B",
                    examples=("B", "F"),
                    allowed_operators=filter_text_operators,
                    value_type="enum_like",
                ),
                make_chembl_field(
                    key="target_chembl_id",
                    label="Target ChEMBL ID",
                    description="ChEMBL target identifier linked to the assay.",
                    placeholder="CHEMBL1824",
                    examples=("CHEMBL1824", "CHEMBL5169197"),
                    allowed_operators=("exact", "in"),
                    value_type="chembl_id",
                ),
            ),
        ),
        build_chembl_resource(
            key="cell_line",
            label="ChEMBL cell line",
            description="Cell line metadata queried with ChEMBL filters.",
            query_model=FILTER_LIST_MODEL,
            fields=(
                make_chembl_field(
                    key="organism",
                    label="Organism",
                    description="Cell line organism.",
                    placeholder="mus",
                    examples=("mus", "Homo sapiens"),
                    allowed_operators=filter_text_operators,
                ),
                make_chembl_field(
                    key="taxonomy_organism",
                    label="Taxonomy organism",
                    description="Cell line taxonomy organism.",
                    placeholder="Mus musculus",
                    examples=("Mus musculus", "Homo sapiens"),
                    allowed_operators=filter_text_operators,
                ),
                make_chembl_field(
                    key="cell_name",
                    label="Cell name",
                    description="Cell line name.",
                    placeholder="HeLa",
                    examples=("HeLa", "A549"),
                    allowed_operators=filter_text_operators,
                ),
                make_chembl_field(
                    key="cell_chembl_id",
                    label="Cell ChEMBL ID",
                    description="ChEMBL cell line identifier.",
                    placeholder="CHEMBL3307715",
                    examples=("CHEMBL3307715",),
                    allowed_operators=("exact", "in"),
                    value_type="chembl_id",
                ),
            ),
        ),
        build_chembl_resource(
            key="molecule",
            label="ChEMBL molecule",
            description="Molecule metadata queried with ChEMBL filters.",
            query_model=FILTER_LIST_MODEL,
            fields=(
                make_chembl_field(
                    key="name",
                    label="Name",
                    description="Molecule name or synonym.",
                    placeholder="Imatinib",
                    examples=("Imatinib", "aspirin"),
                    allowed_operators=("iexact", "icontains", "exact", "contains", "in"),
                ),
                make_chembl_field(
                    key="molecular_weight",
                    label="Molecular weight",
                    description="Molecular weight filter.",
                    placeholder="80,200",
                    examples=("80,200", "300"),
                    allowed_operators=numeric_operators,
                    value_type="number",
                ),
                make_chembl_field(
                    key="molecule_chembl_id",
                    label="Molecule ChEMBL ID",
                    description="ChEMBL molecule identifier.",
                    placeholder="CHEMBL941",
                    examples=("CHEMBL941", "CHEMBL25"),
                    allowed_operators=("exact", "in"),
                    value_type="chembl_id",
                ),
                make_chembl_field(
                    key="molecule_structures__canonical_smiles__connectivity",
                    label="Canonical SMILES connectivity",
                    description="Canonical SMILES connectivity string.",
                    placeholder="c1ccccc1N",
                    examples=("c1ccccc1N", "C1=CC=CC=C1"),
                    allowed_operators=("iexact", "icontains", "exact", "contains", "in"),
                ),
            ),
        ),
        build_chembl_resource(
            key="activity",
            label="ChEMBL activity",
            description="Activity records queried with flat ChEMBL parameters.",
            query_model=FLAT_PARAMETERS_MODEL,
            fields=(
                make_chembl_field(
                    key="target_chembl_id",
                    label="Target ChEMBL ID",
                    description="Target identifier for activity lookup.",
                    placeholder="CHEMBL5169197",
                    examples=("CHEMBL5169197", "CHEMBL1824"),
                    allowed_operators=("exact", "in"),
                    value_type="chembl_id",
                ),
                make_chembl_field(
                    key="pchembl_value",
                    label="pChEMBL value",
                    description="pChEMBL activity value.",
                    placeholder="5.83",
                    examples=("5.83", "7"),
                    allowed_operators=numeric_operators,
                    value_type="number",
                ),
                make_chembl_field(
                    key="standard_type",
                    label="Standard type",
                    description="Activity standard type, such as IC50.",
                    placeholder="IC50",
                    examples=("IC50", "Ki"),
                    allowed_operators=activity_text_operators,
                    value_type="enum_like",
                ),
                make_chembl_field(
                    key="standard_value",
                    label="Standard value",
                    description="Activity standard value.",
                    placeholder="0,100",
                    examples=("0,100", "50"),
                    allowed_operators=numeric_operators,
                    value_type="number",
                ),
                make_chembl_field(
                    key="standard_units",
                    label="Standard units",
                    description="Activity standard units.",
                    placeholder="nM",
                    examples=("nM", "uM"),
                    allowed_operators=activity_text_operators,
                    value_type="enum_like",
                ),
                make_chembl_field(
                    key="molecule_chembl_id",
                    label="Molecule ChEMBL ID",
                    description="Molecule identifier for activity lookup.",
                    placeholder="CHEMBL941",
                    examples=("CHEMBL941", "CHEMBL25"),
                    allowed_operators=("exact", "in"),
                    value_type="chembl_id",
                ),
                make_chembl_field(
                    key="assay_chembl_id",
                    label="Assay ChEMBL ID",
                    description="Assay identifier for activity lookup.",
                    placeholder="CHEMBL1234567",
                    examples=("CHEMBL1234567",),
                    allowed_operators=("exact", "in"),
                    value_type="chembl_id",
                ),
                make_chembl_field(
                    key="assay_type",
                    label="Assay type",
                    description="Activity assay type.",
                    placeholder="B",
                    examples=("B", "F"),
                    allowed_operators=activity_text_operators,
                    value_type="enum_like",
                ),
                make_chembl_field(
                    key="relationship_type",
                    label="Relationship type",
                    description="Activity relationship type.",
                    placeholder="D",
                    examples=("D", "H"),
                    allowed_operators=activity_text_operators,
                    value_type="enum_like",
                ),
                make_chembl_field(
                    key="target_organism",
                    label="Target organism",
                    description="Target organism for activity records.",
                    placeholder="Homo sapiens",
                    examples=("Homo sapiens", "Mus musculus"),
                    allowed_operators=activity_text_operators,
                ),
            ),
        ),
        build_chembl_resource(
            key="substructure",
            label="ChEMBL substructure",
            description="Future structure-query builder for ChEMBL substructure search.",
            query_model=SINGLE_STRUCTURE_QUERY_MODEL,
            query_builder_visible=False,
        ),
        build_chembl_resource(
            key="similarity",
            label="ChEMBL similarity",
            description="Future structure-query builder for ChEMBL similarity search.",
            query_model=SINGLE_STRUCTURE_QUERY_MODEL,
            query_builder_visible=False,
        ),
    ]
    return {resource.key: resource for resource in resources}


def get_chembl_query_builder_resource_catalog() -> dict[str, ChEMBLQueryResourceCatalogEntry]:
    """Return ChEMBL resources enabled for query-builder foundations."""
    return {
        key: resource
        for key, resource in get_chembl_query_resource_catalog().items()
        if resource.query_builder_visible
    }


def get_chembl_query_builder_field_catalog(resource_key: str) -> dict[str, ChEMBLQueryFieldCatalogEntry]:
    """Return visible ChEMBL fields for one query-builder resource."""
    resources = get_chembl_query_builder_resource_catalog()
    if resource_key not in resources:
        msg = f"Unsupported ChEMBL query resource '{resource_key}'."
        raise ValueError(msg)
    return {
        key: field for key, field in resources[resource_key].fields.items() if field.query_builder_visible
    }
