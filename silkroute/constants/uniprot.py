"""UniProt database constants and configuration."""

from __future__ import annotations

# Constants for UniProt data fields and cross-references
# Only should be added the fields that are available and defined
# in the file silkroute/core/interfaces/uniprot.py at line 187
VALID_FIELDS = [
    "accession",
    "protein_name",
    "ec",
    "organism_name",
    "gene_primary",
    "organism_id",
    "sequence",
    "length",
    "keyword",
    "temp_dependence",
    "ph_dependence",
    "cc_interaction",
    "ft_variant",
    # "ft_active_site", # Dont work properly in the uniprot api
    # "ft_binding_site", # Dont work properly in the uniprot api
    "ft_site",
    "ft_domain",
    "ft_motif",
    "ft_region",
]

DEFAULT_UNIPROT_RETURN_FIELDS = (
    "accession",
    "protein_name",
    "organism_name",
    "organism_id",
    "sequence",
    "length",
)

VALID_CROSS_REF_FIELDS = {
    "alphafold": "alphafold_ids",
    "biogrid": "biogrid_ids",
    "brenda": "brenda_ids",
    "go": "go_terms",
    "chembl": "chembl_ids",
    "interpro": "interpro_ids",
    "kegg": "kegg_ids",
    "panther": "panther_ids",
    "pathwaycommons": "pathwaycommons_ids",
    "pdb": "pdb_ids",
    "pfam": "pfam_ids",
    "pride": "pride_ids",
    "refseq": "refseq_ids",
    "reactome": "reactome_ids",
    "sabiork": "sabiork_ids",
    "string": "string_ids",
    "rhea": "rhea_ids",
}

# UniProt REST return-field IDs do not always match SilkRoute's parsed output
# names. Keep that translation centralized so callers can request API fields
# while the parser continues to expose its established column names.
UNIPROT_RETURN_FIELD_TO_PARSED_FIELD = {
    "accession": "accession",
    "protein_name": "protein_name",
    "ec": "ec",
    "organism_name": "organism",
    "gene_primary": "gene_primary",
    "organism_id": "organism_id",
    "sequence": "sequence",
    "length": "length",
    "keyword": "keyword",
    "temp_dependence": "temperature",
    "ph_dependence": "ph",
    "cc_interaction": "interactions",
    "ft_variant": "variants",
    "ft_site": "active_sites",
    "ft_domain": "domains",
    "ft_motif": "domains",
    "ft_region": "domains",
    "xref_alphafolddb": "alphafold_ids",
    "xref_brenda": "brenda_ids",
    "cc_catalytic_activity": "chebi_ids",
    "xref_chembl": "chembl_ids",
    "go_id": "go_terms",
    "xref_interpro": "interpro_ids",
    "xref_kegg": "kegg_ids",
    "xref_panther": "panther_ids",
    "xref_pathwaycommons": "pathwaycommons_ids",
    "xref_pdb": "pdb_ids",
    "xref_pfam": "pfam_ids",
    "xref_pride": "pride_ids",
    "xref_reactome": "reactome_ids",
    "xref_refseq": "refseq_ids",
    "rhea": "rhea_ids",
    "xref_sabio-rk": "sabiork_ids",
    "xref_string": "string_ids",
}

# Mapping of cross-reference fields to (field_name, endpoint_name)
# If there is not a uniprot field associated, just use the endpoint name
XREF_MAPPING = {
    "AlphaFold": ("xref_alphafolddb", "alphafold"),
    "BioDBNet": (None, "biodbnet"),
    "BioGRID": (None, "biogrid"),
    "Brenda": ("xref_brenda", "brenda"),
    "ChEMBL": ("xref_chembl", "chembl"),
    "ChEBI": (None, "chebi"),
    "GO": ("go_id", "go"),
    "InterPro": ("xref_interpro", "interpro"),
    "KEGG": ("xref_kegg", "kegg"),
    "Panther": ("xref_panther", "panther"),
    "PathwayCommons": ("xref_pathwaycommons", "pathwaycommons"),
    "PDB": ("xref_pdb", "pdb"),
    "PubChem": (None, "pubchem"),
    "Reactome": ("xref_reactome", "reactome"),
    "Rhea": ("rhea", "rhea"),
    "RefSeq": ("xref_refseq", "refseq"),
    "SABIO-RK": ("xref_sabio-rk", "sabio-rk"),
    "StringDB": ("xref_string", "string"),
}

