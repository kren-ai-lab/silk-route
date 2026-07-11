"""Static UniProt return-field catalog for the workflow GUI."""

from __future__ import annotations

from dataclasses import dataclass

from bioseq_dl.constants.uniprot import (
    DEFAULT_UNIPROT_RETURN_FIELDS,
    get_default_uniprot_return_fields,
    get_effective_uniprot_return_fields,
    normalize_uniprot_return_fields,
)

__all__ = [
    "DEFAULT_UNIPROT_RETURN_FIELDS",
    "UNIPROT_RETURN_FIELD_OPTIONS",
    "UniProtReturnFieldOption",
    "get_default_uniprot_return_fields",
    "get_effective_uniprot_return_fields",
    "get_uniprot_return_field_labels",
    "get_uniprot_return_field_options",
    "normalize_uniprot_return_fields",
    "return_fields_from_selection",
    "split_known_and_custom_return_fields",
]


@dataclass(frozen=True)
class UniProtReturnFieldOption:
    """Describe one user-facing UniProt return field option."""

    field: str
    label: str
    group: str
    description: str = ""


UNIPROT_RETURN_FIELD_OPTIONS: tuple[UniProtReturnFieldOption, ...] = (
    UniProtReturnFieldOption("accession", "Accession", "Identifiers", "Primary UniProt accession."),
    UniProtReturnFieldOption("id", "Entry ID", "Identifiers", "UniProt entry identifier."),
    UniProtReturnFieldOption("protein_name", "Protein name", "Protein", "Recommended protein name."),
    UniProtReturnFieldOption("gene_primary", "Primary gene name", "Gene", "Primary gene symbol."),
    UniProtReturnFieldOption("organism_name", "Organism name", "Organism", "Scientific organism name."),
    UniProtReturnFieldOption("organism_id", "Organism taxonomy ID", "Organism", "NCBI taxonomy ID."),
    UniProtReturnFieldOption("sequence", "Sequence", "Sequence", "Amino-acid sequence."),
    UniProtReturnFieldOption("length", "Sequence length", "Sequence", "Sequence length in residues."),
    UniProtReturnFieldOption("ec", "Enzyme Commission number", "Function", "EC number annotations."),
    UniProtReturnFieldOption("keyword", "Keywords", "Annotation", "UniProt keyword annotations."),
    UniProtReturnFieldOption("go_id", "Gene Ontology IDs", "Annotation", "GO identifier annotations."),
    UniProtReturnFieldOption("ft_domain", "Domain features", "Features", "Annotated sequence domains."),
    UniProtReturnFieldOption("ft_region", "Region features", "Features", "Annotated sequence regions."),
    UniProtReturnFieldOption("ft_motif", "Motif features", "Features", "Annotated sequence motifs."),
    UniProtReturnFieldOption("ft_site", "Site features", "Features", "Annotated sequence sites."),
    UniProtReturnFieldOption("ft_variant", "Variant features", "Features", "Annotated sequence variants."),
    UniProtReturnFieldOption("cc_function", "Function comments", "Comments", "Function comment text."),
    UniProtReturnFieldOption("cc_interaction", "Interaction comments", "Comments", "Interaction comments."),
    UniProtReturnFieldOption("cc_subunit", "Subunit comments", "Comments", "Subunit comment text."),
    UniProtReturnFieldOption(
        "cc_catalytic_activity",
        "Catalytic activity comments",
        "Comments",
        "Catalytic activity comment text.",
    ),
    UniProtReturnFieldOption(
        "temp_dependence",
        "Temperature dependence",
        "Biophysical properties",
        "Temperature-dependence comments.",
    ),
    UniProtReturnFieldOption(
        "ph_dependence",
        "pH dependence",
        "Biophysical properties",
        "pH-dependence comments.",
    ),
)


def get_uniprot_return_field_options() -> dict[str, str]:
    """Return selectable UniProt return-field values mapped to visible labels."""
    return {option.field: option.label for option in UNIPROT_RETURN_FIELD_OPTIONS}


def get_uniprot_return_field_labels() -> dict[str, str]:
    """Return UniProt return-field labels keyed by stable field IDs."""
    return get_uniprot_return_field_options()


def split_known_and_custom_return_fields(value: object) -> tuple[list[str], list[str]]:
    """Split return fields into visible catalog selections and advanced custom fields."""
    known_fields = get_uniprot_return_field_options()
    known_lookup = {field.casefold(): field for field in known_fields}
    selections: list[str] = []
    custom_fields: list[str] = []
    for field in normalize_uniprot_return_fields(value):
        known_field = known_lookup.get(field.casefold())
        if known_field:
            selections.append(known_field)
        else:
            custom_fields.append(field)
    return selections, custom_fields


def return_fields_from_selection(selected_fields: object, custom_fields: object = None) -> str:
    """Return comma-separated UniProt field IDs from selector and advanced input values."""
    fields = normalize_uniprot_return_fields(selected_fields)
    known_fields = {field.casefold() for field in fields}
    for custom_field in normalize_uniprot_return_fields(custom_fields):
        if custom_field.casefold() not in known_fields:
            fields.append(custom_field)
            known_fields.add(custom_field.casefold())
    return ", ".join(fields)
