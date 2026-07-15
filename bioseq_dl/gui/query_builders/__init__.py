"""Pure query builder helpers for future GUI workflows."""

from __future__ import annotations

from bioseq_dl.gui.query_builders.chebi import (
    ChEBIQueryBuilderRow,
    build_chebi_friendly_query,
    build_chebi_interpreted_query,
)
from bioseq_dl.gui.query_builders.chembl import (
    ChEMBLFilterQueryBuilderRow,
    build_chembl_friendly_query,
    build_chembl_interpreted_query,
)
from bioseq_dl.gui.query_builders.pubchem import (
    PubChemQueryBuilderRow,
    build_pubchem_friendly_query,
    build_pubchem_interpreted_query,
)
from bioseq_dl.gui.query_builders.registry import (
    QueryBuilderSpec,
    get_query_builder_choices,
    get_query_builder_spec,
    get_query_builder_specs,
)
from bioseq_dl.gui.query_builders.uniprot import (
    UniProtQueryBuilderRow,
    build_uniprot_friendly_query,
    build_uniprot_interpreted_query,
)

__all__ = [
    "ChEBIQueryBuilderRow",
    "ChEMBLFilterQueryBuilderRow",
    "PubChemQueryBuilderRow",
    "QueryBuilderSpec",
    "UniProtQueryBuilderRow",
    "build_chebi_friendly_query",
    "build_chebi_interpreted_query",
    "build_chembl_friendly_query",
    "build_chembl_interpreted_query",
    "build_pubchem_friendly_query",
    "build_pubchem_interpreted_query",
    "build_uniprot_friendly_query",
    "build_uniprot_interpreted_query",
    "get_query_builder_choices",
    "get_query_builder_spec",
    "get_query_builder_specs",
]