ENRICHMENT_REQUIRED_UNIPROT_FIELDS: dict[str, tuple[str, ...]] = {
    "alphafold": ("xref_alphafolddb",),
    "biogrid": ("gene_primary", "organism_id"),
    "chembl": ("xref_chembl",),
    "chebi": ("cc_catalytic_activity",),
    "go": ("go_id",),
    "interpro": ("xref_interpro", "accession", "organism_id"),
    "kegg": ("xref_kegg",),
    "pathwaycommons": ("accession", "gene_primary", "organism_id", "xref_reactome"),
    "pathwaycommons_fetch": ("xref_reactome",),
    "pathwaycommons_top_pathways": ("gene_primary", "organism_id"),
    "pathwaycommons_neighborhood": ("accession", "organism_id"),
    "pdb": ("xref_pdb",),
    "pubchem": ("accession",),
    "reactome": ("xref_reactome",),
    "rhea": ("rhea",),
    "refseq": ("xref_refseq",),
    "sabio-rk": ("xref_sabio-rk",),
    "string": ("xref_string", "gene_primary", "organism_id"),
}


def normalize_uniprot_return_fields(value: object) -> list[str]:
    """Normalize UniProt return-field input into stable, deduplicated field IDs."""
    if value is None:
        return []
    if isinstance(value, str):
        raw_values = value.replace("\r\n", "\n").replace("\n", ",").split(",")
    elif isinstance(value, (list, tuple, set)):
        raw_values = value
    else:
        raw_values = [value]

    fields: list[str] = []
    seen: set[str] = set()
    for raw_value in raw_values:
        field = str(raw_value).strip()
        if not field:
            continue
        lookup_value = field.casefold()
        if lookup_value in seen:
            continue
        fields.append(field)
        seen.add(lookup_value)
    return fields


def get_uniprot_parsed_fields(value: object) -> list[str]:
    """Translate UniProt REST return fields to ordered parsed output fields."""
    parsed_fields: list[str] = []
    seen: set[str] = set()
    for field in normalize_uniprot_return_fields(value):
        parsed_field = UNIPROT_RETURN_FIELD_TO_PARSED_FIELD.get(field, field)
        lookup_value = parsed_field.casefold()
        if lookup_value not in seen:
            parsed_fields.append(parsed_field)
            seen.add(lookup_value)
    return parsed_fields


def get_default_uniprot_return_fields() -> list[str]:
    """Return the reviewed default UniProt return fields."""
    return normalize_uniprot_return_fields(DEFAULT_UNIPROT_RETURN_FIELDS)


def get_required_uniprot_fields_for_enrichment(crossref_fields: object) -> list[str]:
    """Return UniProt fields required by selected cross-reference enrichment sources.

    ``accession`` is always included once any enrichment source is recognized: it is the
    provenance key (``source_accession``) that ties every enrichment row back to its
    originating protein, so it must be present even when the user's custom return fields
    omit it.
    """
    required_fields: list[str] = []
    seen: set[str] = set()
    enrichment_requested = False
    for field in normalize_uniprot_return_fields(crossref_fields):
        source = field
        if source.endswith("_all"):
            source = source.rsplit("_", 1)[0]
        required = ENRICHMENT_REQUIRED_UNIPROT_FIELDS.get(source)
        if required is None and "_" in source:
            source_db = source.split("_", 1)[0]
            required = ENRICHMENT_REQUIRED_UNIPROT_FIELDS.get(source_db)
        if required is None:
            continue
        enrichment_requested = True
        for required_field in required:
            lookup_value = required_field.casefold()
            if lookup_value not in seen:
                required_fields.append(required_field)
                seen.add(lookup_value)
    if enrichment_requested and "accession" not in seen:
        required_fields.append("accession")
    return required_fields


def get_effective_uniprot_return_fields(
    value: object,
    crossref_fields: object = None,
) -> list[str]:
    """Return user fields or defaults, merged with fields required for enrichment."""
    fields = normalize_uniprot_return_fields(value) or get_default_uniprot_return_fields()
    seen = {field.casefold() for field in fields}
    for required_field in get_required_uniprot_fields_for_enrichment(crossref_fields):
        lookup_value = required_field.casefold()
        if lookup_value not in seen:
            fields.append(required_field)
            seen.add(lookup_value)
    return fields


DATABASES = {
    "uniprotkb_reviewed": "knowledgebase/complete/uniprot_sprot",
    "uniprotkb_unreviewed": "knowledgebase/complete/uniprot_trembl",
    "uniref100": "uniref/niref100/uniref100",
    "uniref90": "uniref/uniref90/uniref90",
    "uniref50": "uniref/uniref50/uniref50",
}

BASE_URL = "https://ftp.uniprot.org/pub/databases/uniprot/current_release"
