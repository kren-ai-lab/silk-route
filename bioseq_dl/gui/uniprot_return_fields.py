"""Static UniProt return-field catalog for the workflow GUI."""

from __future__ import annotations

from dataclasses import dataclass

from bioseq_dl.constants.uniprot import (
    VALID_FIELDS,
    normalize_uniprot_return_fields,
)


@dataclass(frozen=True)
class UniProtReturnFieldOption:
    """Describe one user-facing UniProt return-field option."""

    field: str
    label: str
    group: str
    description: str = ""


UNIPROT_RETURN_FIELD_OPTIONS: tuple[UniProtReturnFieldOption, ...] = (
    UniProtReturnFieldOption("accession", "Accession", "Identifiers", "Primary UniProt accession."),
    UniProtReturnFieldOption("protein_name", "Protein name", "Protein", "Recommended protein name."),
    UniProtReturnFieldOption("gene_primary", "Primary gene name", "Gene", "Primary gene symbol."),
    UniProtReturnFieldOption("organism_name", "Organism name", "Organism", "Scientific organism name."),
    UniProtReturnFieldOption("organism_id", "Organism taxonomy ID", "Organism", "NCBI taxonomy ID."),
    UniProtReturnFieldOption("sequence", "Sequence", "Sequence", "Amino-acid sequence."),
    UniProtReturnFieldOption("length", "Sequence length", "Sequence", "Sequence length in residues."),
    UniProtReturnFieldOption("ec", "Enzyme Commission number", "Function", "EC number annotations."),
    UniProtReturnFieldOption("keyword", "Keywords", "Annotation", "UniProt keyword annotations."),
    UniProtReturnFieldOption("ft_domain", "Domain features", "Features", "Annotated sequence domains."),
    UniProtReturnFieldOption("ft_region", "Region features", "Features", "Annotated sequence regions."),
    UniProtReturnFieldOption("ft_motif", "Motif features", "Features", "Annotated sequence motifs."),
    UniProtReturnFieldOption("ft_site", "Site features", "Features", "Annotated sequence sites."),
    UniProtReturnFieldOption("ft_variant", "Variant features", "Features", "Annotated sequence variants."),
    UniProtReturnFieldOption("cc_interaction", "Interaction comments", "Comments", "Interaction comments."),
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

CATALOG_FIELD_IDS = {option.field for option in UNIPROT_RETURN_FIELD_OPTIONS}
UNSUPPORTED_CATALOG_FIELDS = sorted(CATALOG_FIELD_IDS - set(VALID_FIELDS))
if UNSUPPORTED_CATALOG_FIELDS:
    msg = f"Unsupported UniProt return-field catalog entries: {UNSUPPORTED_CATALOG_FIELDS}"
    raise RuntimeError(msg)


def get_uniprot_return_field_options() -> dict[str, str]:
    """Return selectable UniProt return-field values mapped to visible labels."""
    return {option.field: option.label for option in UNIPROT_RETURN_FIELD_OPTIONS}


def get_uniprot_return_field_labels() -> dict[str, str]:
    """Return UniProt return-field labels keyed by stable field IDs."""
    return get_uniprot_return_field_options()


def split_known_and_custom_return_fields(value: object) -> tuple[list[str], list[str]]:
    """Split return fields into visible catalog selections and advanced custom fields."""
    known_lookup = {field.casefold(): field for field in get_uniprot_return_field_options()}
    selected_lookup: set[str] = set()
    custom_fields: list[str] = []
    for field in normalize_uniprot_return_fields(value):
        known_field = known_lookup.get(field.casefold())
        if known_field is None:
            custom_fields.append(field)
        else:
            selected_lookup.add(known_field.casefold())
    selections = [
        option.field
        for option in UNIPROT_RETURN_FIELD_OPTIONS
        if option.field.casefold() in selected_lookup
    ]
    return selections, custom_fields


def return_fields_from_selection(selected_fields: object, custom_fields: object = None) -> str:
    """Return comma-separated UniProt field IDs from selector and advanced input values."""
    selected_lookup = {field.casefold() for field in normalize_uniprot_return_fields(selected_fields)}
    fields = [
        option.field
        for option in UNIPROT_RETURN_FIELD_OPTIONS
        if option.field.casefold() in selected_lookup
    ]
    seen = {field.casefold() for field in fields}
    for custom_field in normalize_uniprot_return_fields(custom_fields):
        lookup_value = custom_field.casefold()
        if lookup_value not in seen:
            fields.append(custom_field)
            seen.add(lookup_value)
    return ", ".join(fields)
