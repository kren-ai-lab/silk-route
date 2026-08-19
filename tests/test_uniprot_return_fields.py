"""Offline tests for UniProt enrichment return-field resolution."""

from __future__ import annotations

import pytest

from silkroute.constants.uniprot import (
    get_effective_uniprot_return_fields,
    get_required_uniprot_fields_for_enrichment,
    get_uniprot_parsed_fields,
)


@pytest.mark.parametrize(
    "source", ["chembl", "go", "pdb", "reactome", "kegg", "biogrid", "pathwaycommons_fetch"]
)
def test_enrichment_always_requires_accession_for_provenance(source):
    # source_accession is the provenance key; every recognized enrichment must request it.
    assert "accession" in get_required_uniprot_fields_for_enrichment(source)


def test_accession_added_once_across_multiple_sources():
    required = get_required_uniprot_fields_for_enrichment("chembl,go,pdb")
    assert required.count("accession") == 1


def test_no_accession_without_recognized_enrichment():
    assert get_required_uniprot_fields_for_enrichment("not_a_source") == []
    assert get_required_uniprot_fields_for_enrichment("") == []


def test_effective_fields_add_accession_when_user_omits_it():
    # Custom return fields without accession + an enrichment source -> accession is added.
    effective = get_effective_uniprot_return_fields("gene_primary,length", "chembl")
    assert "accession" in effective


def test_return_fields_map_to_ordered_parser_fields():
    assert get_uniprot_parsed_fields("sequence,organism_name,temp_dependence,xref_string,accession") == [
        "sequence",
        "organism",
        "temperature",
        "string_ids",
        "accession",
    ]
