"""Shared UniProt query field catalog for friendly query interpretation."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

from bioseq_dl.constants.uniprot import XREF_MAPPING

SUPPORTED_MATCH_MODES = ("any", "all", "not")


@dataclass(frozen=True)
class UniProtQueryFieldCatalogEntry:
    """Metadata for one friendly UniProt query field."""

    key: str
    label: str
    description: str
    placeholder: str
    examples: tuple[str, ...]
    supported_match_modes: tuple[str, ...]
    native_field: str
    value_map: dict[str, str]
    supports_range: bool
    resolver_kind: str | None
    query_builder_visible: bool = True


def build_uniprot_database_value_map() -> dict[str, str]:
    """Return supported database aliases for UniProt cross-reference queries."""
    db_map = {db_name: db_name for _, (_, db_name) in XREF_MAPPING.items()}
    db_map["alphafold"] = "alphafolddb"
    return db_map


def build_uniprot_go_name_map() -> dict[str, str]:
    """Return supported friendly GO names mapped to GO numeric identifiers."""
    return {
        "dna repair": "0006281",
        "protein folding": "0006457",
        "response to heat": "0009408",
        "translation": "0006412",
        "proteolysis": "0006508",
        "antioxidant activity": "0016209",
        "hydrocarbon catabolic process": "0120252",
        "peptidase activity": "0008233",
        "response to stimulus": "0050896",
    }


def build_uniprot_keyword_map() -> dict[str, str]:
    """Return supported friendly UniProt keyword names mapped to keyword ids."""
    return {
        "atp binding": "KW-0067",
        "metal-binding": "KW-0479",
        "antiviral defense": "KW-0051",
        "antiviral protein": "KW-0930",
    }


def build_uniprot_function_map() -> dict[str, str]:
    """Return supported friendly enzyme classes mapped to EC class ids."""
    return {
        "oxidoreductase": "1",
        "transferase": "2",
        "hydrolase": "3",
        "lyase": "4",
        "isomerase": "5",
        "ligase": "6",
        "translocase": "7",
    }


def build_uniprot_taxonomy_id_map() -> dict[str, str]:
    """Return supported friendly taxonomy names mapped to taxonomy identifiers."""
    return {
        "human": "9606",
        "homo sapiens": "9606",
        "mammalia": "40674",
        "mouse": "10090",
        "escherichia coli": "562",
        "ecoli": "562",
        "yeast": "4932",
    }


def make_uniprot_query_field_entry(
    *,
    key: str,
    label: str,
    description: str,
    placeholder: str,
    examples: tuple[str, ...],
    native_field: str,
    value_map: dict[str, str] | None = None,
    supports_range: bool = False,
    resolver_kind: str | None = None,
    query_builder_visible: bool = True,
) -> UniProtQueryFieldCatalogEntry:
    """Create a UniProt field catalog entry with standard match-mode metadata."""
    return UniProtQueryFieldCatalogEntry(
        key=key,
        label=label,
        description=description,
        placeholder=placeholder,
        examples=examples,
        supported_match_modes=SUPPORTED_MATCH_MODES,
        native_field=native_field,
        value_map=dict(value_map or {}),
        supports_range=supports_range,
        resolver_kind=resolver_kind,
        query_builder_visible=query_builder_visible,
    )


@cache
def get_uniprot_query_field_catalog() -> dict[str, UniProtQueryFieldCatalogEntry]:
    """Return the shared catalog of friendly UniProt query fields."""
    database_map = build_uniprot_database_value_map()
    go_name_map = build_uniprot_go_name_map()
    keyword_map = build_uniprot_keyword_map()
    function_map = build_uniprot_function_map()
    taxonomy_id_map = build_uniprot_taxonomy_id_map()

    entries = [
        make_uniprot_query_field_entry(
            key="databases",
            label="Databases",
            description="UniProt cross-reference databases to include.",
            placeholder="alphafold,pdb,string",
            examples=("alphafold", "pdb", "string"),
            native_field="database",
            value_map=database_map,
            resolver_kind="database_map",
        ),
        make_uniprot_query_field_entry(
            key="keywords",
            label="Keywords",
            description="UniProt keywords or supported friendly keyword names.",
            placeholder='"ATP binding","Metal-binding"',
            examples=("ATP binding", "Metal-binding"),
            native_field="keyword",
            value_map=keyword_map,
            resolver_kind="keyword_map",
        ),
        make_uniprot_query_field_entry(
            key="go",
            label="GO term",
            description="GO identifiers or supported friendly GO term names.",
            placeholder='0006281,"DNA repair"',
            examples=("DNA repair", "protein folding", "0006281"),
            native_field="go",
            value_map=go_name_map,
            resolver_kind="go_name_map",
        ),
        make_uniprot_query_field_entry(
            key="taxa",
            label="Taxa",
            description="Taxonomy identifiers or names handled by the current interpreter.",
            placeholder="9606, 10090",
            examples=("9606", "10090", "human"),
            native_field="taxonomy_id",
            value_map=taxonomy_id_map,
            resolver_kind="taxonomy_map",
        ),
        make_uniprot_query_field_entry(
            key="taxon",
            label="Taxon",
            description="Single taxonomy identifier or name handled by the current interpreter.",
            placeholder="9606",
            examples=("9606", "human"),
            native_field="taxonomy_id",
            value_map=taxonomy_id_map,
            resolver_kind="taxonomy_map",
        ),
        make_uniprot_query_field_entry(
            key="taxid",
            label="Taxonomy ID",
            description="Taxonomy identifier handled by the current interpreter.",
            placeholder="9606",
            examples=("9606", "10090"),
            native_field="taxonomy_id",
            value_map=taxonomy_id_map,
            resolver_kind="taxonomy_map",
        ),
        make_uniprot_query_field_entry(
            key="organism",
            label="Organism",
            description="Supported organism names resolved to UniProt organism identifiers.",
            placeholder="Homo sapiens",
            examples=("Homo sapiens", "human", "9606"),
            native_field="organism_id",
            value_map=taxonomy_id_map,
            resolver_kind="organism_map",
        ),
        make_uniprot_query_field_entry(
            key="ec",
            label="EC class",
            description="Supported enzyme class names or EC values.",
            placeholder="oxidoreductase",
            examples=("oxidoreductase", "hydrolase"),
            native_field="ec",
            value_map=function_map,
            resolver_kind="function_map",
        ),
        make_uniprot_query_field_entry(
            key="length",
            label="Sequence length",
            description="Protein sequence length range.",
            placeholder="100-500",
            examples=("100-500",),
            native_field="length",
            supports_range=True,
            resolver_kind="length_transform",
        ),
        make_uniprot_query_field_entry(
            key="temperature",
            label="Temperature",
            description="Temperature range metadata understood by the current workflow interpreter.",
            placeholder="20-30,50-60",
            examples=("20-30", "50-60"),
            native_field="cc_bpcp_temp_dependence",
            supports_range=True,
        ),
        make_uniprot_query_field_entry(
            key="ph",
            label="pH",
            description="pH range metadata understood by the current workflow interpreter.",
            placeholder="6-8",
            examples=("6-8",),
            native_field="cc_bpcp_ph_dependence",
            supports_range=True,
        ),
    ]
    return {entry.key: entry for entry in entries}


@cache
def get_uniprot_query_builder_field_catalog() -> dict[str, UniProtQueryFieldCatalogEntry]:
    """Return fields enabled for the future UniProt GUI query builder."""
    return {
        key: entry for key, entry in get_uniprot_query_field_catalog().items() if entry.query_builder_visible
    }
